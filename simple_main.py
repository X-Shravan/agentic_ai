"""
Simplified Exam Surveillance System - Per specification pipeline
Frame → Detect → Track → Analyze → Draw → Return Processed Frame
"""
from __future__ import annotations
import argparse
import signal
import sys
import time
from pathlib import Path
import cv2
from backend.camera_manager import CameraManager
import yaml
from collections import defaultdict
import numpy as np

# Use simple behavior analysis
from agents.simple_behavior_analysis import SimpleBehaviorAnalysis

# Other agents
from agents.detection_agent import DetectionAgent
from agents.tracking_agent import TrackingAgent
from agents.role_classification_agent import RoleClassificationAgent
from alerts.evidence_capture import EvidenceCapture


class SimpleSurveillanceSystem:
    """Simplified surveillance system following exact pipeline specification"""
    
    def __init__(self, config_path="config/config.yaml", demo_mode=False):
        self.config = self._load_config(config_path)
        self.demo_mode = demo_mode
        self.running = False
        
        # Frame timing
        self.frame_count = 0
        self.last_time = time.time()
        self.fps = 0
        
        # Pipeline parameters
        self.TARGET_WIDTH = 640
        self.TARGET_HEIGHT = 480
        self.YOLO_INTERVAL = 2  # Run YOLO every 2nd frame
        self.last_detections = {}
        
        # Initialize agents
        self._init_video_source()
        self.detection_agent = DetectionAgent(self.config)
        self.tracking_agents = {}
        self.role_agents = {}
        self.behavior_agent = SimpleBehaviorAnalysis(self.config)
        self.evidence = EvidenceCapture("evidence")
        
        # Track previous status for evidence saving
        self.prev_status = defaultdict(str)
        
        print("✅ SimpleSurveillanceSystem initialized")
    
    def _load_config(self, path):
        p = Path(path)
        return yaml.safe_load(p.read_text()) if p.exists() else {}
    
    def _init_video_source(self):
        """Initialize video source"""
        if self.demo_mode:
            video_source = 0  # Webcam
        else:
            video_source = self.config.get("video_source", 0)
        
        self.camera_manager = CameraManager([{"id": "camera_0", "type": "webcam" if isinstance(video_source, int) else "file", "device_index": video_source if isinstance(video_source, int) else None, "url": video_source if not isinstance(video_source, int) else None, "resolution": [1280, 720]}])
        if not self.camera_manager.start_all():
            print("❌ Cannot open camera")
            return False
        print("✅ Camera opened")
        return True
    
    def _get_camera_agents(self, camera_id=0):
        """Get or create agents for camera"""
        if camera_id not in self.tracking_agents:
            self.tracking_agents[camera_id] = TrackingAgent(self.config)
            self.role_agents[camera_id] = RoleClassificationAgent(self.config)
        
        return self.tracking_agents[camera_id], self.role_agents[camera_id]
    
    def start(self):
        """Start surveillance"""
        self.running = True
        print("🚀 Surveillance started")
        return True
    
    def stop(self):
        """Stop surveillance"""
        self.running = False
        if hasattr(self, 'camera_manager'):
            self.camera_manager.stop_all()
        print("🛑 Surveillance stopped")
    
    def process_frame(self):
        """
        Main pipeline per specification:
        
        frame = read()
        → Resize
        → Skip check
        → YOLO detection
        → Tracking
        → Behavior analysis
        → Draw
        → Return processed_frame
        """
        
        frames = self.camera_manager.read_all()
        frame = frames.get("camera_0")
        if frame is None:
            return None
        
        # STEP 1: RESIZE
        frame = cv2.resize(frame, (self.TARGET_WIDTH, self.TARGET_HEIGHT))
        
        # STEP 2: SKIP FRAMES
        # NOTE: Skip happens in run() loop, not here
        
        # STEP 3: YOLO DETECTION (every 2nd frame)
        camera_id = 0
        if self.frame_count % self.YOLO_INTERVAL == 0:
            detections = self.detection_agent.detect(frame)
            self.last_detections[camera_id] = detections
            print(f"[YOLO] Frame {self.frame_count}: {len(detections)} detections")
        else:
            detections = self.last_detections.get(camera_id, [])
        
        # STEP 4: TRACKING
        tracker, role_agent = self._get_camera_agents(camera_id)
        tracks = tracker.update(detections)
        role_agent.classify(tracks)
        
        # Filter for students only
        student_tracks = [t for t in tracks if role_agent.is_student(t.track_id)]
        
        print(f"[TRACKING] {len(tracks)} total tracks, {len(student_tracks)} students")
        
        # STEP 5: BEHAVIOR ANALYSIS
        behavior_results = self.behavior_agent.analyze(frame, student_tracks, detections)
        
        # STEP 6: DRAW ON FRAME
        processed_frame = frame.copy()
        
        for tid, behavior in behavior_results.items():
            # Find track for this ID
            track = next((t for t in student_tracks if t.track_id == tid), None)
            if not track:
                continue
            
            x1, y1, x2, y2 = map(int, track.bbox)
            status = behavior["status"]
            confidence = behavior["confidence"]
            yaw = behavior["yaw"]
            pitch = behavior["pitch"]
            
            # Determine color
            if "🚨" in status:  # Alert
                color = (0, 0, 255)  # Red
            elif "👀" in status or "↘️" in status:  # Suspicious
                color = (0, 165, 255)  # Orange
            else:  # Normal
                color = (0, 255, 0)  # Green
            
            # Draw bounding box
            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 3)
            
            # Draw label: ID | Status | Confidence%
            label = f"ID {tid} | {status} | {int(confidence*100)}%"
            cv2.putText(
                processed_frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )
            
            # Draw pose info (for debugging)
            info_text = f"Yaw:{int(yaw)}° Pitch:{int(pitch)}°"
            cv2.putText(
                processed_frame,
                info_text,
                (x1, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1
            )
            
            # STEP 7: SAVE EVIDENCE (on status change)
            current_status = status
            if tid in self.prev_status:
                prev = self.prev_status[tid]
                # Alert if transitioning from normal to alert
                if ("🚨" in current_status or "🤝" in current_status) and \
                   ("🚨" not in prev and "🤝" not in prev):
                    print(f"🚨 ALERT: ID {tid} - {current_status}")
                    self.evidence.save_screenshot(
                        processed_frame, tid,
                        confidence,
                        [current_status]
                    )
            
            self.prev_status[tid] = current_status
        
        # Add FPS and info
        current_time = time.time()
        dt = current_time - self.last_time
        self.fps = 0.9 * self.fps + 0.1 * (1 / max(0.001, dt))
        self.last_time = current_time
        
        cv2.putText(
            processed_frame,
            f"FPS: {int(self.fps)}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )
        
        cv2.putText(
            processed_frame,
            f"Frame {self.frame_count} | Students: {len(student_tracks)}",
            (20, processed_frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )
        
        # STEP 8: RETURN PROCESSED FRAME
        return {
            "frame": processed_frame,
            "tracks": student_tracks,
            "detections": detections,
            "behavior": behavior_results
        }
    
    def run(self, display=True):
        """Main loop with frame skipping"""
        if not self.start():
            return
        
        print("🎬 Running surveillance pipeline...")
        
        try:
            while self.running:
                # FRAME SKIP (every 2nd frame)
                if self.frame_count % 2 != 0:
                    self.frame_count += 1
                    continue
                
                # Process
                result = self.process_frame()
                if result is None:
                    break
                
                self.frame_count += 1
                
                # Display
                if display:
                    cv2.imshow("Surveillance System", result["frame"])
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
        
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
        finally:
            self.stop()
            cv2.destroyAllWindows()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Simple Surveillance System")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--demo", action="store_true", help="Demo mode (webcam)")
    parser.add_argument("--no-display", action="store_true")
    
    args = parser.parse_args()
    
    system = SimpleSurveillanceSystem(
        config_path=args.config,
        demo_mode=args.demo
    )
    
    def handler(sig, frame):
        print("\n🛑 Shutting down...")
        system.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    
    system.run(display=not args.no_display)


if __name__ == "__main__":
    main()
