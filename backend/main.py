"""
Production-Ready FastAPI Backend for Enterprise Surveillance System
Handles WebRTC streaming, WebSocket alerts, and REST APIs
"""

from __future__ import annotations
from fastapi import Body, FastAPI, WebSocket, HTTPException, Depends, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Set
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from collections import Counter, defaultdict
import uuid
import numpy as np

from backend.api import websocket as webrtc_module
from backend.api.alerts import router as alerts_router
from backend.api.cameras import router as cameras_router
from backend.api.reports import router as reports_router
from backend.api.students import router as students_router
from backend.database.store import store

try:
    from camera import get_global_camera_manager
except ImportError:
    # Fallback if camera module is not available
    def get_global_camera_manager():
        return None

from aiortc import RTCSessionDescription

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BehaviorType(str, Enum):
    LEANING = "leaning"
    PHONE_DETECTED = "phone_detected"
    GAZE_DOWNWARD = "gaze_downward"
    GAZE_SIDEWAYS = "gaze_sideways"
    EXCESSIVE_TURNING = "excessive_turning"
    WRIST_BELOW_DESK = "wrist_below_desk"
    SHOULDER_MOVEMENT = "shoulder_movement"
    PAPER_SHARING = "paper_sharing"
    REPEATED_GAZE = "repeated_gaze"
    REPEATED_HEAD_TURN = "repeated_head_turn"
    STUDENT_INTERACTION = "student_interaction"
    BENDING_DOWN = "bending_down"


class StudentDetection(BaseModel):
    student_id: str
    track_id: int
    camera_id: str
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float
    timestamp: datetime


class FaceAnalysis(BaseModel):
    face_detected: bool
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None
    gaze_x: float | None = None
    gaze_y: float | None = None
    iris_detected: bool = False
    landmarks: List[List[float]] | None = None  # 468 landmarks


class SkeletonAnalysis(BaseModel):
    skeleton_detected: bool
    keypoints: Dict[str, List[float]] | None = None  # joint_name -> [x, y, confidence]
    leaning_detected: bool = False
    shoulder_angle: float | None = None
    wrist_position: str | None = None  # "above_desk", "below_desk"
    posture_quality: float = 0.0  # 0-1


class BehaviorEvent(BaseModel):
    event_id: str
    student_id: str
    behavior_type: BehaviorType
    timestamp: datetime
    duration_ms: float
    confidence: float


class RiskScore(BaseModel):
    student_id: str
    timestamp: datetime
    score: float  # 0-100
    level: RiskLevel
    components: Dict[str, float]  # {gaze: 0.3, pose: 0.25, phone: 0.2, etc.}
    explanations: List[str]


class Alert(BaseModel):
    alert_id: str
    student_id: str
    timestamp: datetime
    severity: RiskLevel
    reason: str
    behaviors: List[BehaviorEvent]
    evidence_captured: bool
    gemini_explanation: str | None = None


class WebRTCOffer(BaseModel):
    sdp: str
    type: str = "offer"


class WebRTCAnswer(BaseModel):
    sdp: str
    type: str = "answer"


class FramePushRequest(BaseModel):
    camera_id: str
    frame_base64: str
    timestamp: datetime | None = None


class CameraStatus(BaseModel):
    camera_id: str
    status: str  # "streaming", "waiting", "offline"
    connected_peers: int
    fps: int
    codec: str
    last_frame_time: datetime | None = None
    students_tracked: int = 0


# ==================== FASTAPI SETUP ====================

app = FastAPI(
    title="Enterprise Exam Surveillance System",
    description="Production-grade AI invigilation platform",
    version="1.0.0"
)

# Ensure storage directories exist at root
from pathlib import Path
from fastapi.staticfiles import StaticFiles
Path("storage/evidence").mkdir(parents=True, exist_ok=True)
Path("storage/reports").mkdir(parents=True, exist_ok=True)

app.mount("/storage", StaticFiles(directory="storage"), name="storage")

runtime_state: Dict[str, Any] = {
    "started": False,
    "startup_errors": [],
    "pipeline": None,
    "camera_manager": None,
}

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CONNECTION MANAGERS ====================

class ConnectionManager:
    """Manages WebSocket connections for alerts"""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # camera_id -> set of user_ids
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        async with self.lock:
            self.active_connections[user_id] = websocket
        logger.info(f"✅ User {user_id} connected to alerts")

    async def disconnect(self, user_id: str):
        async with self.lock:
            self.active_connections.pop(user_id, None)
        logger.info(f"❌ User {user_id} disconnected")

    async def subscribe_camera(self, user_id: str, camera_id: str):
        """Subscribe user to camera alerts"""
        async with self.lock:
            if camera_id not in self.subscriptions:
                self.subscriptions[camera_id] = set()
            self.subscriptions[camera_id].add(user_id)

    async def unsubscribe_camera(self, user_id: str, camera_id: str):
        """Unsubscribe user from camera alerts"""
        async with self.lock:
            if camera_id in self.subscriptions:
                self.subscriptions[camera_id].discard(user_id)

    async def broadcast_alert(self, alert: Alert, camera_id: str):
        """Broadcast alert to subscribed users"""
        async with self.lock:
            subscribers = self.subscriptions.get(camera_id, set()).copy()

        for user_id in subscribers:
            connection = self.active_connections.get(user_id)
            if connection:
                try:
                    await connection.send_json({
                        "type": "alert",
                        "data": alert.model_dump(mode='json')
                    })
                except Exception as e:
                    logger.error(f"Failed to send alert to {user_id}: {e}")

    async def broadcast_status(self, status: dict, camera_id: str):
        """Broadcast camera status update"""
        async with self.lock:
            subscribers = self.subscriptions.get(camera_id, set()).copy()

        for user_id in subscribers:
            connection = self.active_connections.get(user_id)
            if connection:
                try:
                    await connection.send_json({
                        "type": "status",
                        "data": status
                    })
                except Exception as e:
                    logger.error(f"Failed to send status to {user_id}: {e}")


connection_manager = ConnectionManager()


# ==================== DATA HELPERS ====================

def _risk_level_value(level: RiskLevel | str | None) -> str | None:
    """Return a comparable string value for risk levels."""
    if level is None:
        return None
    return level.value if isinstance(level, RiskLevel) else str(level)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse values stored by the in-memory store into datetimes for sorting/grouping."""
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _stored_timestamp(item: Dict[str, Any]) -> datetime:
    """Best-effort timestamp accessor used for recent-first sorting."""
    return _parse_datetime(item.get("timestamp")) or _parse_datetime(item.get("created_at")) or datetime.min


def _risk_sort_value(item: Dict[str, Any]) -> float:
    """Support both legacy `risk_score` and current `score` field names."""
    value = item.get("score", item.get("risk_score", 0))
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _behavior_label(value: Any) -> str:
    """Normalize behavior labels for consistent analytics counters."""
    if isinstance(value, BehaviorType):
        value = value.value
    normalized = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    dashboard_labels = {
        "phone_detected": "Using Mobile",
        "mobile_detected": "Using Mobile",
        "using_mobile": "Using Mobile",
        "gaze_sideways": "Looking Around",
        "excessive_turning": "Looking Around",
        "looking_around": "Looking Around",
        "gaze_downward": "Looking to Copy",
        "paper_sharing": "Looking to Copy",
        "looking_to_copy": "Looking to Copy",
        "leaning": "Leaning",
    }
    return dashboard_labels.get(normalized, normalized.replace("_", " ").title())


def _alert_payload(alert: Alert) -> Dict[str, Any]:
    """Convert an Alert model into the shared store's alert shape."""
    behaviors = [behavior.model_dump(mode="json") for behavior in alert.behaviors]
    max_confidence = max((behavior.confidence for behavior in alert.behaviors), default=0.0)
    return {
        **alert.model_dump(mode="json"),
        "alert_type": alert.reason or "SUSPICIOUS_BEHAVIOR",
        "risk_score": max_confidence * 100 if max_confidence <= 1 else max_confidence,
        "severity": alert.severity.value,
        "behaviors": behaviors,
    }


def _filter_alerts(
    student_id: str | None = None,
    severity: RiskLevel | str | None = None,
) -> List[Dict[str, Any]]:
    """Read alerts from the shared store and apply common filters."""
    severity_value = _risk_level_value(severity)
    alerts = store.list("alerts")
    if student_id:
        alerts = [item for item in alerts if item.get("student_id") == student_id]
    if severity_value:
        alerts = [item for item in alerts if item.get("severity") == severity_value]
    return sorted(alerts, key=_stored_timestamp, reverse=True)


def _latest_risk_by_student() -> Dict[str, Dict[str, Any]]:
    """Return the latest risk score record for every student."""
    latest: Dict[str, Dict[str, Any]] = {}
    for item in store.list("risk_scores"):
        student_id = item.get("student_id")
        if not student_id:
            continue
        if student_id not in latest or _stored_timestamp(item) > _stored_timestamp(latest[student_id]):
            latest[student_id] = item
    return latest


def _timeline_from_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group alerts into minute buckets for dashboard charts."""
    buckets: Dict[str, int] = defaultdict(int)
    for alert in alerts:
        timestamp = _stored_timestamp(alert)
        if timestamp == datetime.min:
            continue
        minute = timestamp.replace(second=0, microsecond=0).isoformat()
        buckets[minute] += 1
    return [
        {"timestamp": timestamp, "alert_count": count}
        for timestamp, count in sorted(buckets.items())
    ]


# ==================== INITIALIZATION ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Store main loop for thread-safe websocket broadcasts from pipeline thread
    runtime_state["main_loop"] = asyncio.get_running_loop()

    logger.info("🚀 Starting surveillance backend...")
    runtime_state["startup_errors"] = []

    # Load config
    config = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "webrtc": {
            "bitrate": 2500000,
            "fps": 30,
        },
        "alert_thresholds": {
            "low": 20,
            "medium": 40,
            "high": 60,
            "critical": 80,
        }
    }

    # Initialize the process-wide WebRTC server exactly once.
    server = webrtc_module.init_webrtc_server(config)
    logger.info("✅ WebRTC server initialized")

    # Build the existing integrated pipeline without allowing optional CV/model
    # failures to prevent FastAPI from becoming healthy.
    pipeline = None
    try:
        from pipeline.integrated_pipeline import IntegratedSurveillancePipeline
        pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)
        pipeline.start()
        runtime_state["pipeline"] = pipeline
        logger.info("✅ Detection pipeline initialized and started")
    except Exception as exc:
        runtime_state["startup_errors"].append(f"pipeline: {exc}")
        logger.exception("Detection pipeline unavailable; backend will remain operational")

    # ==================== CRITICAL FIX ====================
    # Initialize Camera Manager with frame_sink to push frames to WebRTC
    def frame_sink_callback(camera_id: str, frame: np.ndarray, timestamp: float) -> None:
        """Send camera frames immediately to WebRTC with cached AI overlays, and submit to detection thread."""
        try:
            active_pipeline = runtime_state.get("pipeline")
            if active_pipeline is not None:
                # 1. Draw the latest cached AI annotations onto a copy of the frame
                annotated = active_pipeline.overlay_latest_results(camera_id, frame)
                # 2. Push to WebRTC server immediately (no blocking, 30 FPS)
                server.push_frame(camera_id, annotated, timestamp)
                # 3. Submit the raw frame to the AI pipeline thread for asynchronous processing
                active_pipeline.submit_frame(camera_id, frame, timestamp)
                return

            server.push_frame(camera_id, frame, timestamp)
        except Exception as e:
            logger.error(f"❌ Failed to push frame to WebRTC: {e}")

    def pipeline_result_callback(frame_results: Dict[str, Any]) -> None:
        """Publish existing pipeline results to the shared REST/WebSocket state."""
        camera_id = frame_results.get("camera_id")
        frame_timestamp = frame_results.get("timestamp") or datetime.now()
        for student in frame_results.get("students", {}).values():
            store.upsert("students", "student_id", {
                **student,
                "camera_id": camera_id,
                "tracking_id": student.get("track_id"),
                "last_seen": frame_timestamp.isoformat() if isinstance(frame_timestamp, datetime) else str(frame_timestamp),
            })
            store.append("risk_scores", {
                "student_id": student.get("student_id"),
                "camera_id": camera_id,
                "risk_score": student.get("risk_score", 0),
                "risk_level": student.get("risk_level", "low"),
                "timestamp": frame_timestamp.isoformat() if isinstance(frame_timestamp, datetime) else str(frame_timestamp),
            })
        for alert in frame_results.get("alerts", []):
            store.upsert("alerts", "alert_id", alert)

            # Broadcast to WebSockets in a thread-safe manner
            main_loop = runtime_state.get("main_loop")
            if main_loop is not None:
                try:
                    ts = datetime.fromisoformat(alert["timestamp"]) if isinstance(alert["timestamp"], str) else alert["timestamp"]
                    behaviors_list = []
                    for b in alert.get("behaviors", []):
                        b_ts = datetime.fromisoformat(b["timestamp"]) if isinstance(b["timestamp"], str) else b["timestamp"]
                        behaviors_list.append(BehaviorEvent(
                            event_id=b.get("event_id", f"EV-{uuid.uuid4().hex[:6].upper()}"),
                            student_id=b.get("student_id", alert["student_id"]),
                            behavior_type=b.get("behavior_type", "gaze_sideways"),
                            timestamp=b_ts,
                            duration_ms=b.get("duration_ms", 0.0),
                            confidence=b.get("confidence", 1.0)
                        ))

                    alert_obj = Alert(
                        alert_id=alert["alert_id"],
                        student_id=alert["student_id"],
                        timestamp=ts,
                        severity=RiskLevel(alert["severity"].lower()),
                        reason=alert.get("reason", "Suspicious behavior"),
                        behaviors=behaviors_list,
                        evidence_captured=alert.get("evidence_captured", False),
                        gemini_explanation=alert.get("gemini_explanation")
                    )
                    asyncio.run_coroutine_threadsafe(
                        connection_manager.broadcast_alert(alert_obj, "global"),
                        main_loop
                    )
                    logger.info(f"📢 Broadcasted alert {alert['alert_id']} to WebSockets")
                except Exception as e:
                    logger.error(f"❌ Failed to parse and broadcast alert: {e}")

    if pipeline is not None:
        pipeline.result_sink = pipeline_result_callback

    from camera import init_global_camera_manager, load_camera_config
    camera_config = load_camera_config()
    manager = init_global_camera_manager(config=camera_config, frame_sink=frame_sink_callback)
    runtime_state["camera_manager"] = manager
    logger.info("✅ Camera Manager initialized with WebRTC frame sink")

    # Auto-connect first available camera
    try:
        result = manager.auto_discover_and_connect()
        if result.get("connected"):
            logger.info(f"✅ Auto-connected to camera: {result.get('primary_camera_id')}")
        else:
            logger.warning("⚠️ No camera auto-connected; backend remains ready for manual connect")
    except Exception as exc:
        runtime_state["startup_errors"].append(f"camera discovery: {exc}")
        logger.exception("Camera discovery failed; backend remains operational")
    runtime_state["started"] = True


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down surveillance backend...")

    # Stop capture before the pipeline so no new work is submitted.
    try:
        manager = runtime_state.get("camera_manager") or get_global_camera_manager()
        manager.stop_all()
        logger.info("✅ Cameras stopped")
    except Exception as e:
        logger.error(f"Camera shutdown error: {e}")

    pipeline = runtime_state.get("pipeline")
    if pipeline is not None:
        try:
            pipeline.stop()
            logger.info("✅ Detection pipeline stopped")
        except Exception:
            logger.exception("Pipeline shutdown error")

    # Clean up WebRTC last.
    try:
        server = webrtc_module.get_webrtc_server()
        await server.cleanup()
    except Exception:
        logger.exception("WebRTC shutdown error")
    runtime_state["started"] = False
    logger.info("✅ Shutdown complete")


# ==================== WEBRTC ENDPOINTS ====================

def clean_sdp_force_vp8(sdp: str) -> str:
    """Strip all codecs except VP8 (and generic controls) from the SDP to prevent aiortc H.264 parsing crashes."""
    lines = sdp.split("\r\n")
    cleaned_lines = []
    
    video_pt_to_exclude = set()
    video_pt_to_keep = set()
    
    in_video = False
    for line in lines:
        if line.startswith("m=video "):
            in_video = True
        elif line.startswith("m=audio ") or line.startswith("m=application "):
            in_video = False
            
        if in_video and line.startswith("a=rtpmap:"):
            parts = line.split(":")
            if len(parts) > 1:
                subparts = parts[1].split(" ")
                pt = subparts[0]
                codec = subparts[1].split("/")[0] if len(subparts) > 1 else ""
                if codec.upper() != "VP8":
                    video_pt_to_exclude.add(pt)
                else:
                    video_pt_to_keep.add(pt)
                    
    in_video = False
    for line in lines:
        if line.startswith("m=video "):
            in_video = True
            parts = line.split(" ")
            media_info = parts[:4]
            payloads = parts[4:]
            kept_payloads = [p for p in payloads if p in video_pt_to_keep]
            if not kept_payloads:
                kept_payloads = [p for p in payloads if p not in video_pt_to_exclude]
            if not kept_payloads:
                kept_payloads = payloads
            cleaned_lines.append(" ".join(media_info + kept_payloads))
            continue
            
        elif line.startswith("m=audio ") or line.startswith("m=application "):
            in_video = False
            
        if in_video:
            exclude_line = False
            for pt in video_pt_to_exclude:
                if (f":{pt} " in line or 
                    f":{pt}\r" in line or 
                    line.endswith(f":{pt}") or 
                    line.startswith(f"a=fmtp:{pt}") or 
                    line.startswith(f"a=rtcp-fb:{pt}") or 
                    line.startswith(f"a=rtpmap:{pt}")):
                    exclude_line = True
                    break
            if exclude_line:
                continue
                
        cleaned_lines.append(line)
        
    return "\r\n".join(cleaned_lines)


@app.post("/api/webrtc/{camera_id}/offer")
async def webrtc_offer(camera_id: str, offer: WebRTCOffer):
    """
    Handle WebRTC offer from frontend
    Returns SDP answer for peer connection
    """
    try:
        logger.info(f"📡 WebRTC offer received for camera {camera_id}")

        server = webrtc_module.get_webrtc_server()
        server.register_camera(camera_id)

        # Parse offer - clean it first to force VP8 and prevent aiortc H264 profile crashes
        cleaned_sdp = clean_sdp_force_vp8(offer.sdp)
        offer_description = RTCSessionDescription(sdp=cleaned_sdp, type=offer.type)

        # Get answer
        answer = await server.handle_offer(camera_id, offer_description)

        logger.info(f"✅ WebRTC answer sent for camera {camera_id}")

        return WebRTCAnswer(sdp=answer.sdp, type="answer")

    except Exception as e:
        logger.error(f"❌ WebRTC offer error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/webrtc/cameras/status")
async def get_all_cameras_status():
    """Get status of all cameras"""
    server = webrtc_module.get_webrtc_server()
    statuses = server.get_all_cameras_status()
    return {"cameras": statuses, "timestamp": datetime.now()}


@app.get("/api/webrtc/camera/{camera_id}/status")
async def get_camera_status(camera_id: str):
    """Get status of specific camera"""
    server = webrtc_module.get_webrtc_server()
    status = server.get_camera_status(camera_id)
    return {**status, "camera_id": camera_id, "timestamp": datetime.now()}


# ==================== FRAME PUSH ENDPOINT ====================

@app.post("/api/detection/push-frame")
async def push_frame(
    payload: FramePushRequest | None = Body(default=None),
    camera_id: str | None = None,
    frame_base64: str | None = None,
    timestamp: datetime | None = None,
):
    """
    Push processed frame to WebRTC streaming buffer
    This is called by the edge AI processing pipeline
    """
    try:
        if payload is not None:
            camera_id = payload.camera_id
            frame_base64 = payload.frame_base64
            timestamp = payload.timestamp
        if not camera_id or not frame_base64:
            raise HTTPException(status_code=422, detail="camera_id and frame_base64 are required")
        if timestamp is None:
            timestamp = datetime.now()

        # Decode base64 frame
        import base64
        import cv2

        frame_data = base64.b64decode(frame_base64)
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise ValueError("Failed to decode frame")

        # Push to WebRTC server
        server = webrtc_module.get_webrtc_server()
        server.push_frame(camera_id, frame, timestamp.timestamp())

        return {"status": "ok", "camera_id": camera_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Frame push error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== ALERT ENDPOINTS ====================

@app.post("/api/alerts/publish")
async def publish_alert(alert: Alert):
    """
    Publish alert from edge processing
    Broadcasts to all connected WebSocket clients
    """
    try:
        logger.warning(f"🚨 Alert: {alert.severity} - Student {alert.student_id}")
        stored_alert = store.upsert("alerts", "alert_id", _alert_payload(alert))

        for behavior in alert.behaviors:
            store.append("behavior_history", {
                **behavior.model_dump(mode="json"),
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
            })

        await connection_manager.broadcast_alert(alert, "global")
        return {"status": "published", "alert_id": alert.alert_id, "alert": stored_alert}
    except Exception as e:
        logger.error(f"❌ Alert publish error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/alerts/history")
async def get_alert_history(
    limit: int = 50,
    student_id: str | None = None,
    severity: RiskLevel | None = None
):
    """Get historical alerts (from database)"""
    alerts = _filter_alerts(student_id=student_id, severity=severity)
    return {
        "alerts": alerts[:limit],
        "total": len(alerts),
        "limit": limit,
        "student_id": student_id,
        "severity": _risk_level_value(severity),
    }


# ==================== WEBSOCKET ALERTS ====================

@app.websocket("/ws/alerts/{user_id}")
async def websocket_alerts(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time alerts
    ONLY sends alert metadata, NOT video frames
    """
    await connection_manager.connect(websocket, user_id)

    try:
        while True:
            # Keep connection alive and listen for subscription updates
            data = await websocket.receive_json()

            if data.get("type") == "subscribe":
                camera_id = data.get("camera_id")
                await connection_manager.subscribe_camera(user_id, camera_id)
                await websocket.send_json({
                    "type": "subscription_updated",
                    "camera_id": camera_id,
                    "status": "subscribed"
                })

            elif data.get("type") == "unsubscribe":
                camera_id = data.get("camera_id")
                await connection_manager.unsubscribe_camera(user_id, camera_id)
                await websocket.send_json({
                    "type": "subscription_updated",
                    "camera_id": camera_id,
                    "status": "unsubscribed"
                })

    except WebSocketDisconnect:
        await connection_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
        await connection_manager.disconnect(user_id)


# ==================== DETECTION DATA ENDPOINTS ====================

@app.post("/api/detection/behavior-event")
async def log_behavior_event(event: BehaviorEvent):
    """Log behavior event from detection pipeline"""
    logger.info(f"📊 Behavior event: {event.behavior_type} - Student {event.student_id}")
    payload = event.model_dump(mode="json")
    payload["behavior_type"] = event.behavior_type.value
    item = store.append("behavior_history", payload)
    return {"status": "logged", "event_id": event.event_id, "event": item}


@app.post("/api/detection/risk-score")
async def log_risk_score(score: RiskScore):
    """Log risk score from fusion engine"""
    logger.debug(f"📈 Risk score: {score.score} ({score.level}) - Student {score.student_id}")
    payload = score.model_dump(mode="json")
    payload["level"] = score.level.value
    payload["risk_level"] = score.level.value
    item = store.append("risk_scores", payload)
    return {"status": "logged", "risk_score": item}


@app.post("/api/detection/student-detection")
async def log_student_detection(detection: StudentDetection):
    """Log student detection from YOLO"""
    logger.debug(f"👤 Student detected: {detection.student_id} - Camera {detection.camera_id}")
    payload = detection.model_dump(mode="json")
    item = store.upsert("students", "student_id", {
        "student_id": detection.student_id,
        "camera_id": detection.camera_id,
        "tracking_id": detection.track_id,
        "last_bbox": detection.bbox,
        "last_confidence": detection.confidence,
        "last_seen": detection.timestamp.isoformat(),
    })
    tracking_event = store.append("behavior_history", {
        **payload,
        "event_id": f"TRK-{uuid.uuid4().hex[:10].upper()}",
        "behavior_type": "student_detection",
        "duration_ms": 0,
    })
    return {"status": "logged", "student": item, "tracking_event": tracking_event}


# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/analytics/dashboard")
async def get_dashboard_analytics():
    """Get dashboard analytics summary"""
    alerts = _filter_alerts()
    students = store.list("students")
    latest_risk = _latest_risk_by_student()
    high_risk_students = [
        {
            "student_id": student_id,
            "risk_score": _risk_sort_value(item),
            "risk_level": item.get("risk_level") or item.get("level"),
            "timestamp": item.get("timestamp") or item.get("created_at"),
        }
        for student_id, item in latest_risk.items()
        if (item.get("risk_level") or item.get("level")) in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
        or _risk_sort_value(item) >= 60
    ]
    high_risk_students.sort(key=lambda item: item["risk_score"], reverse=True)

    severity_counts = Counter(alert.get("severity", "unknown") for alert in alerts)
    behavior_counts: Counter[str] = Counter()
    for alert in alerts:
        for behavior in alert.get("behaviors", []) or []:
            behavior_counts[_behavior_label(behavior.get("behavior_type"))] += 1
    return {
        "total_students": len(students),
        "total_alerts": len(alerts),
        "high_risk_students": high_risk_students,
        "alert_trends": _timeline_from_alerts(alerts),
        "severity_counts": dict(severity_counts),
        "behavior_counts": dict(behavior_counts),
        "timestamp": datetime.now()
    }


@app.get("/api/analytics/timeline")
async def get_analytics_timeline():
    """Return alert timeline arrays used by the React analytics chart."""
    timeline = _timeline_from_alerts(_filter_alerts())
    return {
        "timestamps": [item["timestamp"] for item in timeline],
        "alert_counts": [item["alert_count"] for item in timeline],
        "timeline": timeline,
        "timestamp": datetime.now(),
    }


@app.get("/api/analytics/cheating-types")
async def get_cheating_type_distribution():
    """Return behavior distribution using the same shape as the dashboard fallback API."""
    behavior_counts: Counter[str] = Counter()
    for event in store.list("behavior_history"):
        behavior_type = event.get("behavior_type")
        if behavior_type == "student_detection":
            continue
        behavior_counts[_behavior_label(behavior_type)] += 1
    return {
        "cheating_types": dict(behavior_counts),
        "total_alerts": sum(behavior_counts.values()),
        "timestamp": datetime.now(),
    }


@app.get("/api/analytics/heatmap/{camera_id}")
async def get_heatmap(camera_id: str):
    """Get suspicious activity heatmap for camera"""
    grid_size = 10
    heatmap = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
    detections = [
        event for event in store.list("behavior_history")
        if event.get("camera_id") == camera_id and event.get("bbox")
    ]
    for detection in detections:
        bbox = detection.get("bbox") or []
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        center_x = max(0.0, min(1.0, ((x1 + x2) / 2) / max(max(x1, x2, 1.0), 1.0)))
        center_y = max(0.0, min(1.0, ((y1 + y2) / 2) / max(max(y1, y2, 1.0), 1.0)))
        heatmap[min(grid_size - 1, int(center_y * grid_size))][min(grid_size - 1, int(center_x * grid_size))] += 1
    return {
        "camera_id": camera_id,
        "heatmap": heatmap,
        "points": len(detections),
        "timestamp": datetime.now()
    }


@app.get("/api/analytics/student/{student_id}")
async def get_student_analytics(student_id: str):
    """Get analytics for specific student"""
    risks = sorted(
        [item for item in store.list("risk_scores") if item.get("student_id") == student_id],
        key=_stored_timestamp,
        reverse=True,
    )
    behaviors = sorted(
        [item for item in store.list("behavior_history") if item.get("student_id") == student_id],
        key=_stored_timestamp,
        reverse=True,
    )
    alerts = _filter_alerts(student_id=student_id)
    latest_risk = risks[0] if risks else {}
    return {
        "student_id": student_id,
        "risk_score": _risk_sort_value(latest_risk),
        "risk_level": latest_risk.get("risk_level") or latest_risk.get("level"),
        "risk_history": risks,
        "behaviors": behaviors,
        "alerts": alerts,
        "timestamp": datetime.now()
    }


# Register routers after local fixed-path routes so dynamic router paths such as
# /api/alerts/{alert_id} do not shadow /api/alerts/history.
app.include_router(alerts_router, prefix="/api")
app.include_router(cameras_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(students_router, prefix="/api")


# ==================== HEALTH CHECKS ====================

@app.get("/health")
async def health_check():
    """System health check"""
    server = webrtc_module.get_webrtc_server()
    manager = runtime_state.get("camera_manager") or get_global_camera_manager()
    pipeline = runtime_state.get("pipeline")
    errors = list(runtime_state.get("startup_errors", []))
    components = {
        "webrtc": server.health() if hasattr(server, "health") else {"status": "running"},
        "camera_manager": {"status": "running", "summary": manager.summary()},
        "pipeline": pipeline.health() if pipeline is not None else {"status": "unavailable"},
    }
    healthy = (
        runtime_state.get("started", False)
        and components["webrtc"].get("status") == "running"
        and components["pipeline"].get("status") in {"running", "degraded"}
    )
    return {
        "status": "healthy" if healthy else "degraded",
        "ready": runtime_state.get("started", False),
        "webrtc_server": components["webrtc"].get("status", "unknown"),
        "cameras_registered": len(server.get_all_cameras_status()),
        "components": components,
        "startup_errors": errors,
        "timestamp": datetime.now()
    }


@app.get("/")
async def root():
    """API documentation"""
    return {
        "name": "Enterprise Exam Surveillance System",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "webrtc": "/api/webrtc/",
            "alerts": "/api/alerts/",
            "detection": "/api/detection/",
            "analytics": "/api/analytics/",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
