"""
Production-Ready FastAPI Backend for Enterprise Surveillance System
Handles WebRTC streaming, WebSocket alerts, and REST APIs
"""

from __future__ import annotations
from fastapi import FastAPI, WebSocket, HTTPException, Depends, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Set
import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
import uuid
import numpy as np

from backend.api import websocket as webrtc_module
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


# ==================== INITIALIZATION ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("🚀 Starting surveillance backend...")
    
    # Load config
    config = {
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
    
    # Initialize WebRTC server
    webrtc_module.init_webrtc_server(config)
    logger.info("✅ WebRTC server initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down surveillance backend...")
    server = webrtc_module.get_webrtc_server()
    await server.cleanup()
    logger.info("✅ Shutdown complete")


# ==================== WEBRTC ENDPOINTS ====================

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
        
        # Parse offer
        offer_description = RTCSessionDescription(sdp=offer.sdp, type=offer.type)
        
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
    camera_id: str,
    frame_base64: str,  # Base64 encoded frame
    timestamp: datetime = None
):
    """
    Push processed frame to WebRTC streaming buffer
    This is called by the edge AI processing pipeline
    """
    try:
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
        await connection_manager.broadcast_alert(alert, "global")
        return {"status": "published", "alert_id": alert.alert_id}
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
    # TODO: Implement database query
    return {
        "alerts": [],
        "total": 0,
        "limit": limit
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
    # TODO: Store in database
    return {"status": "logged", "event_id": event.event_id}


@app.post("/api/detection/risk-score")
async def log_risk_score(score: RiskScore):
    """Log risk score from fusion engine"""
    logger.debug(f"📈 Risk score: {score.score} ({score.level}) - Student {score.student_id}")
    # TODO: Store in database
    return {"status": "logged"}


@app.post("/api/detection/student-detection")
async def log_student_detection(detection: StudentDetection):
    """Log student detection from YOLO"""
    logger.debug(f"👤 Student detected: {detection.student_id} - Camera {detection.camera_id}")
    # TODO: Store in database
    return {"status": "logged"}


# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/analytics/dashboard")
async def get_dashboard_analytics():
    """Get dashboard analytics summary"""
    return {
        "total_students": 0,
        "total_alerts": 0,
        "high_risk_students": [],
        "alert_trends": [],
        "timestamp": datetime.now()
    }


@app.get("/api/analytics/heatmap/{camera_id}")
async def get_heatmap(camera_id: str):
    """Get suspicious activity heatmap for camera"""
    return {
        "camera_id": camera_id,
        "heatmap": None,  # 2D array
        "timestamp": datetime.now()
    }


@app.get("/api/analytics/student/{student_id}")
async def get_student_analytics(student_id: str):
    """Get analytics for specific student"""
    return {
        "student_id": student_id,
        "risk_score": 0,
        "behaviors": [],
        "alerts": [],
        "timestamp": datetime.now()
    }


# ==================== HEALTH CHECKS ====================

@app.get("/health")
async def health_check():
    """System health check"""
    server = webrtc_module.get_webrtc_server()
    cameras = server.get_all_cameras_status()
    
    return {
        "status": "healthy",
        "webrtc_server": "running",
        "cameras_registered": len(cameras),
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
