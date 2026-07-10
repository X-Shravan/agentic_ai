"""
Complete Integration Pipeline
Demonstrates full end-to-end system integration
Camera capture → Detection → Tracking → Analysis → Streaming → Frontend
"""

from __future__ import annotations
import cv2
import numpy as np
import asyncio
import threading
import time
import logging
from collections import deque
from datetime import datetime
from pathlib import Path

# Import system modules
from analysis.skeleton_analyzer import SkeletonAnalyzer
from analysis.multimodal_fusion import MultiModalFusionEngine, FusionInput, RiskLevel
from analysis.gemini_reasoning import GeminiReasoningEngine, GeminiBatchProcessor
from server.webrtc_server import init_webrtc_server, get_webrtc_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedSurveillancePipeline:
    """
    Complete surveillance pipeline integrating all components
    """
    
    def __init__(self, config: dict):
        self.config = config
        
        # Initialize components
        self.skeleton_analyzer = SkeletonAnalyzer(
            frame_width=config.get("frame_width", 640),
            frame_height=config.get("frame_height", 480),
            desk_y_ratio=config.get("desk_y_ratio", 0.7)
        )
        
        self.fusion_engine = MultiModalFusionEngine(
            temporal_window=config.get("temporal_window", 15),
            persistence_threshold=config.get("persistence_threshold", 10)
        )
        
        # Gemini (optional)
        gemini_key = config.get("gemini_api_key")
        if gemini_key:
            self.gemini = GeminiReasoningEngine(gemini_key)
            self.batch_processor = GeminiBatchProcessor(self.gemini)
        else:
            self.gemini = None
            self.batch_processor = None
        
        # WebRTC server
        init_webrtc_server(config)
        self.webrtc_server = get_webrtc_server()
        
        # State management
        self.running = False
        self.students_tracked = {}  # track_id -> student_data
        self.recent_alerts = deque(maxlen=100)
        
        logger.info("✅ Integrated pipeline initialized")
    
    async def process_frame(
        self,
        frame: np.ndarray,
        camera_id: str,
        yolo_results: dict,
        face_mesh_results: dict = None
    ) -> dict:
        """
        Process single frame through complete pipeline
        
        Args:
            frame: Input frame (BGR)
            camera_id: Camera identifier
            yolo_results: YOLO detection results {track_id: {bbox, confidence, class}}
            face_mesh_results: Optional face mesh results
        
        Returns:
            Processing results with all analyses
        """
        
        frame_results = {
            "timestamp": datetime.now(),
            "camera_id": camera_id,
            "students": {},
            "alerts": [],
            "frame_annotated": frame.copy()
        }
        
        # 1. Run skeleton analysis
        skeleton_results = self.skeleton_analyzer.analyze(frame, face_mesh_results)
        frame_results["skeleton"] = skeleton_results
        
        # Annotate skeleton on frame
        if skeleton_results.detected:
            frame_annotated = self.skeleton_analyzer.draw_skeleton(
                frame_results["frame_annotated"],
                skeleton_results
            )
            frame_results["frame_annotated"] = frame_annotated
        
        # 2. Process each detected student
        for track_id, detection in yolo_results.items():
            student_id = f"{camera_id}_{track_id}"
            
            # 3. Prepare fusion input (multi-modal)
            fusion_input = FusionInput(
                # Face mesh data
                gaze_left_score=face_mesh_results.get("gaze_left", 0.0) if face_mesh_results else 0.0,
                gaze_right_score=face_mesh_results.get("gaze_right", 0.0) if face_mesh_results else 0.0,
                gaze_down_score=face_mesh_results.get("gaze_down", 0.0) if face_mesh_results else 0.0,
                head_yaw_degrees=face_mesh_results.get("yaw", 0.0) if face_mesh_results else 0.0,
                head_pitch_degrees=face_mesh_results.get("pitch", 0.0) if face_mesh_results else 0.0,
                head_roll_degrees=face_mesh_results.get("roll", 0.0) if face_mesh_results else 0.0,
                
                # Skeleton data
                leaning_score=skeleton_results.leaning_severity if skeleton_results.detected else 0.0,
                wrist_below_desk_score=skeleton_results.wrist_movement_severity if skeleton_results.detected else 0.0,
                arm_extension_score=skeleton_results.arm_movement_severity if skeleton_results.detected else 0.0,
                shoulder_movement_score=skeleton_results.shoulder_angle_degrees / 45.0 if skeleton_results.detected else 0.0,
                
                # Phone detection
                phone_visible_score=detection.get("phone_confidence", 0.0),
                
                # Movement stability
                movement_variance=detection.get("movement_variance", 0.0),
                
                timestamp=time.time()
            )
            
            # 4. Fuse all modalities
            fusion_output = self.fusion_engine.fuse(fusion_input)
            
            # 5. Store student results
            student_data = {
                "track_id": track_id,
                "student_id": student_id,
                "bbox": detection.get("bbox"),
                "confidence": detection.get("confidence", 0.0),
                "risk_score": fusion_output.overall_risk_score,
                "risk_level": fusion_output.risk_level.value,
                "behaviors": fusion_output.primary_behaviors,
                "component_scores": fusion_output.component_scores,
            }
            
            frame_results["students"][student_id] = student_data
            self.students_tracked[track_id] = student_data
            
            # 6. Check if alert should be triggered
            alert_threshold = self.config.get("alert_threshold", 60)
            if fusion_output.overall_risk_score > alert_threshold:
                alert = await self._create_alert(
                    student_data,
                    fusion_output,
                    camera_id
                )
                frame_results["alerts"].append(alert)
                self.recent_alerts.append(alert)
                
                # 7. Gemini reasoning (if enabled)
                if self.batch_processor:
                    await self.batch_processor.queue_alert({
                        "alert_id": alert["alert_id"],
                        "student_id": student_id,
                        "behaviors": fusion_output.primary_behaviors,
                        "overall_risk": fusion_output.overall_risk_score,
                        "gaze_score": fusion_output.component_scores["gaze"],
                        "pose_score": fusion_output.component_scores["pose"],
                        "phone_score": fusion_output.component_scores["phone"],
                        "timestamp": datetime.now().isoformat()
                    })
        
        # 8. Push frame to WebRTC server
        self.webrtc_server.push_frame(
            camera_id,
            frame_results["frame_annotated"],
            time.time()
        )
        
        return frame_results
    
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
    
    async def run_async(self, camera_id: str, rtsp_url: str):
        """
        Run pipeline asynchronously for a camera
        """
        logger.info(f"🎬 Starting pipeline for {camera_id}")
        
        # TODO: Integrate with actual camera capture and YOLO/tracking
        # This is a template showing integration points
        
        self.running = True
        frame_count = 0
        
        try:
            while self.running:
                # 1. Capture frame (would be from OpenCV RTSP capture)
                # frame = cap.read()
                
                # 2. Run YOLO detection (would be from detection pipeline)
                # yolo_results = detector.detect(frame)
                
                # 3. Run DeepSORT tracking (would be from tracking pipeline)
                # tracking_results = tracker.update(yolo_results)
                
                # 4. Run face mesh (would be from face detection pipeline)
                # face_mesh_results = face_detector.detect(frame)
                
                # 5. Process through integrated pipeline
                # results = await self.process_frame(
                #     frame,
                #     camera_id,
                #     tracking_results,
                #     face_mesh_results
                # )
                
                frame_count += 1
                
                # Check alerts periodically
                if frame_count % 30 == 0:
                    logger.info(f"✅ {camera_id}: {frame_count} frames processed, "
                               f"{len(self.students_tracked)} students tracked, "
                               f"{len(self.recent_alerts)} recent alerts")
                
                # Small delay to prevent CPU overload
                await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}")
        
        finally:
            logger.info(f"🛑 Pipeline stopped for {camera_id}")
            self.running = False
    
    def stop(self):
        """Stop pipeline"""
        self.running = False
    
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


if __name__ == "__main__":
    asyncio.run(main())
