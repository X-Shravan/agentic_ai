"""
Complete Integration Pipeline
Demonstrates full end-to-end system integration
Camera capture → Detection → Tracking → Analysis → Streaming → Frontend
"""

from __future__ import annotations
import cv2
import numpy as np
import asyncio
import time
import logging
import queue
import threading
import uuid
import concurrent.futures
from collections import deque
from datetime import datetime
from typing import Any, Dict, Iterable

# Import system modules
from backend.agents.behavior_agent import FusionInput, MultiModalFusionEngine
from backend.agents.face_agent import FaceAnalysisAgent
from backend.agents.gaze_agent import GazeAgent
from backend.agents.gemini_agent import GeminiBatchProcessor, GeminiReasoningEngine
from backend.agents.skeleton_agent import SkeletonAnalyzer
from backend.agents.detection_agent import Detection
from backend.api.websocket import get_webrtc_server

# Import re-connected AI invigilation agents
from backend.agents.role_classification_agent import RoleClassificationAgent
from backend.cv.reference_verifier import ReferenceVerifier
from backend.agents.smartwatch_vision_verifier import SmartwatchVisionVerifier
from backend.agents.answersheet_vision_verifier import AnswerSheetVisionVerifier
from backend.risk_engine.risk_calculator import RiskCalculator
from backend.agents.decision_agent import DecisionAgent
from backend.agents.evidence_agent import EvidenceAgent
from backend.agents.report_agent import ReportAgent
from backend.crewai.crew import SurveillanceCrew
from backend.langgraph.workflow import SurveillanceWorkflow, build_workflow
from backend.langgraph.state import SurveillanceState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedSurveillancePipeline:
    """
    Complete surveillance pipeline integrating all components
    """
    
    def __init__(self, config: dict, webrtc_server=None, result_sink=None):
        self.config = config
        self.result_sink = result_sink
        
        # Initialize components
        self.detector = None
        self.tracker = None
        if config.get("enable_detection", True):
            try:
                from backend.agents.detection_agent import DetectionAgent
                from backend.agents.tracking_agent import TrackingAgent

                self.detector = DetectionAgent(config)
                self.tracker = TrackingAgent(config)
            except Exception as exc:
                logger.warning("⚠️ Detection/tracking unavailable; synthetic mode enabled: %s", exc)

        self.skeleton_analyzer = SkeletonAnalyzer(
            frame_width=config.get("frame_width", 640),
            frame_height=config.get("frame_height", 480),
            desk_y_ratio=config.get("desk_y_ratio", 0.7)
        )
        self.face_agent = FaceAnalysisAgent()
        self.gaze_agent = GazeAgent()
        
        b_conf = config.get("behavior_temporal", {})
        from backend.agents.temporal_behavior import BehaviorConfig, StrictnessMode
        behavior_config = BehaviorConfig()
        if b_conf:
            mode_str = str(b_conf.get("strictness_mode", "strict")).lower()
            if mode_str == "normal":
                behavior_config.apply_mode(StrictnessMode.NORMAL)
            elif mode_str == "very_strict":
                behavior_config.apply_mode(StrictnessMode.VERY_STRICT)
            else:
                behavior_config.apply_mode(StrictnessMode.STRICT)
            windows = b_conf.get("windows", {})
            if "short" in windows:
                behavior_config.window_short = float(windows["short"])
            if "medium" in windows:
                behavior_config.window_medium = float(windows["medium"])
            if "long" in windows:
                behavior_config.window_long = float(windows["long"])
            rep = b_conf.get("repetition", {})
            if "gaze_medium" in rep:
                behavior_config.repetition_gaze_medium = int(rep["gaze_medium"])
            if "gaze_high" in rep:
                behavior_config.repetition_gaze_high = int(rep["gaze_high"])
            cd = b_conf.get("cooldown", {})
            if "behavioral_alert" in cd:
                behavior_config.cooldown_seconds = float(cd["behavioral_alert"])

        self.fusion_engine = MultiModalFusionEngine(
            temporal_window=config.get("temporal_window", 15),
            persistence_threshold=config.get("persistence_threshold", 10),
            behavior_config=behavior_config
        )
        
        # Gemini (optional)
        gemini_key = config.get("gemini_api_key")
        if gemini_key:
            self.gemini = GeminiReasoningEngine(gemini_key)
            self.batch_processor = GeminiBatchProcessor(self.gemini)
        else:
            self.gemini = None
            self.batch_processor = None
            
        # Reconnected Surveillance Agents
        self.role_classifier = RoleClassificationAgent(config)
        self.risk_calculator = RiskCalculator()
        self.decision_agent = DecisionAgent(config)
        self.evidence_agent = EvidenceAgent()
        self.report_agent = ReportAgent()
        self.crew = SurveillanceCrew(self.gemini)
        
        # Reference-image verification layer
        self.reference_verifier = ReferenceVerifier(config)
        self.verification_cache = {}  # (track_id, obj_class) -> (verified_class, similarity)
        
        # Gemini Vision smartwatch verifier layer
        self.smartwatch_verifier = SmartwatchVisionVerifier(config)
        self.gemini_vision_cache = {}  # (track_id, obj_class) -> (verified_class, confidence, timestamp, bbox)
        
        # Gemini Vision answer sheet verifier layer
        self.answersheet_verifier = AnswerSheetVisionVerifier(config)
        self._answersheet_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="AnswerSheetVerify"
        )
        self.answersheet_vision_cache = {}  # (camera_id, track_id) or (track_id, obj_class) -> (verified_class, confidence, timestamp, bbox)
        self._book_stability = {}           # (track_id, obj_class) -> hit_count
        self._book_detection_times = {}     # (track_id, obj_class) -> t0_time
        self._book_min_stability_hits = 1   # Start verification immediately on first candidate detection
        self._answersheet_in_flight = set() # (camera_id, track_id) currently in verification
        self._book_temporal_history = {}    # cache_key -> list of recent verification outcomes
        self._book_confirmed_labels = {}    # cache_key -> confirmed_label ("answer_sheet" or "book")
        self._book_last_logged_info = {}    # cache_key -> {"confirmed_label": str, "res_class": str}
        self.temporal_confirmation_frames = int(
            config.get("book_verification", {}).get("temporal_confirmation_frames", 3)
        )
        
        # Scientific Calculator verification layer (completely independent)
        from calculator_verification import CalculatorCandidateDetector, CalculatorConfig, CalculatorGeminiVerifier
        self.calculator_config = CalculatorConfig.from_dict(config)
        self.calculator_detector = CalculatorCandidateDetector(self.calculator_config)
        self.calculator_verifier = CalculatorGeminiVerifier(self.calculator_config)
        self.workflow_impl = SurveillanceWorkflow(
            detection_agent=self.detector,
            tracking_agent=self.tracker,
            face_agent=self.face_agent,
            gaze_agent=self.gaze_agent,
            skeleton_agent=self.skeleton_analyzer,
            behavior_agent=self.fusion_engine,
            risk_calculator=self.risk_calculator,
            evidence_agent=self.evidence_agent,
            gemini_agent=self.gemini,
            report_agent=self.report_agent
        )
        self.workflow = build_workflow(self.workflow_impl)
        
        # The FastAPI lifecycle owns the process-wide WebRTC server.
        try:
            self.webrtc_server = webrtc_server or get_webrtc_server()
        except Exception:
            self.webrtc_server = None
        
        # State management
        self.running = False
        self.students_tracked = {}  # track_id -> student_data
        self.phone_session_timers = {}  # student_id -> start_timestamp
        self.phone_session_alerted = {}  # student_id -> bool
        self.sw_session_timers = {}      # student_id -> start_timestamp
        self.sw_session_alerted = {}     # student_id -> bool
        self._frame_queue: queue.Queue[tuple[str, np.ndarray, float]] = queue.Queue(
            maxsize=1
        )
        self._worker_thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._camera_errors: Dict[str, str] = {}
        self._last_processed_at: Dict[str, float] = {}
        self._frames_submitted = 0
        self._frames_processed = 0
        self._frames_dropped = 0
        
        # Thread-safe caching for latest AI results
        self._latest_detections = []
        self._latest_tracking_results = []
        self._latest_skeleton_results = None
        self._latest_result_timestamp: float = 0.0
        self._latest_result_frame_id: int = 0
        self._latest_results_lock = threading.Lock()
        
        logger.info("✅ Integrated pipeline initialized with re-connected surveillance agents")

    def start(self) -> bool:
        """Start the worker used by CameraStream frame callbacks."""
        with self._state_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                self.running = True
                return True
            self.running = True
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="IntegratedDetectionPipeline",
                daemon=True,
            )
            self._worker_thread.start()
        logger.info("✅ Detection pipeline worker started")
        return True

    def submit_frame(self, camera_id: str, frame: np.ndarray, timestamp: float | None = None) -> bool:
        """Queue a latest frame without blocking a camera capture thread."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            logger.warning("Ignoring invalid frame from %s", camera_id)
            return False
        if not self.running:
            return False

        # Drop old frame if queue is full before copying the new one
        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()
                self._frame_queue.task_done()
                self._frames_dropped += 1
            except queue.Empty:
                pass

        item = (camera_id, frame.copy(), float(timestamp or time.time()))
        try:
            self._frame_queue.put_nowait(item)
        except queue.Full:
            self._frames_dropped += 1
            return False
        self._frames_submitted += 1
        return True

    def _find_track_id_for_detection(self, det: Any, tracking_results: Iterable[Any]) -> int:
        """Find associated Track ID for a detection with direct track IoU priority and class compatibility."""
        if hasattr(det, "track_id") and det.track_id is not None:
            return det.track_id
        det_bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
        det_cls = getattr(det, "class_name", "") or (det.get("class_name", "") if isinstance(det, dict) else "")
        from backend.agents.tracking_agent import iou, are_classes_compatible
        if det_bbox and tracking_results:
            # 1. Direct IoU match with a compatible tracked object
            best_iou = 0.0
            best_tid = None
            for track in tracking_results:
                t_cls = getattr(track, "class_name", "")
                if not are_classes_compatible(det_cls, t_cls):
                    continue
                t_bbox = getattr(track, "bbox", None)
                if isinstance(t_bbox, (list, tuple)) and len(t_bbox) == 4:
                    cur_iou = iou(det_bbox, t_bbox)
                    if cur_iou > best_iou:
                        best_iou = cur_iou
                        best_tid = getattr(track, "track_id", None)
            if best_iou > 0.35 and best_tid is not None:
                return best_tid
            # 2. Match with active track objects_detected of compatible class
            for track in tracking_results:
                for obj in getattr(track, "objects_detected", []):
                    if are_classes_compatible(det_cls, obj.get("class_name", "")) and tuple(obj.get("bbox", ())) == tuple(det_bbox):
                        return obj.get("track_id", track.track_id)
            # 3. Match with closest track of COMPATIBLE class only
            closest_track_id = None
            min_dist = float('inf')
            det_center = det.center if hasattr(det, "center") else (
                ((det_bbox[0] + det_bbox[2]) // 2, (det_bbox[1] + det_bbox[3]) // 2)
            )
            for track in tracking_results:
                t_cls = getattr(track, "class_name", "")
                if not are_classes_compatible(det_cls, t_cls):
                    continue
                track_bbox = getattr(track, "bbox", None)
                if isinstance(track_bbox, (list, tuple)) and len(track_bbox) == 4:
                    tx1, ty1, tx2, ty2 = track_bbox
                    t_center = ((tx1 + tx2) // 2, (ty1 + ty2) // 2)
                    dist = ((t_center[0] - det_center[0])**2 + (t_center[1] - det_center[1])**2)**0.5
                    if dist < min_dist and dist < 150.0:
                        min_dist = dist
                        closest_track_id = getattr(track, "track_id", None)
            if closest_track_id is not None:
                return closest_track_id
        # Fallback track ID when no compatible track is in vicinity
        return getattr(det, "track_id", None) or 1

    def _trigger_early_answersheet_verification(self, detections: List[Any], tracking_results: Iterable[Any], frame: np.ndarray, camera_id: str = "cam_0"):
        """Trigger Answer Sheet verification as early as possible on the current live camera frame when YOLO detects BOOK."""
        for det in detections:
            class_name = getattr(det, "class_name", "")
            norm_class = class_name.lower().replace(" ", "_").replace("-", "_")
            if norm_class in {"book", "book_paper", "answer_book", "notebook", "paper_sheet", "answer_sheet"}:
                track_id = self._find_track_id_for_detection(det, tracking_results)
                bbox = getattr(det, "bbox", (0, 0, 0, 0))
                yolo_conf = float(getattr(det, "confidence", 0.80))
                is_cand = bool(getattr(det, "is_candidate", False))
                self._verify_answersheet_with_gemini(
                    track_id, class_name, bbox, frame, camera_id=camera_id,
                    yolo_conf=yolo_conf, is_candidate=is_cand
                )

    def _trigger_calculator_verification(
        self,
        detections: List[Any],
        tracking_results: Iterable[Any],
        frame: np.ndarray,
        camera_id: str = "cam_0",
    ) -> None:
        """Trigger independent background verification for scientific calculator candidates."""
        if not getattr(self, "calculator_verifier", None) or not getattr(self, "calculator_config", None):
            return
        if not self.calculator_config.enabled:
            return
        try:
            from calculator_verification import CalculatorCandidate
            candidates = self.calculator_detector.detect_candidates(frame, existing_detections=detections)
            for cand in candidates:
                cand_track_id = None
                if tracking_results:
                    for trk in tracking_results:
                        t_bbox = getattr(trk, "bbox", None)
                        if t_bbox and self.calculator_detector._compute_iou(cand.bbox, t_bbox) > 0.40:
                            cand_track_id = getattr(trk, "track_id", None)
                            break
                cand.track_id = cand_track_id
                self.calculator_verifier.trigger_async_verification(frame, cand, camera_id=camera_id)

            # In addition, check if YOLO detected a cell phone, and dispatch for calculator verification
            # in case YOLO misclassified a calculator as a cell phone
            if detections:
                for det in detections:
                    cname = getattr(det, "class_name", "") or (det.get("class_name") if isinstance(det, dict) else "")
                    if cname in {"cell phone", "phone"}:
                        dbbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
                        if not dbbox or len(dbbox) != 4:
                            continue
                        cand_bbox = tuple(int(v) for v in dbbox)
                        if any(self.calculator_detector._compute_iou(cand_bbox, c.bbox) > 0.60 for c in candidates):
                            continue
                        cand_track_id = self._find_track_id_for_detection(det, tracking_results)
                        phone_cand = CalculatorCandidate(
                            bbox=cand_bbox,
                            confidence=float(getattr(det, "confidence", 0.70)),
                            source="yolo",
                            track_id=cand_track_id,
                        )
                        self.calculator_verifier.trigger_async_verification(frame, phone_cand, camera_id=camera_id)
        except Exception as e:
            logger.debug("Calculator verification trigger error: %s", e)

    def _sync_detections_for_display(self, detections: List[Any], tracking_results: Iterable[Any], camera_id: str = "cam_0") -> List[Any]:
        """Synchronize raw YOLO detections with verified semantic labels (e.g. answer_sheet, analog watch)."""
        from backend.agents.detection_agent import Detection
        sync_detections = []
        for det in detections:
            cname = (getattr(det, "class_name", "") or (det.get("class_name", "") if isinstance(det, dict) else "")).lower().strip()
            if cname == "laptop":
                continue
            track_id = self._find_track_id_for_detection(det, tracking_results)
            if det.class_name == "smart watch":
                det_copy = Detection(bbox=det.bbox, confidence=det.confidence, class_name=det.class_name, track_id=track_id)
                if track_id is not None:
                    v_class, v_conf = self._get_gemini_verification_result(track_id, "smart watch")
                    if v_class == "smartwatch":
                        det_copy.class_name = "smart watch"
                        det_copy.confidence = v_conf if v_conf > 0 else det.confidence
                    elif v_class in {"not_smartwatch", "analog_watch"}:
                        det_copy.class_name = "analog watch"
                        det_copy.confidence = v_conf if v_conf > 0 else det.confidence
                    elif v_class == "pending":
                        det_copy.class_name = "analog watch"
                        det_copy.confidence = 0.0
                    else:
                        det_copy.class_name = "analog watch"
                        det_copy.confidence = 0.0
                else:
                    det_copy.class_name = "analog watch"
                    det_copy.confidence = 0.0
                if det_copy.class_name == "analog watch" and det_copy.confidence == 0.0:
                    continue
                sync_detections.append(det_copy)
            elif det.class_name in {"book", "book_paper", "answer_book", "notebook", "paper_sheet", "answer_sheet"}:
                is_cand = getattr(det, "is_candidate", False)
                v_class, v_conf = self._get_answersheet_verification_result(track_id, det.class_name, camera_id=camera_id, bbox=det.bbox)
                threshold = self.config.get("answer_sheet_verify", {}).get("threshold", 0.80)
                
                # TWO-STAGE BEHAVIOR:
                # Stage 1 produced BOOK + bounding box.
                # Stage 2 determined ANSWER_SHEET or BOOK.
                # Bounding box is ALWAYS displayed on overlay (never suppressed!).
                if v_class == "answer_sheet" and v_conf >= threshold:
                    final_class = "answer_sheet"
                    final_conf = v_conf
                    if self.tracker is not None and track_id is not None:
                        self.tracker.update_track_class(track_id, "answer_sheet", safe=True)
                else:
                    final_class = "book"
                    final_conf = v_conf if v_conf > 0 else det.confidence
                    if self.tracker is not None and track_id is not None:
                        self.tracker.update_track_class(track_id, "book", safe=True)

                det_copy = Detection(bbox=det.bbox, confidence=final_conf, class_name=final_class, is_candidate=is_cand, track_id=track_id)
                sync_detections.append(det_copy)
            elif det.class_name in {"cell phone", "phone", "calculator", "scientific_calculator"}:
                det_copy = Detection.from_item(det)
                det_copy.track_id = track_id
                calc_res = None
                if getattr(self, "calculator_verifier", None):
                    calc_res = self.calculator_verifier.get_cached_result(camera_id, track_id, det.bbox)
                if calc_res and calc_res.safe and calc_res.object_type == "SCIENTIFIC_CALCULATOR":
                    det_copy.class_name = "scientific_calculator"
                    det_copy.confidence = calc_res.confidence
                    det_copy.safe = True
                    if self.tracker is not None and track_id is not None:
                        self.tracker.update_track_class(track_id, "scientific_calculator", safe=True)
                    logger.info(f"🧮 [CALCULATOR] Track {track_id} corrected from {det.class_name.upper()} -> SCIENTIFIC CALCULATOR (display)")
                    sync_detections.append(det_copy)
                else:
                    sync_detections.append(det_copy)
            else:
                det_copy = Detection.from_item(det)
                det_copy.track_id = track_id
                sync_detections.append(det_copy)

        # Surface confirmed standalone calculator candidates on overlay ONLY if present in current detections
        if getattr(self, "calculator_verifier", None) and getattr(self, "calculator_detector", None):
            for key, c_res in list(self.calculator_verifier.cache.items()):
                if isinstance(key, tuple) and key[0] == camera_id:
                    if c_res.safe and c_res.object_type == "SCIENTIFIC_CALCULATOR":
                        for d in sync_detections:
                            if self.calculator_detector._compute_iou(c_res.bbox, d.bbox) > 0.40:
                                d.class_name = "scientific_calculator"
                                d.safe = True
                                d.confidence = c_res.confidence
        return sync_detections

    def overlay_latest_results(self, camera_id: str, frame: np.ndarray) -> np.ndarray:
        """Overlay the latest cached AI detections and skeleton on a frame."""
        annotated = frame.copy()
        with self._latest_results_lock:
            detections = list(self._latest_detections)
            tracking_results = list(self._latest_tracking_results)
            skeleton_results = self._latest_skeleton_results
            res_timestamp = getattr(self, "_latest_result_timestamp", 0.0)

        # Freshness / TTL check: do not draw stale overlay if AI worker latency is too old (> 0.75s)
        if res_timestamp > 0 and (time.time() - res_timestamp) > 0.75:
            return annotated

        if self.tracker is not None and tracking_results:
            try:
                annotated = self.tracker.draw_tracks(annotated, tracking_results)
            except Exception as e:
                logger.error(f"Error drawing cached tracks: {e}")
        elif self.detector is not None and detections:
            try:
                sync_detections = self._sync_detections_for_display(detections, tracking_results, camera_id=camera_id)
                annotated = self.detector.draw_detections(annotated, sync_detections)
            except Exception as e:
                logger.error(f"Error drawing cached detections: {e}")

        if skeleton_results is not None and getattr(skeleton_results, "detected", False):
            try:
                annotated = self.skeleton_analyzer.draw_skeleton(annotated, skeleton_results)
            except Exception as e:
                logger.error(f"Error drawing cached skeleton: {e}")

        return annotated

    def _worker_loop(self) -> None:
        """Keep processing after per-camera or per-frame failures."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while self.running or not self._frame_queue.empty():
                try:
                    camera_id, frame, timestamp = self._frame_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                try:
                    loop.run_until_complete(self._process_camera_frame(frame, camera_id, timestamp))
                    self._last_processed_at[camera_id] = time.time()
                    self._camera_errors.pop(camera_id, None)
                    self._frames_processed += 1
                except Exception as exc:
                    self._camera_errors[camera_id] = str(exc)
                    logger.exception("Frame processing failed for %s; pipeline remains active", camera_id)
                finally:
                    self._frame_queue.task_done()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    async def _process_camera_frame(self, frame: np.ndarray, camera_id: str, timestamp: float | None = None) -> dict:
        """Process one camera frame without blocking the camera acquisition thread."""
        annotated = frame.copy()
        detections = []
        tracking_results = []
        if self.detector is not None and self.tracker is not None:
            raw_dets = self.detector.detect(frame)
            detections = [d for d in raw_dets if getattr(d, "class_name", "").lower().strip() != "laptop"]

            tracking_results = self.tracker.update(detections, frame=frame)
            # EARLY VERIFICATION TRIGGER on live camera frame (triggered directly by YOLO BOOK detection)
            self._trigger_early_answersheet_verification(detections, tracking_results, frame, camera_id=camera_id)
            # Standalone calculator candidate verification (completely independent)
            self._trigger_calculator_verification(detections, tracking_results, frame, camera_id=camera_id)
            sync_detections = self._sync_detections_for_display(detections, tracking_results, camera_id=camera_id)
            if self.tracker is not None and tracking_results:
                annotated = self.tracker.draw_tracks(annotated, tracking_results)
            elif self.detector is not None and sync_detections:
                annotated = self.detector.draw_detections(annotated, sync_detections)

        now_ts = float(timestamp or time.time())
        with self._latest_results_lock:
            self._latest_detections = detections
            self._latest_tracking_results = tracking_results
            self._latest_result_timestamp = now_ts
            self._latest_result_frame_id = self._frames_processed

        res = await self.process_frame(annotated, camera_id, tracking_results, timestamp=timestamp, clean_frame=frame)

        with self._latest_results_lock:
            self._latest_skeleton_results = res.get("skeleton")

        return res
    
    async def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        yolo_results: dict | Iterable[Any] | None,
        face_mesh_results: dict = None,
        timestamp: float | None = None,
        clean_frame: np.ndarray = None,
    ) -> dict:
        """
        Process single frame through complete pipeline
        
        Args:
            frame: Input frame (BGR)
            camera_id: Camera identifier
            yolo_results: Tracking results as either {track_id: {bbox, confidence, class}}
                          or Track-like objects with track_id/bbox/confidence
            face_mesh_results: Optional face mesh results
        
        Returns:
            Processing results with all analyses
        """
        # 1. Structured log for Camera frame received
        logger.info(f"📸 CAMERA [{camera_id}] - Frame Received")

        # Clean up verification cache for inactive track IDs
        active_track_ids = set()
        if yolo_results:
            for item in yolo_results:
                tid = getattr(item, "track_id", None) or (item.get("track_id") if isinstance(item, dict) else None)
                if tid is not None:
                    active_track_ids.add(tid)
            # Retain fallback track ID 1 so standalone crops are not wiped immediately
            active_track_ids.add(1)
            self.verification_cache = {
                k: v for k, v in self.verification_cache.items()
                if k[0] in active_track_ids
            }
            self.gemini_vision_cache = {
                k: v for k, v in self.gemini_vision_cache.items()
                if k[0] in active_track_ids
            }
            now_cache = time.time()
            max_cache_age = getattr(self.answersheet_verifier, "cache_duration", 10.0)
            cleaned_as_cache = {}
            for k, v in self.answersheet_vision_cache.items():
                if len(v) < 3 or (now_cache - v[2]) > max_cache_age:
                    continue
                # Invalidate if track ID has disappeared from active tracks
                if isinstance(k, tuple):
                    tid = None
                    if len(k) == 2:
                        if isinstance(k[1], int):
                            tid = k[1]
                        elif isinstance(k[0], int):
                            tid = k[0]
                    if tid is not None and tid not in active_track_ids:
                        continue  # Track disappeared -> invalidate cached result
                cleaned_as_cache[k] = v
            self.answersheet_vision_cache = cleaned_as_cache
            self._book_stability = {
                k: v for k, v in self._book_stability.items()
                if k[0] in active_track_ids
            }
            self._book_detection_times = {
                k: v for k, v in self._book_detection_times.items()
                if k[0] in active_track_ids
            }
            self._book_temporal_history = {
                k: v for k, v in self._book_temporal_history.items()
                if not (isinstance(k, tuple) and len(k) == 2 and isinstance(k[1], int) and k[1] not in active_track_ids)
            }
            self._book_confirmed_labels = {
                k: v for k, v in self._book_confirmed_labels.items()
                if not (isinstance(k, tuple) and len(k) == 2 and isinstance(k[1], int) and k[1] not in active_track_ids)
            }
            self._book_last_logged_info = {
                k: v for k, v in self._book_last_logged_info.items()
                if not (isinstance(k, tuple) and len(k) == 2 and isinstance(k[1], int) and k[1] not in active_track_ids)
            }

        frame_results = {
            "timestamp": datetime.now(),
            "camera_id": camera_id,
            "students": {},
            "alerts": [],
            "calculators": [],
            "frame_annotated": frame.copy()
        }

        # Count persons and phones detected in YOLO results
        person_count = 0
        phone_count = 0
        if yolo_results:
            for item in yolo_results:
                cls_name = getattr(item, "class_name", "") or (item.get("class_name") if isinstance(item, dict) else "")
                tid = getattr(item, "track_id", None) or (item.get("track_id") if isinstance(item, dict) else None)
                conf = getattr(item, "confidence", 0.0) or (item.get("confidence", 0.0) if isinstance(item, dict) else 0.0)
                if tid is not None and cls_name:
                    logger.info(f"[YOLO] Track={tid} {cls_name.upper()} confidence={float(conf):.2f}")
                if cls_name == "person":
                    person_count += 1
                elif cls_name in {"cell phone", "phone"}:
                    phone_count += 1
        
        # 2. Structured log for YOLO detection stage
        logger.info(f"🔍 YOLO [{camera_id}] - Persons Detected: {person_count}, Phones Detected: {phone_count}")

        # 3. Structured log for DeepSORT tracking stage
        track_ids = []
        if yolo_results:
            for item in yolo_results:
                tid = getattr(item, "track_id", None) or (item.get("track_id") if isinstance(item, dict) else None)
                if tid is not None:
                    track_ids.append(tid)
        logger.info(f"🆔 DeepSORT [{camera_id}] - Confirmed Track IDs: {track_ids}")

        # 4. Classify roles using RoleClassificationAgent
        try:
            valid_tracks = [t for t in yolo_results if hasattr(t, "history")] if yolo_results else []
            if valid_tracks:
                self.role_classifier.classify(valid_tracks)
        except Exception as e:
            logger.error(f"Failed to run role classifier: {e}")

        # Use clean frame for CV analysis to prevent annotations from disrupting keypoints
        cv_frame = clean_frame if clean_frame is not None else frame

        # 5. Run skeleton analysis
        skeleton_results = self.skeleton_analyzer.analyze(cv_frame, face_mesh_results)
        frame_results["skeleton"] = skeleton_results
        
        # Annotate skeleton on frame
        if skeleton_results.detected:
            frame_annotated = self.skeleton_analyzer.draw_skeleton(
                frame_results["frame_annotated"],
                skeleton_results
            )
            frame_results["frame_annotated"] = frame_annotated
        
        # 6. Process each detected student
        for track_id, detection in self._iter_student_detections(yolo_results):
            student_id = f"{camera_id}_{track_id}"

            # Filter out invigilators
            is_student = True
            if hasattr(detection, "track_id") and track_id in self.role_classifier.classifications:
                is_student = self.role_classifier.is_student(track_id)
            if not is_student:
                logger.info(f"⏭️ Skipping track {track_id}: Classified as Invigilator")
                continue

            # Run Face Mesh & Iris Gaze analysis
            face_results = self.face_agent.analyze(cv_frame, detection)
            gaze_results = self.gaze_agent.analyze(cv_frame, face_results, detection)

            # Reference image verification layer for watches and books/papers
            student_objects = self._value(detection, "objects_detected", []) or []
            for obj in student_objects:
                obj_class = obj.get("class_name", "")
                normalized_class = obj_class.lower().replace(" ", "_").replace("-", "_")
                if normalized_class in {"smart_watch", "smartwatch"}:
                    query_class = obj_class
                        
                    bbox = obj.get("bbox", (0, 0, 0, 0))
                    self._verify_smartwatch_with_gemini(track_id, query_class, bbox, cv_frame)
                    v_class, v_conf = self._get_gemini_verification_result(track_id, query_class)
                    
                    if v_class == "smartwatch":
                        obj["class_name"] = "smart watch"
                        obj["confirmed"] = True
                        logger.info(f"[SMARTWATCH VISION] Confirmed smartwatch for Student {student_id}")
                    elif v_class in {"not_smartwatch", "analog_watch"}:
                        obj["class_name"] = "analog watch"
                        logger.info(f"[SMARTWATCH VISION] Reclassified candidate to analog watch for Student {student_id}")
                    elif v_class == "pending":
                        obj["class_name"] = "analog watch"  # unconfirmed while pending
                    else:
                        obj["class_name"] = "digital watch"  # uncertain fallback
                    
                    # Print precise diagnostic log
                    has_phone = any(o.get("class_name") in {"cell phone", "mobile", "phone"} for o in student_objects)
                    print("YOLO CLASS:")
                    print("smartwatch")
                    print("YOLO CONFIDENCE:")
                    print(f"{obj.get('confidence', 0.0):.2f}")
                    print("VISION INPUT:")
                    print("smartwatch verification")
                    print("VISION OUTPUT:")
                    print(v_class)
                    print("FINAL VERIFIED CLASS:")
                    print(obj["class_name"])
                    print("MOBILE PHONE CLASS:")
                    print("cell phone" if has_phone else "None")
                    print("MOBILE PHONE BRANCH ENTERED:")
                    print("True" if has_phone else "False")
                    print()
                elif normalized_class == "analog_watch":
                    cache_key = (track_id, obj_class)
                    bbox = obj.get("bbox", (0, 0, 0, 0))
                    now = time.time()
                    
                    is_stale = False
                    if cache_key in self.verification_cache:
                        cached_val = self.verification_cache[cache_key]
                        if len(cached_val) == 4:
                            v_class, v_sim, cached_time, cached_bbox = cached_val
                            # Check area change
                            x1_c, y1_c, x2_c, y2_c = cached_bbox
                            x1, y1, x2, y2 = bbox
                            area_cached = max(1, (x2_c - x1_c) * (y2_c - y1_c))
                            area_current = max(1, (x2 - x1) * (y2 - y1))
                            area_ratio = area_current / area_cached
                            if area_ratio < 0.5 or area_ratio > 1.5:
                                is_stale = True
                            if now - cached_time > self.reference_verifier.cache_duration:
                                is_stale = True
                        else:
                            is_stale = True
                            
                    if cache_key not in self.verification_cache or is_stale:
                        x1, y1, x2, y2 = bbox
                        h_f, w_f = cv_frame.shape[:2]
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w_f, x2), min(h_f, y2)
                        
                        if x2 > x1 and y2 > y1:
                            crop = cv_frame[y1:y2, x1:x2]
                            verified_class, similarity = self.reference_verifier.verify(crop, obj_class)
                            self.verification_cache[cache_key] = (verified_class, similarity, now, bbox)
                            
                            # Print precise requested log format
                            if verified_class == "analog_watch":
                                logger.info(f"[REFERENCE_VERIFY] Track={track_id} YOLO={obj_class} Result=analog_watch Score={similarity:.2f} Status=NORMAL")
                            else:
                                logger.info(f"[REFERENCE_VERIFY] Track={track_id} YOLO={obj_class} Result={verified_class} Score={similarity:.2f} Status=UNCERTAIN")
                        else:
                            self.verification_cache[cache_key] = ("unknown", 0.0, now, bbox)
                            
                    verified_class, similarity, _, _ = self.verification_cache[cache_key]
                    
                    if verified_class == "analog_watch":
                        obj["class_name"] = "analog watch"
                        logger.info(f"[REFERENCE VERIFY] Reclassified watch to normal analog watch for Student {student_id}")

                elif normalized_class in {"book", "book_paper", "answer_book", "notebook", "paper_sheet", "answer_sheet"}:
                    bbox = obj.get("bbox", (0, 0, 0, 0))
                    y_conf = float(obj.get("confidence", 0.80))
                    is_cand = bool(obj.get("is_candidate", False))
                    self._verify_answersheet_with_gemini(
                        track_id, obj_class, bbox, cv_frame, camera_id=camera_id,
                        yolo_conf=y_conf, is_candidate=is_cand
                    )
                    v_class, v_conf = self._get_answersheet_verification_result(track_id, obj_class, camera_id=camera_id, bbox=bbox)
                    
                    threshold = self.config.get("answer_sheet_verify", {}).get("threshold", 0.80)
                    if v_class == "answer_sheet" and v_conf >= threshold:
                        obj["class_name"] = "answer_sheet"
                        obj["confirmed"] = True
                        logger.info(f"[ANSWER SHEET VISION] Confirmed answer sheet for Student {student_id}")
                    elif v_class == "book":
                        obj["class_name"] = "book"
                        obj["confirmed"] = True

                elif normalized_class in {"cell_phone", "mobile", "phone", "calculator", "scientific_calculator"}:
                    bbox = obj.get("bbox", (0, 0, 0, 0))
                    calc_res = None
                    if getattr(self, "calculator_verifier", None):
                        calc_res = self.calculator_verifier.get_cached_result(camera_id, track_id, bbox)
                    if calc_res and calc_res.safe and calc_res.object_type == "SCIENTIFIC_CALCULATOR":
                        logger.info(f"🧮 [ARBITRATION] Track {track_id} = SCIENTIFIC CALCULATOR / SAFE")
                        logger.info(f"🧮 [FUSION] Track={track_id} {obj_class.upper()} -> SCIENTIFIC CALCULATOR")
                        logger.info(f"🧮 [RISK] Track={track_id} SCIENTIFIC CALCULATOR -> SAFE")
                        obj["class_name"] = "scientific_calculator"
                        obj["safe"] = True
                        obj["confidence"] = calc_res.confidence
                        obj["phone_confidence"] = 0.0
                        if not any(o.get("class_name") in {"cell phone", "mobile", "phone"} and not o.get("safe", False) for o in student_objects):
                            if isinstance(detection, dict):
                                detection["phone_confidence"] = 0.0
                            else:
                                setattr(detection, "phone_confidence", 0.0)
                    elif calc_res and calc_res.object_type == "NOT_CALCULATOR":
                        logger.info(f"📱 [ARBITRATION] Track {track_id} = CELL PHONE / CRITICAL")
                        logger.info(f"📱 [RISK] Track={track_id} CELL PHONE -> CRITICAL")
                    elif calc_res and calc_res.classification == "uncertain":
                        logger.info(f"🧮 [CALCULATOR] Verification uncertain for Track {track_id}")

            # Also handle direct detection class verification if applicable
            direct_class = self._value(detection, "class_name", "")
            if direct_class:
                normalized_direct = direct_class.lower().replace(" ", "_").replace("-", "_")
                if normalized_direct in {"smart_watch", "smartwatch"}:
                    query_class = direct_class
                        
                    bbox = self._value(detection, "bbox", (0, 0, 0, 0))
                    self._verify_smartwatch_with_gemini(track_id, query_class, bbox, cv_frame)
                    v_class, v_conf = self._get_gemini_verification_result(track_id, query_class)
                    
                    if v_class == "smartwatch":
                        if isinstance(detection, dict):
                            detection["class_name"] = "smart watch"
                            detection["confirmed"] = True
                        else:
                            setattr(detection, "class_name", "smart watch")
                            setattr(detection, "confirmed", True)
                    elif v_class in {"not_smartwatch", "analog_watch"}:
                        if isinstance(detection, dict):
                            detection["class_name"] = "analog watch"
                        else:
                            setattr(detection, "class_name", "analog watch")
                    elif v_class == "pending":
                        if isinstance(detection, dict):
                            detection["class_name"] = "analog watch"  # unconfirmed while pending
                        else:
                            setattr(detection, "class_name", "analog watch")
                    else:
                        if isinstance(detection, dict):
                            detection["class_name"] = "digital watch"
                        else:
                            setattr(detection, "class_name", "digital watch")
                    
                    # Print precise diagnostic log
                    has_phone = False
                    student_objects = self._value(detection, "objects_detected", []) or []
                    if student_objects:
                        has_phone = any(o.get("class_name") in {"cell phone", "mobile", "phone"} for o in student_objects)
                    print("YOLO CLASS:")
                    print("smartwatch")
                    print("YOLO CONFIDENCE:")
                    print(f"{self._value(detection, 'confidence', 0.0):.2f}")
                    print("VISION INPUT:")
                    print("smartwatch verification")
                    print("VISION OUTPUT:")
                    print(v_class)
                    print("FINAL VERIFIED CLASS:")
                    print(self._value(detection, 'class_name', ''))
                    print("MOBILE PHONE CLASS:")
                    print("cell phone" if has_phone else "None")
                    print("MOBILE PHONE BRANCH ENTERED:")
                    print("True" if has_phone else "False")
                    print()
                elif normalized_direct == "analog_watch":
                    cache_key = (track_id, direct_class)
                    bbox = self._value(detection, "bbox", (0, 0, 0, 0))
                    now = time.time()
                    
                    is_stale = False
                    if cache_key in self.verification_cache:
                        cached_val = self.verification_cache[cache_key]
                        if len(cached_val) == 4:
                            v_class, v_sim, cached_time, cached_bbox = cached_val
                            x1_c, y1_c, x2_c, y2_c = cached_bbox
                            x1, y1, x2, y2 = bbox
                            area_cached = max(1, (x2_c - x1_c) * (y2_c - y1_c))
                            area_current = max(1, (x2 - x1) * (y2 - y1))
                            area_ratio = area_current / area_cached
                            if area_ratio < 0.5 or area_ratio > 1.5:
                                is_stale = True
                            if now - cached_time > self.reference_verifier.cache_duration:
                                is_stale = True
                        else:
                            is_stale = True
                            
                    if cache_key not in self.verification_cache or is_stale:
                        x1, y1, x2, y2 = bbox
                        h_f, w_f = cv_frame.shape[:2]
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w_f, x2), min(h_f, y2)
                        if x2 > x1 and y2 > y1:
                            crop = cv_frame[y1:y2, x1:x2]
                            verified_class, similarity = self.reference_verifier.verify(crop, direct_class)
                            self.verification_cache[cache_key] = (verified_class, similarity, now, bbox)
                            
                            # Print precise requested log format
                            if verified_class == "analog_watch":
                                logger.info(f"[REFERENCE_VERIFY] Track={track_id} YOLO={direct_class} Result=analog_watch Score={similarity:.2f} Status=NORMAL")
                            else:
                                logger.info(f"[REFERENCE_VERIFY] Track={track_id} YOLO={direct_class} Result={verified_class} Score={similarity:.2f} Status=UNCERTAIN")
                        else:
                            self.verification_cache[cache_key] = ("unknown", 0.0, now, bbox)
                            
                    verified_class, similarity, _, _ = self.verification_cache[cache_key]
                    if verified_class == "analog_watch":
                        if isinstance(detection, dict):
                            detection["class_name"] = "analog watch"
                        else:
                            setattr(detection, "class_name", "analog watch")

                elif normalized_direct in {"book", "book_paper", "answer_book", "notebook", "paper_sheet", "answer_sheet"}:
                    bbox = self._value(detection, "bbox", (0, 0, 0, 0))
                    y_conf = float(self._value(detection, "confidence", 0.80))
                    is_cand = bool(self._value(detection, "is_candidate", False))
                    self._verify_answersheet_with_gemini(
                        track_id, direct_class, bbox, cv_frame, camera_id=camera_id,
                        yolo_conf=y_conf, is_candidate=is_cand
                    )
                    v_class, v_conf = self._get_answersheet_verification_result(track_id, direct_class, camera_id=camera_id, bbox=bbox)
                    
                    threshold = self.config.get("answer_sheet_verify", {}).get("threshold", 0.80)
                    if v_class == "answer_sheet" and v_conf >= threshold:
                        if isinstance(detection, dict):
                            detection["class_name"] = "answer_sheet"
                            detection["confirmed"] = True
                        else:
                            setattr(detection, "class_name", "answer_sheet")
                            setattr(detection, "confirmed", True)
                    elif v_class == "book":
                        if isinstance(detection, dict):
                            detection["class_name"] = "book"
                            detection["confirmed"] = True
                        else:
                            setattr(detection, "class_name", "book")
                            setattr(detection, "confirmed", True)

                elif normalized_direct in {"cell_phone", "mobile", "phone", "calculator", "scientific_calculator"}:
                    bbox = self._value(detection, "bbox", (0, 0, 0, 0))
                    calc_res = None
                    if getattr(self, "calculator_verifier", None):
                        calc_res = self.calculator_verifier.get_cached_result(camera_id, track_id, bbox)
                    if calc_res and calc_res.safe and calc_res.object_type == "SCIENTIFIC_CALCULATOR":
                        logger.info(f"🧮 [ARBITRATION] Track {track_id} = SCIENTIFIC CALCULATOR / SAFE")
                        logger.info(f"🧮 [FUSION] Track={track_id} {direct_class.upper()} -> SCIENTIFIC CALCULATOR")
                        logger.info(f"🧮 [RISK] Track={track_id} SCIENTIFIC CALCULATOR -> SAFE")
                        if isinstance(detection, dict):
                            detection["class_name"] = "scientific_calculator"
                            detection["safe"] = True
                            detection["confidence"] = calc_res.confidence
                            detection["phone_confidence"] = 0.0
                        else:
                            setattr(detection, "class_name", "scientific_calculator")
                            setattr(detection, "safe", True)
                            setattr(detection, "confidence", calc_res.confidence)
                            setattr(detection, "phone_confidence", 0.0)
                    elif calc_res and calc_res.object_type == "NOT_CALCULATOR":
                        logger.info(f"📱 [ARBITRATION] Track {track_id} = CELL PHONE / CRITICAL")
                        logger.info(f"📱 [RISK] Track={track_id} CELL PHONE -> CRITICAL")
                    elif calc_res and (calc_res.classification == "uncertain" or getattr(calc_res, "verification_status", "") == "temporarily_unavailable"):
                        logger.info(f"🧮 [CALCULATOR] Verification uncertain/unavailable (e.g. Gemini 429) for Track {track_id}. Preserving original YOLO {direct_class} as unverified.")
                        if isinstance(detection, dict):
                            detection["verification_status"] = "unverified"
                        else:
                            setattr(detection, "verification_status", "unverified")

            phone_confidence = self._phone_confidence(detection)
            sw_confidence = self._smartwatch_confidence(detection)
            movement_variance = self._movement_variance(detection)

            # Manage stable 1-second phone detection timer
            curr_time = timestamp if timestamp is not None else time.time()
            conf_threshold = 0.30
            if self.detector is not None and hasattr(self.detector, "MOBILE_CONF_MIN"):
                conf_threshold = self.detector.MOBILE_CONF_MIN
            
            phone_detected = (phone_confidence >= conf_threshold)
            if phone_detected:
                if student_id not in self.phone_session_timers:
                    self.phone_session_timers[student_id] = curr_time
                    self.phone_session_alerted[student_id] = False
                    logger.info(f"📱 Phone detection started for {student_id} at {curr_time}. Starting 1-second stable detection timer.")
                phone_elapsed = curr_time - self.phone_session_timers[student_id]
            else:
                if student_id in self.phone_session_timers:
                    logger.info(f"📱 Phone disappeared for {student_id}. Resetting timer.")
                    del self.phone_session_timers[student_id]
                if student_id in self.phone_session_alerted:
                    del self.phone_session_alerted[student_id]
                phone_elapsed = 0.0

            # Manage stable 1-second smartwatch detection timer
            sw_detected = (sw_confidence >= conf_threshold)
            if sw_detected:
                if student_id not in self.sw_session_timers:
                    self.sw_session_timers[student_id] = curr_time
                    self.sw_session_alerted[student_id] = False
                    logger.info(f"⌚ Smartwatch detection started for {student_id} at {curr_time}. Starting 1-second stable detection timer.")
                sw_elapsed = curr_time - self.sw_session_timers[student_id]
            else:
                if student_id in self.sw_session_timers:
                    logger.info(f"⌚ Smartwatch disappeared for {student_id}. Resetting timer.")
                    del self.sw_session_timers[student_id]
                if student_id in self.sw_session_alerted:
                    del self.sw_session_alerted[student_id]
                sw_elapsed = 0.0

            # Only expose phone detection to AI analysis if stable for >= 1 second
            active_phone_score = phone_confidence if (phone_detected and phone_elapsed >= 1.0) else 0.0

            # Structured logs for computer vision stages
            logger.info(f"👤 Face Mesh [{camera_id}] - Face Detected: {face_results.get('face_detected')}, Head Pose: Yaw={(face_results.get('yaw') or 0.0):.1f} Pitch={(face_results.get('pitch') or 0.0):.1f}")
            logger.info(f"👁️ Iris Tracking [{camera_id}] - Iris Detected: {gaze_results.get('iris_detected')}, Gaze: {gaze_results.get('direction')}")
            logger.info(f"🦴 Pose [{camera_id}] - Skeleton Detected: {skeleton_results.detected}, Anomaly Score: {skeleton_results.anomaly_score:.1f}")

            # 7. Prepare fusion input (multi-modal with track ID)
            det_bbox = self._value(detection, "bbox")
            fusion_input = FusionInput(
                gaze_left_score=gaze_results.get("confidence", 0.0) if gaze_results.get("direction") == "LEFT" else 0.0,
                gaze_right_score=gaze_results.get("confidence", 0.0) if gaze_results.get("direction") == "RIGHT" else 0.0,
                gaze_down_score=gaze_results.get("confidence", 0.0) if gaze_results.get("direction") == "DOWN" else 0.0,
                head_yaw_degrees=face_results.get("yaw") or 0.0,
                head_pitch_degrees=face_results.get("pitch") or 0.0,
                head_roll_degrees=face_results.get("roll") or 0.0,
                leaning_score=skeleton_results.leaning_severity if skeleton_results.detected else 0.0,
                wrist_below_desk_score=skeleton_results.wrist_movement_severity if skeleton_results.detected else 0.0,
                arm_extension_score=skeleton_results.arm_movement_severity if skeleton_results.detected else 0.0,
                shoulder_movement_score=skeleton_results.shoulder_angle_degrees / 45.0 if skeleton_results.detected else 0.0,
                phone_visible_score=active_phone_score,
                movement_variance=movement_variance,
                timestamp=curr_time,
                track_id=track_id,
                bbox=tuple(map(int, det_bbox)) if det_bbox and len(det_bbox) >= 4 else None
            )
            
            # 8. Fuse all modalities using fusion engine (with temporal tracking)
            fusion_output = self.fusion_engine.fuse(fusion_input, track_id=track_id)
            logger.info(f"📊 Behaviour [{camera_id}] - Student ID {student_id} Primary: {fusion_output.primary_behaviors}")

            # 9. Calculate dynamic risk score using RiskCalculator
            risk_res = self.risk_calculator.calculate(
                phone_score=active_phone_score,
                gaze_score=gaze_results.get("confidence", 0.0) if gaze_results.get("direction") in {"LEFT", "RIGHT", "DOWN"} else 0.0,
                pose_score=skeleton_results.anomaly_score / 100.0 if skeleton_results.detected else 0.0,
                behavior_score=fusion_output.overall_risk_score / 100.0,
                history_score=0.0,
                student_id=student_id
            )
            risk_score = risk_res["risk_score"]
            risk_level = risk_res["level"]
            logger.info(f"📈 Risk Engine [{camera_id}] - Student ID {student_id} Score: {risk_score:.1f} ({risk_level})")

            # 10. Run DecisionAgent
            decision_input = {
                track_id: {
                    "score": risk_score,
                    "events": fusion_output.primary_behaviors or ["suspicious_behavior"],
                    "situation": fusion_output.brief_reason
                }
            }
            decisions = self.decision_agent.decide(decision_input)
            decision = decisions[track_id]
            
            # 🚨 ANSWER BOOK OVERRIDE RULE
            # Check if student has a CONFIRMED safe object (confirmed book or verified answer sheet/calculator).
            # Synthetic candidates (is_candidate=True) MUST NOT suppress risk.
            # Safe objects must NOT suppress independent behavioral misconduct signals (gaze, head turns, leaning, interaction).
            has_confirmed_safe_object = False
            has_suspicious_device = False
            
            student_objects = self._value(detection, "objects_detected", []) or []
            for obj in student_objects:
                obj_class = obj.get("class_name", "")
                is_cand = bool(obj.get("is_candidate", False))
                is_safe = bool(obj.get("safe", False))
                is_confirmed = bool(obj.get("confirmed", False))
                obj_conf = float(obj.get("confidence", 0.0))

                # 1. YOLO_CONFIRMED_BOOK: Real YOLO detection >= NORMAL_BOOK_CONFIDENCE (not synthetic candidate)
                # 2. VERIFIED_ANSWER_SHEET: Verified by semantic layer (safe=True or confirmed=True)
                # 3. VERIFIED_CALCULATOR: Safe scientific calculator
                if is_safe or (is_confirmed and not is_cand):
                    has_confirmed_safe_object = True
                elif obj_class in {"book", "answer book", "notebook", "paper sheet"} and not is_cand and obj_conf >= 0.30:
                    has_confirmed_safe_object = True
                elif obj_class in {"scientific_calculator", "calculator"} and is_safe:
                    has_confirmed_safe_object = True

                if obj_class in {"cell phone", "mobile", "phone", "smart watch", "earphones", "earbuds", "bluetooth device", "tablet"} and not is_safe and obj_class not in {"scientific_calculator", "calculator"}:
                    has_suspicious_device = True

            direct_class_curr = self._value(detection, "class_name", "")
            if (direct_class_curr in {"scientific_calculator", "calculator"} and self._value(detection, "safe", False)) or (direct_class_curr == "answer_sheet" and self._value(detection, "safe", False)):
                has_confirmed_safe_object = True
            if direct_class_curr in {"cell phone", "mobile", "phone", "smart watch"} and not self._value(detection, "safe", False) and direct_class_curr not in {"scientific_calculator", "calculator"}:
                has_suspicious_device = True
            
            if has_confirmed_safe_object and not has_suspicious_device:
                # Check for active behavioral misconduct signals from MediaPipe / fusion / gaze / pose
                behavioral_score = fusion_output.overall_risk_score
                primary_behaviors = getattr(fusion_output, "primary_behaviors", []) or []
                has_behavioral_signals = (
                    behavioral_score >= 20.0
                    or any(b in primary_behaviors for b in [
                        "gaze_sideways", "repeated_gaze_deviation", "excessive_turning",
                        "repeated_head_turning", "leaning", "repeated_leaning", "paper_sharing",
                        "student_interaction", "wrist_below_desk", "gaze_downward"
                    ])
                )
                if not has_behavioral_signals:
                    logger.info(f"📚 Confirmed safe object on desk for Student {student_id} without suspicious devices or behavioral signals. Suppressing false object alerts.")
                    decision.should_alert = False
                    risk_score = min(risk_score, 15.0)
                    risk_level = "LOW"
                    risk_res["risk_score"] = risk_score
                    risk_res["level"] = "LOW"
                    risk_res["components"] = {k: min(v, 15.0) for k, v in risk_res.get("components", {}).items()}
                else:
                    logger.info(f"⚠️ Safe object on desk for Student {student_id}, but independent behavioral signals active ({primary_behaviors}). Preserving behavioral risk score={risk_score:.1f}.")

            # Apply Mobile Phone immediate alert / override / suppression logic
            if phone_detected and phone_elapsed >= 1.0:
                from backend.agents.decision_agent import AlertLevel
                if not self.phone_session_alerted[student_id]:
                    # First time stable detection >= 1s: Force immediate alert
                    self.phone_session_alerted[student_id] = True
                    
                    # Force Risk to CRITICAL for mobile phone detection
                    risk_score = max(risk_score, 90.0)
                    risk_level = "CRITICAL"
                    risk_res["risk_score"] = risk_score
                    risk_res["level"] = risk_level
                    
                    logger.info(f"🚨 Stable phone detection for >= 1 second on {student_id}. Forcing immediate alert.")
                    if "phone_detected" not in fusion_output.primary_behaviors:
                        fusion_output.primary_behaviors.append("phone_detected")
                    if not fusion_output.brief_reason or "phone" not in fusion_output.brief_reason.lower():
                        fusion_output.brief_reason = "📱 Mobile phone detected in vicinity - HIGH RISK"
                    
                    decision.should_alert = True
                    decision.risk_score = risk_score
                    decision.level = getattr(AlertLevel, risk_level, AlertLevel.HIGH)
                else:
                    # Already alerted in this session. Suppress duplicate alert unless other signs trigger it.
                    # Recalculate risk score without phone
                    risk_res_no_phone = self.risk_calculator.calculate(
                        phone_score=0.0,
                        gaze_score=gaze_results.get("confidence", 0.0) if gaze_results.get("direction") in {"LEFT", "RIGHT", "DOWN"} else 0.0,
                        pose_score=skeleton_results.anomaly_score / 100.0 if skeleton_results.detected else 0.0,
                        behavior_score=fusion_output.overall_risk_score / 100.0,
                        history_score=0.0,
                        student_id=student_id
                    )
                    score_no_phone = risk_res_no_phone["risk_score"]
                    if score_no_phone < 75.0:
                        # Suppress duplicate phone alert
                        decision.should_alert = False

            # Apply Smartwatch immediate alert / override / suppression logic
            if sw_detected and sw_elapsed >= 1.0:
                from backend.agents.decision_agent import AlertLevel
                if not self.sw_session_alerted[student_id]:
                    # First time stable detection >= 1s: Force immediate alert
                    self.sw_session_alerted[student_id] = True
                    
                    # Force Risk to at least HIGH
                    risk_score = max(risk_score, 75.0)
                    risk_level = "HIGH" if risk_score < 90.0 else "CRITICAL"
                    risk_res["risk_score"] = risk_score
                    risk_res["level"] = risk_level
                    
                    logger.info(f"🚨 Stable smartwatch detection for >= 1 second on {student_id}. Forcing immediate alert.")
                    if "smartwatch_detected" not in fusion_output.primary_behaviors:
                        fusion_output.primary_behaviors.append("smartwatch_detected")
                    fusion_output.brief_reason = "Smartwatch Detected"
                    
                    decision.should_alert = True
                    decision.risk_score = risk_score
                    decision.level = getattr(AlertLevel, risk_level, AlertLevel.HIGH)
                else:
                    # Already alerted in this session. Suppress duplicate alert unless other signs trigger it.
                    # Recalculate risk score without smartwatch
                    risk_res_no_sw = self.risk_calculator.calculate(
                        phone_score=0.0,
                        gaze_score=gaze_results.get("confidence", 0.0) if gaze_results.get("direction") in {"LEFT", "RIGHT", "DOWN"} else 0.0,
                        pose_score=skeleton_results.anomaly_score / 100.0 if skeleton_results.detected else 0.0,
                        behavior_score=fusion_output.overall_risk_score / 100.0,
                        history_score=0.0,
                        student_id=student_id
                    )
                    score_no_sw = risk_res_no_sw["risk_score"]
                    if score_no_sw < 75.0:
                        # Suppress duplicate smartwatch alert
                        decision.should_alert = False

            logger.info(f"⚖️ Decision [{camera_id}] - Student ID {student_id} Should Alert: {decision.should_alert}")

            # 11. Execute LangGraph workflow nodes
            lg_state: SurveillanceState = {
                "camera_id": camera_id,
                "frame_id": str(int(timestamp or time.time())),
                "student_id": student_id,
                "tracking_id": track_id,
                "seat": student_id,
                "raw_detections": [Detection.from_item(d) for d in yolo_results] if yolo_results else [],
                "detections": [Detection.from_item(d).to_dict() for d in yolo_results] if yolo_results else [],
                "tracks": [{"student_id": student_id, "tracking_id": track_id, "bbox": self._value(detection, "bbox"), "confidence": self._value(detection, "confidence")}],
                "face_analysis": face_results,
                "gaze_analysis": gaze_results,
                "skeleton_analysis": skeleton_results.__dict__ if skeleton_results.detected else {},
                "behaviors": [{"behavior": b.upper(), "confidence": fusion_output.overall_confidence} for b in fusion_output.primary_behaviors],
                "risk": risk_res,
                "evidence_threshold": self.config.get("alert_threshold", 60),
                "session_id": "LIVE",
            }
            
            # Store student results immediately so detection state is never lost
            student_data = {
                "track_id": track_id,
                "student_id": student_id,
                "bbox": self._value(detection, "bbox"),
                "confidence": self._value(detection, "confidence", 0.0),
                "risk_score": risk_score,
                "risk_level": risk_level.lower(),
                "behaviors": fusion_output.primary_behaviors,
                "component_scores": risk_res["components"],
                "face": face_results,
                "gaze": gaze_results,
            }
            frame_results["students"][student_id] = student_data
            self.students_tracked[track_id] = student_data

            try:
                if hasattr(self.workflow, "ainvoke"):
                    lg_state = await asyncio.wait_for(self.workflow.ainvoke(lg_state), timeout=3.0)
                elif hasattr(self.workflow, "run_async"):
                    lg_state = await asyncio.wait_for(self.workflow.run_async(lg_state), timeout=3.0)
                else:
                    lg_state = await asyncio.wait_for(asyncio.to_thread(self.workflow.invoke, lg_state), timeout=3.0)
                logger.info(f"🕸️ LangGraph [{camera_id}] - Workflow Node execution complete")
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ LangGraph workflow timed out for {student_id}; continuing pipeline")
            except Exception as e:
                logger.error(f"❌ LangGraph workflow execution failed: {e}")
            
            # 12. Check if alert should be triggered
            if decision.should_alert:
                alert_id = str(uuid.uuid4())
                # Execute CrewAI kickoff
                crew_inputs = {
                    "student_id": student_id,
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "behaviors": fusion_output.primary_behaviors,
                    "gaze": gaze_results.get("direction"),
                    "pose": face_results.get("head_pose"),
                    "camera_id": camera_id,
                }
                crew_result = self.crew.kickoff(inputs=crew_inputs)
                logger.info(f"👥 CrewAI [{camera_id}] - Kickoff Result status: {crew_result.get('status')}")
                crew_decision = crew_result.get("result", "Escalate to Invigilator")

                # Retrieve Gemini API explanation
                gemini_explanation = None
                if self.gemini:
                    try:
                        explanation_data = await self.gemini.analyze_alert(crew_inputs)
                        gemini_explanation = explanation_data.get("ai_explanation")
                    except Exception as e:
                        logger.error(f"Failed to query Gemini API: {e}")
                
                # Fallback to local reasoning
                if not gemini_explanation:
                    try:
                        from backend.agents.gemini_agent import GeminiReasoningEngine
                        fallback_gemini = GeminiReasoningEngine()
                        explanation_data = await fallback_gemini.analyze_alert(crew_inputs)
                        gemini_explanation = explanation_data.get("ai_explanation")
                    except Exception as e:
                        logger.error(f"Fallback reasoning failed: {e}")

                logger.info(f"🤖 Gemini [{camera_id}] - Explanation Generated: {gemini_explanation is not None}")

                # Capture evidence
                evidence_record = None
                try:
                    clip_frames = list(self.frame_history.get(camera_id, [])) if hasattr(self, "frame_history") else []
                    evidence_record = self.evidence_agent.capture(
                        frame=cv_frame,
                        annotated_frame=frame_results["frame_annotated"],
                        student_id=student_id,
                        event=fusion_output.brief_reason,
                        camera_id=camera_id,
                        tracking_id=track_id,
                        confidence=self._value(detection, "confidence", 0.0),
                        risk_score=risk_score,
                        clip_frames=clip_frames,
                        session_id=self.config.get("session_id", "LIVE"),
                        metadata={
                            "behaviors": fusion_output.primary_behaviors,
                            "risk_level": risk_level,
                            "gemini_explanation": gemini_explanation,
                            "crew_decision": crew_decision
                        },
                        alert_id=alert_id
                    )
                    from backend.database.store import store
                    store.upsert("evidence", "evidence_id", evidence_record)
                except Exception as e:
                    logger.error(f"Evidence capture failed: {e}")
                
                logger.info(f"Evidence [{camera_id}] - Student ID {student_id} Captured: {evidence_record is not None}")

                # Generate PDF report for this specific alert
                report_data = None
                try:
                    report_data = self.report_agent.generate_pdf(
                        session_id=self.config.get("session_id", "LIVE"),
                        events=[evidence_record] if evidence_record else [],
                        gemini_summary={
                            "pdf_report_summary": gemini_explanation,
                            "primary_assessment": fusion_output.brief_reason,
                            "recommendation": "Immediate invigilator review.",
                            "crew_decision": crew_decision
                        },
                        exam={
                            "exam_name": "Online Proctored Exam",
                            "subject": "Surveillance Session"
                        }
                    )
                    from backend.database.store import store
                    store.upsert("reports", "report_id", {
                        **report_data,
                        "session_id": self.config.get("session_id", "LIVE"),
                        "email_status": "pending_delivery",
                        "gemini_summary": {
                            "pdf_report_summary": gemini_explanation,
                            "primary_assessment": fusion_output.brief_reason,
                            "recommendation": "Immediate invigilator review.",
                            "crew_decision": crew_decision
                        }
                    })
                    logger.info(f"Report Agent [{camera_id}] - PDF Report Generated: {report_data['pdf_path']}")
                except Exception as e:
                    logger.error(f"Failed to generate PDF report: {e}")

                # Trigger automated email delivery asynchronously in the background
                try:
                    import os
                    from email_sender import send_email_with_retries
                    recipient = os.getenv("RECIPIENT_EMAIL") or os.getenv("EMAIL_USER")
                    
                    send_email_with_retries(
                        recipient_email=recipient,
                        pdf_path=report_data["pdf_path"] if report_data else "",
                        student_id=student_id,
                        camera_id=camera_id,
                        behaviour=fusion_output.brief_reason,
                        risk_score=risk_score,
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        gemini_explanation=gemini_explanation,
                        crew_decision=crew_decision,
                        evidence_image=evidence_record.get("annotated_frame_path") if evidence_record else None,
                        evidence_video=evidence_record.get("evidence_video_path") if evidence_record else None,
                        report_id=report_data.get("report_id") if report_data else None,
                        behaviors=fusion_output.primary_behaviors,
                        confidence=self._value(detection, "confidence", 0.90)
                    )
                    logger.info(f"Email Sender [{camera_id}] - Email background task enqueued for student {student_id}")
                except Exception as e:
                    logger.error(f"Failed to enqueue email sending task: {e}")

                # Cleanly map behaviors list to standard BehaviorType enum strings
                mapped_behaviors = []
                for b in fusion_output.primary_behaviors:
                    mapped_behaviors.append({
                        "event_id": f"EV-{uuid.uuid4().hex[:6].upper()}",
                        "student_id": student_id,
                        "behavior_type": self._map_behavior_to_enum(b),
                        "timestamp": datetime.now().isoformat(),
                        "duration_ms": 0.0,
                        "confidence": fusion_output.overall_confidence
                    })

                alert = {
                    "alert_id": alert_id,
                    "student_id": student_id,
                    "camera_id": camera_id,
                    "tracking_id": track_id,
                    "session_id": self.config.get("session_id", "LIVE"),
                    "timestamp": datetime.now().isoformat(),
                    "severity": risk_level.lower(),
                    "risk_score": risk_score,
                    "reason": fusion_output.brief_reason,
                    "behaviors": mapped_behaviors,
                    "repetition_summary": getattr(fusion_output, "episodes_summary", {}),
                    "evidence_captured": evidence_record is not None,
                    "evidence_id": evidence_record.get("evidence_id") if evidence_record else None,
                    "image_path": evidence_record.get("image_path") if evidence_record else None,
                    "annotated_image_path": evidence_record.get("annotated_image_path") if evidence_record else None,
                    "original_image_path": evidence_record.get("original_image_path") if evidence_record else None,
                    "gemini_explanation": gemini_explanation,
                    "pdf_path": report_data["pdf_path"] if report_data else None,
                    "crew_decision": crew_decision
                }
                frame_results["alerts"].append(alert)
                self.recent_alerts.append(alert)
                
                # Database sync
                from backend.database.store import store
                store.upsert("alerts", "alert_id", alert)
                
                if self.batch_processor:
                    await self.batch_processor.queue_alert({
                        "alert_id": alert["alert_id"],
                        "student_id": student_id,
                        "behaviors": fusion_output.primary_behaviors,
                        "overall_risk": risk_score,
                        "gaze_score": risk_res["components"].get("gaze_score", 0.0),
                        "pose_score": risk_res["components"].get("pose_score", 0.0),
                        "phone_score": risk_res["components"].get("phone_score", 0.0),
                        "timestamp": datetime.now().isoformat()
                    })
        
        # 8. Push frame to WebRTC server (handled immediately by the capture thread frame sink)
        # self.webrtc_server.push_frame(
        #     camera_id,
        #     frame_results["frame_annotated"],
        #     float(timestamp or time.time())
        # )

        # Collect active verified calculators for this frame
        if getattr(self, "calculator_verifier", None) and getattr(self, "calculator_config", None):
            for key, c_res in list(self.calculator_verifier.cache.items()):
                if isinstance(key, tuple) and key[0] == camera_id:
                    if c_res.safe and c_res.object_type == "SCIENTIFIC_CALCULATOR":
                        is_active_track = c_res.track_id is not None and c_res.track_id in active_track_ids
                        is_fresh = (time.time() - c_res.timestamp) < self.calculator_config.cache_duration
                        if is_active_track or is_fresh:
                            calc_dict = {
                                "track_id": c_res.track_id,
                                "bbox": c_res.bbox,
                                "classification": c_res.classification,
                                "object_type": c_res.object_type,
                                "confidence": c_res.confidence,
                                "safe": c_res.safe,
                                "reason": c_res.reason,
                            }
                            if not any(
                                self.calculator_detector._compute_iou(c_res.bbox, c["bbox"]) > 0.40
                                for c in frame_results["calculators"]
                            ):
                                frame_results["calculators"].append(calc_dict)

        if self.result_sink is not None:
            sink_result = self.result_sink(frame_results)
            if asyncio.iscoroutine(sink_result):
                await sink_result
        
        return frame_results
    
    def _verify_smartwatch_with_gemini(self, track_id: int, obj_class: str, bbox: tuple, cv_frame: np.ndarray):
        """
        Trigger or retrieve background Gemini Vision verification for a smartwatch candidate.
        """
        cache_key = (track_id, obj_class)
        now = time.time()
        
        # Check staleness
        is_stale = False
        if cache_key in self.gemini_vision_cache:
            cached_val = self.gemini_vision_cache[cache_key]
            if len(cached_val) == 4:
                v_class, v_conf, cached_time, cached_bbox = cached_val
                if v_class != "pending":
                    # Check area change
                    x1_c, y1_c, x2_c, y2_c = cached_bbox
                    x1, y1, x2, y2 = bbox
                    area_cached = max(1, (x2_c - x1_c) * (y2_c - y1_c))
                    area_current = max(1, (x2 - x1) * (y2 - y1))
                    area_ratio = area_current / area_cached
                    if area_ratio < 0.5 or area_ratio > 1.5:
                        is_stale = True
                    if now - cached_time > self.smartwatch_verifier.cache_duration:
                        is_stale = True
            else:
                is_stale = True
        
        if cache_key not in self.gemini_vision_cache or is_stale:
            # Crop and trigger background task
            x1, y1, x2, y2 = bbox
            h_f, w_f = cv_frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_f, x2), min(h_f, y2)
            
            if x2 > x1 and y2 > y1:
                crop = cv_frame[y1:y2, x1:x2].copy()
                
                # Mark as pending
                self.gemini_vision_cache[cache_key] = ("pending", 0.0, now, bbox)
                
                # Define callback/async task
                async def run_verification():
                    try:
                        logger.info(f"⏳ [SMARTWATCH VISION] Starting Gemini Vision verification for Track ID {track_id}...")
                        result = await self.smartwatch_verifier.verify_crop(crop)
                        v_class = result.get("classification", "uncertain")
                        v_conf = result.get("confidence", 0.0)
                        v_reason = result.get("reason", "")
                        
                        status = "UNCERTAIN"
                        if v_class == "smartwatch" and v_conf >= self.smartwatch_verifier.threshold:
                            status = "CONFIRMED"
                        elif v_class == "not_smartwatch" and v_conf >= self.smartwatch_verifier.threshold:
                            status = "REJECTED"
                        
                        # Print precise requested log format
                        print(
                            f"[SMARTWATCH VISION] "
                            f"Track ID: {track_id} "
                            f"YOLO Class: {obj_class} "
                            f"Gemini Result: {v_class} "
                            f"Confidence: {v_conf:.2f} "
                            f"Status: {status}"
                        )
                        logger.info(
                            f"[SMARTWATCH VISION] Track={track_id} YOLO={obj_class} Result={v_class} Score={v_conf:.2f} Status={status} Reason={v_reason}"
                        )
                        
                        # Update cache with actual result
                        self.gemini_vision_cache[cache_key] = (v_class, v_conf, time.time(), bbox)
                    except Exception as e:
                        logger.error(f"[SMARTWATCH VISION] Background task error for Track ID {track_id}: {e}")
                        self.gemini_vision_cache[cache_key] = ("uncertain", 0.0, time.time(), bbox)
                
                # Spawn background task
                asyncio.create_task(run_verification())
            else:
                self.gemini_vision_cache[cache_key] = ("uncertain", 0.0, now, bbox)

    def _get_gemini_verification_result(self, track_id: int, obj_class: str) -> tuple[str, float]:
        """
        Get cached Gemini Vision verification results.
        Returns: (verified_class_name, confidence)
        """
        cache_key = (track_id, obj_class)
        if cache_key in self.gemini_vision_cache:
            v_class, v_conf, _, _ = self.gemini_vision_cache[cache_key]
            return v_class, v_conf
        return "pending", 0.0

    def _verify_answersheet_with_gemini(
        self,
        track_id: Optional[int],
        obj_class: str,
        bbox: tuple,
        cv_frame: np.ndarray,
        camera_id: str = "cam_0",
        yolo_conf: float = 0.80,
        is_candidate: bool = False
    ):
        """
        Lightweight Semantic Verification Layer for Book vs Answer Sheet detection.
        Performs very fast OpenCV multi-signal verification on the crop (near-white HSV,
        color diversity/Hasler colorfulness, geometry, ruled lines).
        Applies temporal confirmation over consecutive frames to prevent flicker.
        Caches confirmed result by Track ID and reuses it without repeating verification every frame.
        """
        now = time.time()
        max_cache_age = getattr(self.answersheet_verifier, "cache_duration", 10.0)

        # Cache keys: primary (camera_id, track_id) when track_id is valid, plus backward-compat keys
        has_valid_track = (track_id is not None and track_id > 0)
        cache_key = (camera_id, track_id) if has_valid_track else (camera_id, "spatial", bbox)
        compat_key = (track_id, obj_class) if has_valid_track else None
        cached_val = self.answersheet_vision_cache.get(cache_key) or (
            self.answersheet_vision_cache.get(compat_key) if compat_key else None
        )
        # Check existing cache: if already confirmed by temporal history and not stale, reuse cached result directly
        is_confirmed = (cache_key in self._book_confirmed_labels and self._book_confirmed_labels[cache_key] in {"answer_sheet", "book"})
        if is_confirmed and cached_val and len(cached_val) == 4:
            v_class, v_conf, cached_time, cached_bbox = cached_val
            if now - cached_time <= max_cache_age:
                if cached_bbox:
                    cx1, cy1, cx2, cy2 = cached_bbox
                    x1, y1, x2, y2 = bbox
                    inter_w = max(0, min(x2, cx2) - max(x1, cx1))
                    inter_h = max(0, min(y2, cy2) - max(y1, cy1))
                    inter_area = inter_w * inter_h
                    area1 = max(1, (x2 - x1) * (y2 - y1))
                    area2 = max(1, (cx2 - cx1) * (cy2 - cy1))
                    iou = inter_area / float(area1 + area2 - inter_area)
                    if iou > 0.30:
                        return
                else:
                    return

        # Perform crop validation
        if cv_frame is None or not isinstance(cv_frame, np.ndarray) or cv_frame.size == 0:
            self.answersheet_vision_cache[cache_key] = ("book", 0.80, now, bbox)
            if compat_key:
                self.answersheet_vision_cache[compat_key] = ("book", 0.80, now, bbox)
            return

        x1, y1, x2, y2 = bbox
        h_f, w_f = cv_frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_f, x2), min(h_f, y2)

        if x2 <= x1 or y2 <= y1 or (x2 - x1) < 20 or (y2 - y1) < 20:
            # Invalid crop -> fail-safe: keep BOOK
            self.answersheet_vision_cache[cache_key] = ("book", 0.80, now, bbox)
            if compat_key:
                self.answersheet_vision_cache[compat_key] = ("book", 0.80, now, bbox)
            return

        crop = cv_frame[y1:y2, x1:x2].copy()

        try:
            # Multi-signal OpenCV Semantic Verification (< 2 ms)
            res_class, v_conf, metrics = self.answersheet_verifier.verify_candidate_semantics(
                crop, yolo_conf=yolo_conf
            )

            # Temporal confirmation tracking
            history = self._book_temporal_history.setdefault(cache_key, [])
            history.append(res_class)
            if len(history) > 10:
                history.pop(0)

            # Enforce temporal stabilization: require repeated consecutive evidence
            # before changing BOOK -> ANSWER_SHEET or ANSWER_SHEET -> BOOK.
            # One weak or anomalous frame must NOT change the classification.
            req_frames = max(3, getattr(self, "temporal_confirmation_frames", 3))
            current_label = self._book_confirmed_labels.get(cache_key)

            if current_label is None:
                # Initial detection: require req_frames consecutive frames
                if len(history) >= req_frames and all(h == history[-1] for h in history[-req_frames:]):
                    confirmed_label = history[-1]
                    self._book_confirmed_labels[cache_key] = confirmed_label
                else:
                    confirmed_label = "pending"
            else:
                # Transitioning between classes: require at least req_frames consecutive frames
                if res_class != current_label:
                    if len(history) >= req_frames and all(h == res_class for h in history[-req_frames:]):
                        confirmed_label = res_class
                        self._book_confirmed_labels[cache_key] = confirmed_label
                    else:
                        confirmed_label = current_label
                else:
                    confirmed_label = current_label

            geom_ok = metrics.get("geometry_pass", False)
            geom_str = "PASS" if geom_ok else "FAIL"
            white_ratio = metrics.get("white_ratio", 0.0)
            color_ratio = metrics.get("color_ratio", 0.0)
            line_score = metrics.get("line_score", 0.0)

            res_str = "ANSWER_SHEET" if confirmed_label == "answer_sheet" else (
                "BOOK" if confirmed_label == "book" else "PENDING"
            )

            # Concise debug logging: only on new candidate, confirmed label transition, or semantic change
            last_info = self._book_last_logged_info.get(cache_key)
            is_new = (last_info is None)
            label_transition = bool(last_info and last_info.get("confirmed_label") != confirmed_label)
            semantic_change = bool(last_info and last_info.get("res_class") != res_class)

            if is_new or label_transition or semantic_change:
                log_line = (
                    f"[BOOK_VERIFY] track={track_id} yolo_conf={yolo_conf:.2f} "
                    f"white_ratio={white_ratio:.2f} color_ratio={color_ratio:.2f} "
                    f"geometry={geom_str} line_score={line_score:.2f} result={res_str}"
                )
                print(log_line)
                logger.info(log_line)

                # Keep legacy [ANSWER_SHEET] format for backward compatibility
                print(
                    f"\n[ANSWER_SHEET]\n"
                    f"Track: {track_id}\n"
                    f"White Ratio: {white_ratio:.2f}\n"
                    f"Geometry: {geom_str}\n"
                    f"Result: {res_str}\n"
                )
                logger.info(
                    f"[ANSWER_SHEET] Track: {track_id} White Ratio: {white_ratio:.2f} Geometry: {geom_str} Result: {res_str}"
                )
                self._book_last_logged_info[cache_key] = {
                    "confirmed_label": confirmed_label,
                    "res_class": res_class
                }

            # Store verified or confirmed result in cache
            store_class = confirmed_label if confirmed_label in {"answer_sheet", "book"} else ("pending" if is_candidate else res_class)
            store_conf = v_conf if confirmed_label in {"answer_sheet", "book"} else (0.0 if store_class == "pending" else v_conf)

            self.answersheet_vision_cache[cache_key] = (store_class, store_conf, now, bbox)
            if compat_key:
                self.answersheet_vision_cache[compat_key] = (store_class, store_conf, now, bbox)
                if store_class == "answer_sheet":
                    self.answersheet_vision_cache[(track_id, "answer_sheet")] = (store_class, store_conf, now, bbox)
            self.answersheet_vision_cache[(camera_id, "spatial", bbox)] = (store_class, store_conf, now, bbox)

        except Exception as e:
            # Fail-safe: never crash surveillance
            logger.error(f"[BOOK_VERIFY] Semantic verification error for Track {track_id}: {e}")
            fallback_class = self._book_confirmed_labels.get(cache_key, "book")
            self.answersheet_vision_cache[cache_key] = (fallback_class, 0.80, now, bbox)
            if compat_key:
                self.answersheet_vision_cache[compat_key] = (fallback_class, 0.80, now, bbox)

    _verify_answersheet_crop = _verify_answersheet_with_gemini

    def _run_answersheet_verification_worker(
        self,
        cache_key: Any,
        compat_key: Any,
        track_id: Optional[int],
        crop: np.ndarray,
        bbox: tuple,
        camera_id: str,
        t0: float,
        t1: float,
    ):
        """Dedicated background worker executing Gemini Vision answer sheet verification synchronously."""
        t2 = time.time()  # Gemini request started timestamp
        h_crop, w_crop = crop.shape[:2]
        orientation = "portrait" if h_crop >= w_crop else "landscape"
        try:
            # Fast supporting checks
            geom_ok, aspect_ratio, geom_reason = self.answersheet_verifier.verify_geometry(crop)
            white_ok, white_ratio, white_reason = self.answersheet_verifier.verify_whiteness(crop)
            lines_ok, lines_count, lines_reason = self.answersheet_verifier.verify_ruled_lines(crop)

            # Direct synchronous Gemini call (runs in dedicated background thread)
            result = self.answersheet_verifier.verify_crop_sync(crop)
            t3 = time.time()  # Gemini response received timestamp

            v_class = result.get("classification", "uncertain")
            v_conf = float(result.get("confidence", 0.0))
            v_reason = result.get("reason", "")

            t4 = time.time()  # Result applied timestamp

            # Store in cache
            self.answersheet_vision_cache[cache_key] = (v_class, v_conf, t4, bbox)
            if compat_key:
                self.answersheet_vision_cache[compat_key] = (v_class, v_conf, t4, bbox)
                self.answersheet_vision_cache[(track_id, "answer_sheet")] = (v_class, v_conf, t4, bbox)
            self.answersheet_vision_cache[(camera_id, "spatial", bbox)] = (v_class, v_conf, t4, bbox)

            # Precise latency metrics
            cand_to_verify_ms = max(0.0, (t1 - t0) * 1000.0)
            verify_to_gemini_ms = max(0.0, (t3 - t1) * 1000.0)
            applied_ms = max(0.0, (t4 - t3) * 1000.0)
            total_ms = max(0.0, (t4 - t0) * 1000.0)

            t0_dt = datetime.fromtimestamp(t0).strftime("%H:%M:%S.%f")[:-3]
            t1_dt = datetime.fromtimestamp(t1).strftime("%H:%M:%S.%f")[:-3]
            t3_dt = datetime.fromtimestamp(t3).strftime("%H:%M:%S.%f")[:-3]

            print(
                f"\n[ANSWER_SHEET]\n"
                f"BOOK detected: {t0_dt}\n\n"
                f"[ANSWER_SHEET]\n"
                f"Verification started: {t1_dt}\n\n"
                f"[ANSWER_SHEET]\n"
                f"Gemini response: {t3_dt}\n\n"
                f"[ANSWER_SHEET]\n"
                f"Result: {v_class} {v_conf:.2f}\n\n"
                f"Total: {total_ms:.0f} ms\n"
            )
            logger.info(
                f"[ANSWER_SHEET] BOOK DETECTED -> VERIFY START: {cand_to_verify_ms:.0f}ms | "
                f"VERIFY START -> GEMINI RESPONSE: {verify_to_gemini_ms:.0f}ms | "
                f"GEMINI RESPONSE -> RESULT APPLIED: {applied_ms:.0f}ms | "
                f"TOTAL VERIFICATION LATENCY: {total_ms:.0f}ms | Cam={camera_id} Track={track_id} Orientation={orientation}"
            )
        except Exception as e:
            logger.error(f"[ANSWER_SHEET] Error in background verification: {e}")
            self.answersheet_vision_cache[cache_key] = ("uncertain", 0.0, time.time(), bbox)
            if compat_key:
                self.answersheet_vision_cache[compat_key] = ("uncertain", 0.0, time.time(), bbox)
        finally:
            self._answersheet_in_flight.discard(cache_key)

    def _get_answersheet_verification_result(
        self,
        track_id: Optional[int],
        obj_class: str = "book",
        camera_id: str = "cam_0",
        bbox: Optional[tuple] = None
    ) -> tuple[str, float]:
        """Retrieve verified status from cache for a track and object class, supporting camera_id and spatial lookup."""
        now = time.time()
        max_age = getattr(self.answersheet_verifier, "cache_duration", 10.0)

        # 1. Check (camera_id, track_id)
        if track_id is not None and track_id > 0:
            key1 = (camera_id, track_id)
            if key1 in self.answersheet_vision_cache:
                v_class, v_conf, cached_time, _ = self.answersheet_vision_cache[key1]
                if now - cached_time <= max_age:
                    return v_class, v_conf

            # 2. Check (track_id, obj_class) for backward compatibility
            key2 = (track_id, obj_class)
            if key2 in self.answersheet_vision_cache:
                v_class, v_conf, cached_time, _ = self.answersheet_vision_cache[key2]
                if now - cached_time <= max_age:
                    return v_class, v_conf

            # 3. Check (track_id, "answer_sheet")
            key3 = (track_id, "answer_sheet")
            if key3 in self.answersheet_vision_cache:
                v_class, v_conf, cached_time, _ = self.answersheet_vision_cache[key3]
                if now - cached_time <= max_age:
                    return v_class, v_conf

        # 4. Spatial bounding-box matching within the same camera
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            area1 = max(1, (x2 - x1) * (y2 - y1))
            for k, val in list(self.answersheet_vision_cache.items()):
                if len(val) == 4 and isinstance(k, tuple) and k[0] == camera_id:
                    v_class, v_conf, cached_time, cached_bbox = val
                    if now - cached_time <= max_age:
                        cx1, cy1, cx2, cy2 = cached_bbox
                        inter_w = max(0, min(x2, cx2) - max(x1, cx1))
                        inter_h = max(0, min(y2, cy2) - max(y1, cy1))
                        inter_area = inter_w * inter_h
                        if inter_area > 0:
                            area2 = max(1, (cx2 - cx1) * (cy2 - cy1))
                            iou = inter_area / float(area1 + area2 - inter_area)
                            if iou > 0.30:
                                return v_class, v_conf

        return "pending", 0.0

    def _map_behavior_to_enum(self, b: str) -> str:
        mapping = {
            "phone_detected": "phone_detected",
            "cell_phone": "phone_detected",
            "mobile_detected": "phone_detected",
            "using_mobile": "phone_detected",
            "smartwatch_detected": "smartwatch_detected",
            "smart_watch_detected": "smartwatch_detected",
            "smart_watch": "smartwatch_detected",
            "gaze_sideways": "gaze_sideways",
            "looking_around": "gaze_sideways",
            "repeated_gaze_deviation": "gaze_sideways",
            "correlated_gaze_and_head_turning": "excessive_turning",
            "repeated_head_turning": "excessive_turning",
            "excessive_turning": "excessive_turning",
            "gaze_downward": "gaze_downward",
            "looking_to_copy": "gaze_downward",
            "paper_sharing": "paper_sharing",
            "sharing_answers": "paper_sharing",
            "student_interaction": "paper_sharing",
            "repeated_student_interaction": "paper_sharing",
            "repeated_student_interaction_with_correlated_gaze": "paper_sharing",
            "leaning": "leaning",
            "repeated_leaning": "leaning",
            "leaning_to_copy": "leaning",
            "wrist_below_desk": "wrist_below_desk",
            "hidden_hand_below_desk": "wrist_below_desk",
            "shoulder_movement": "shoulder_movement",
            "excessive_movement": "shoulder_movement",
        }
        cleaned = b.lower().replace(" ", "_").replace("-", "_")
        return mapping.get(cleaned, "gaze_sideways")

    async def _create_alert(self, student_data: dict, fusion_output, camera_id: str) -> dict:
        """Create alert with evidence"""
        import uuid
        
        alert = {
            "alert_id": str(uuid.uuid4()),
            "student_id": student_data["student_id"],
            "camera_id": camera_id,
            "timestamp": datetime.now().isoformat(),
            "severity": fusion_output.risk_level.value,
            "risk_score": fusion_output.overall_risk_score,
            "reason": fusion_output.brief_reason,
            "behaviors": fusion_output.primary_behaviors,
            "component_scores": fusion_output.component_scores,
            "detailed_reasons": fusion_output.detailed_reasons,
        }
        
        logger.warning(f"🚨 ALERT: {alert['severity']} - {alert['student_id']} - {alert['reason']}")
        
        return alert

    def _iter_student_detections(self, detections: dict | Iterable[Any] | None):
        """Normalize detection/tracking output into (track_id, detection) pairs for PERSON tracks only."""
        if detections is None:
            return []
        if isinstance(detections, dict):
            items = list(detections.items())
        else:
            items = [
                (self._value(item, "track_id", index + 1), item)
                for index, item in enumerate(detections)
            ]
        # Only PERSON tracks should be processed as students!
        student_items = []
        for tid, item in items:
            cname = str(self._value(item, "class_name", "person")).lower().strip()
            if cname in {"person", "student"}:
                student_items.append((tid, item))
        return student_items

    def _value(self, item: Any, key: str, default: Any = None) -> Any:
        """Read a value from either dict-like or object-like detection records."""
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def _phone_confidence(self, detection: Any) -> float:
        """Extract linked phone confidence from a track/detection if available."""
        cname = str(self._value(detection, "class_name", "")).lower()
        if cname in {"scientific_calculator", "calculator"} or self._value(detection, "safe", False):
            direct = 0.0
        else:
            direct = self._value(detection, "phone_confidence")
            if direct is not None and float(direct) > 0.0:
                return float(direct)
        objects = self._value(detection, "objects_detected", []) or []
        phone_scores = [
            float(obj.get("confidence", 0.0))
            for obj in objects
            if obj.get("class_name") in {"cell phone", "mobile", "phone", "earphones", "earbuds", "bluetooth device", "tablet"}
            and not obj.get("safe", False)
            and obj.get("class_name") not in {"scientific_calculator", "calculator"}
        ]
        return max(phone_scores, default=(float(direct) if direct is not None else 0.0))

    def _smartwatch_confidence(self, detection: Any) -> float:
        """Extract linked smartwatch confidence from a track/detection if available."""
        objects = self._value(detection, "objects_detected", []) or []
        sw_scores = [
            float(obj.get("confidence", 0.0))
            for obj in objects
            if obj.get("class_name") in {"smart watch", "smartwatch"}
        ]
        return max(sw_scores, default=0.0)

    def _movement_variance(self, detection: Any) -> float:
        """Estimate short-term movement variance from track history when present."""
        direct = self._value(detection, "movement_variance")
        if direct is not None:
            return float(direct)
        history = self._value(detection, "history", []) or []
        if len(history) < 3:
            return 0.0
        points = np.array(history[-10:], dtype=float)
        return float(np.clip(np.mean(np.std(points, axis=0)) / 120.0, 0.0, 1.0))

    def _synthetic_frame(self, camera_id: str, frame_count: int) -> np.ndarray:
        """Generate a lightweight synthetic frame for dry-run/demo mode."""
        height = int(self.config.get("frame_height", 480))
        width = int(self.config.get("frame_width", 640))
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (28, 28, 38)
        cv2.putText(frame, f"{camera_id} synthetic feed", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 240, 255), 2)
        for idx in range(3):
            x = 90 + idx * 170 + int(10 * np.sin(frame_count / 20 + idx))
            y = 150 + idx * 45
            cv2.rectangle(frame, (x, y), (x + 85, y + 140), (70, 160, 220), 2)
            cv2.putText(frame, f"ID {idx + 1}", (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 255, 140), 1)
        return frame

    def _synthetic_tracks(self, camera_id: str, frame_count: int) -> Dict[int, Dict[str, Any]]:
        """Generate stable Track-like dicts when no camera/model is available."""
        tracks: Dict[int, Dict[str, Any]] = {}
        for idx in range(3):
            track_id = idx + 1
            x = 90 + idx * 170 + int(10 * np.sin(frame_count / 20 + idx))
            y = 150 + idx * 45
            tracks[track_id] = {
                "track_id": track_id,
                "bbox": [x, y, x + 85, y + 140],
                "confidence": 0.9,
                "phone_confidence": 0.85 if frame_count % 120 > 90 and idx == 1 else 0.0,
                "movement_variance": 0.35 if idx == 2 else 0.08,
            }
        return tracks
    
    async def run_async(self, camera_id: str, rtsp_url: str):
        """
        Run pipeline asynchronously for a camera
        """
        logger.info(f"🎬 Starting pipeline for {camera_id}")

        self.running = True
        frame_count = 0
        capture = None
        synthetic_mode = self.config.get("synthetic_mode", False)
        
        try:
            if not synthetic_mode:
                capture = cv2.VideoCapture(rtsp_url)
                if not capture.isOpened():
                    logger.warning("⚠️ Could not open camera source %s; switching to synthetic mode", rtsp_url)
                    synthetic_mode = True

            while self.running:
                frame_count += 1

                if synthetic_mode:
                    frame = self._synthetic_frame(camera_id, frame_count)
                    tracking_results = self._synthetic_tracks(camera_id, frame_count)
                else:
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        logger.warning("⚠️ Frame read failed for %s; retrying", camera_id)
                        await asyncio.sleep(0.1)
                        continue

                    if self.detector and self.tracker:
                        detections = self.detector.detect(frame)
                        tracking_results = self.tracker.update(detections, frame=frame)
                        frame = self.tracker.draw_tracks(frame, tracking_results)
                    else:
                        tracking_results = self._synthetic_tracks(camera_id, frame_count)

                await self.process_frame(frame, camera_id, tracking_results)
                
                # Check alerts periodically
                if frame_count % 30 == 0:
                    logger.info(f"✅ {camera_id}: {frame_count} frames processed, "
                               f"{len(self.students_tracked)} students tracked, "
                               f"{len(self.recent_alerts)} recent alerts")
                
                # Small delay to prevent CPU overload
                await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.exception("❌ Pipeline error for %s: %s", camera_id, e)
        
        finally:
            if capture is not None:
                capture.release()
            logger.info(f"🛑 Pipeline stopped for {camera_id}")
            self.running = False
    
    def stop(self, timeout: float = 5.0):
        """Stop the worker and release CV resources."""
        self.running = False
        worker = self._worker_thread
        if worker and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=timeout)
        self._worker_thread = None
        if hasattr(self, "_answersheet_executor") and self._answersheet_executor:
            try:
                self._answersheet_executor.shutdown(wait=False)
            except Exception:
                pass
        for component in (self.face_agent, self.gaze_agent, self.skeleton_analyzer):
            release = getattr(component, "release", None)
            if callable(release):
                try:
                    release()
                except Exception:
                    logger.exception("Failed to release pipeline component %s", type(component).__name__)

    def health(self) -> dict:
        worker_alive = bool(self._worker_thread and self._worker_thread.is_alive())
        return {
            "status": "running" if self.running and worker_alive else "stopped",
            "running": self.running,
            "worker_alive": worker_alive,
            "queue_depth": self._frame_queue.qsize(),
            "frames_submitted": self._frames_submitted,
            "frames_processed": self._frames_processed,
            "frames_dropped": self._frames_dropped,
            "camera_errors": dict(self._camera_errors),
            "last_processed_at": dict(self._last_processed_at),
            "agents": {
                "detection": "ready" if self.detector is not None else "degraded",
                "tracking": "ready" if self.tracker is not None else "degraded",
                "behavior": "ready" if self.fusion_engine is not None else "unavailable",
                "face": "ready" if getattr(self.face_agent, "face_mesh", None) is not None else "degraded",
                "gaze": "ready" if getattr(self.gaze_agent, "face_mesh", None) is not None else "degraded",
                "pose": "ready" if getattr(self.skeleton_analyzer, "pose", None) is not None else "degraded",
            },
        }
    
    def get_dashboard_stats(self) -> dict:
        """Get statistics for dashboard"""
        return {
            "total_students": len(self.students_tracked),
            "high_risk_students": sum(
                1 for s in self.students_tracked.values()
                if s.get("risk_level") in ["high", "critical"]
            ),
            "total_alerts": len(self.recent_alerts),
            "recent_alerts": list(self.recent_alerts)[-10:],
            "timestamp": datetime.now().isoformat()
        }


# Compatibility name for runtime health and lifecycle terminology. This is the
# existing integrated pipeline, not another pipeline implementation.
DetectionPipeline = IntegratedSurveillancePipeline


# Example Usage
async def main():
    """Example integration usage"""
    
    config = {
        "frame_width": 640,
        "frame_height": 480,
        "desk_y_ratio": 0.7,
        "temporal_window": 15,
        "persistence_threshold": 10,
        "alert_threshold": 60,
        "gemini_api_key": None,  # Set if using Gemini
        "webrtc": {
            "bitrate": 2500000,
            "fps": 30,
        }
    }
    
    # Initialize pipeline
    pipeline = IntegratedSurveillancePipeline(config)
    
    # Simulate processing
    # In real deployment, this would process actual camera streams
    logger.info("✅ Integration pipeline ready for deployment")
    
    # Example: Get dashboard stats
    stats = pipeline.get_dashboard_stats()
    logger.info(f"Dashboard stats: {stats}")


IntegratedPipeline = IntegratedSurveillancePipeline

if __name__ == "__main__":
    asyncio.run(main())
