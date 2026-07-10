from __future__ import annotations
import argparse
import signal
import sys
import time
from pathlib import Path
import cv2
import yaml

from agents.behavior_analysis_agent import BehaviorAnalysisAgent
from agents.decision_agent import DecisionAgent
from agents.detection_agent import DetectionAgent
from agents.risk_scoring_agent import RiskScoringAgent
from agents.role_classification_agent import RoleClassificationAgent
from agents.surveillance_agent import DemoSurveillanceAgent, SurveillanceAgent
from agents.tracking_agent import TrackingAgent
from alerts.evidence_capture import EvidenceCapture
from alerts.hardware_alert import HardwareAlert
from utils.alert_utils import alert_message


class ExamSurveillanceSystem:
    def __init__(self, config_path="config/config.yaml", demo_mode=False):
        self.config = self._load_config(config_path)
        self.demo_mode = demo_mode
        self.running = False
        self.frame_count = 0
        self.last_time = time.time()

        # 🔥 PERFORMANCE
        self.YOLO_INTERVAL = 2
        self.FRAME_SKIP = 2
        self.last_detections = {}

        # Surveillance Agent
        if demo_mode:
            self.config.setdefault("demo", {})["video_source"] = 0
            self.surveillance_agent = DemoSurveillanceAgent(self.config)
        else:
            self.surveillance_agent = SurveillanceAgent(self.config)

        # Global Agents
        self.detection_agent = DetectionAgent(self.config)
        self.evidence = EvidenceCapture(
            self.config.get("alerts", {}).get("evidence_dir", "evidence")
        )
        self.hardware = HardwareAlert(
            self.config.get("alerts", {}).get("hardware_enabled", False)
        )

        # Per-camera agents
        self.tracking_agents = {}
        self.role_agents = {}
        self.behavior_agents = {}
        self.risk_agents = {}
        self.decision_agents = {}

    def _load_config(self, path):
        p = Path(path)
        return yaml.safe_load(p.read_text()) if p.exists() else {}

    def _on_alert(self, decision):
        tid = getattr(decision, 'track_id', 'Unknown')
        score = getattr(decision, 'risk_score', 0)
        msg = alert_message(tid, score)
        print(f"🚨 ALERT: {msg}")
        self.hardware.trigger(msg)

    def _camera_agents(self, camera_id):
        if camera_id not in self.tracking_agents:
            self.tracking_agents[camera_id] = TrackingAgent(self.config)
            self.role_agents[camera_id] = RoleClassificationAgent(self.config)
            self.behavior_agents[camera_id] = BehaviorAnalysisAgent(self.config)
            self.risk_agents[camera_id] = RiskScoringAgent(self.config)

            decision_agent = DecisionAgent(self.config)
            decision_agent.register_callback(self._on_alert)
            self.decision_agents[camera_id] = decision_agent

        return (
            self.tracking_agents[camera_id],
            self.role_agents[camera_id],
            self.behavior_agents[camera_id],
            self.risk_agents[camera_id],
            self.decision_agents[camera_id],
        )

    def start(self):
        self.running = self.surveillance_agent.start()
        return self.running

    def stop(self):
        self.running = False
        self.surveillance_agent.stop()

    def process_frame(self):
        frames = self.surveillance_agent.get_frames()
        if not frames:
            return {}

        results = {}

        for cam_id, frame_data in frames.items():

            # 🔥 RESIZE (performance)
            frame = cv2.resize(frame_data.image, (640, 480))

            tracker, role_agent, behavior_agent, risk_agent, decision_agent = self._camera_agents(cam_id)

            # 🔥 YOLO FRAME SKIP
            if self.frame_count % self.YOLO_INTERVAL == 0:
                detections = self.detection_agent.detect(frame)
                self.last_detections[cam_id] = detections
            else:
                detections = self.last_detections.get(cam_id, [])

            # Pipeline
            tracks = tracker.update(detections)
            role_agent.classify(tracks)

            student_tracks = [t for t in tracks if role_agent.is_student(t.track_id)]
            behavior = behavior_agent.analyze(frame, student_tracks, detections)

            associations = risk_agent.associate_detections_to_tracks(detections, student_tracks)
            scores = risk_agent.calculate_scores(detections, behavior, associations)
            decisions = decision_agent.decide(scores)

            # Alerts
            for tid, dec in decisions.items():
                if dec.should_alert:
                    events = scores.get(tid, {}).get("events", [])
                    print(f"🚨 ALERT → ID {tid} | Score {dec.risk_score}")
                    self.evidence.save_screenshot(frame, tid, dec.risk_score, events)

            # ✅ CRITICAL: PROCESS FRAME WITH DRAWINGS BEFORE RETURNING
            processed_frame = frame.copy()
            
            # Draw detections first
            processed_frame = self.detection_agent.draw_detections(processed_frame, detections)
            
            # Draw tracks and labels
            if tracker:
                processed_frame = tracker.draw_tracks(processed_frame, tracks)
            
            # Draw all student info with bounding boxes and status
            for tid, track_info in list(scores.items()):
                score = track_info.get("score", 0)
                situation = track_info.get("situation", "Normal")
                
                # Determine color based on status
                if "🚨" in situation:  # ALERT (Mobile/Copy/Sharing)
                    color = (0, 0, 255)  # Red
                elif "👀" in situation or "↘️" in situation:  # SUSPICIOUS
                    color = (0, 165, 255)  # Orange
                else:  # NORMAL
                    color = (0, 255, 0)  # Green
                
                # Draw bounding box and label for each track
                for track in tracks:
                    if track.track_id == tid:
                        x1, y1, x2, y2 = map(int, track.bbox)
                        
                        # Draw rectangle
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 3)
                        
                        # Draw label above box with ID and situation
                        confidence = int(score * 100)
                        label_text = f"ID {tid} | {situation} | {confidence}%"
                        label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        
                        # Background for text
                        cv2.rectangle(
                            processed_frame, 
                            (x1, y1 - 30),
                            (x1 + label_size[0] + 5, y1),
                            color,
                            -1
                        )
                        
                        # Text
                        cv2.putText(
                            processed_frame, label_text,
                            (x1 + 2, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (255, 255, 255),
                            1
                        )
                        break

            results[cam_id] = {
                "frame": processed_frame,  # ✅ RETURN PROCESSED FRAME WITH DRAWINGS
                "detections": detections,
                "tracks": tracks,
                "scores": scores,
            }

        return results

    def run(self, display=True):
        if not self.start():
            print("❌ Failed to start system")
            return

        print("🚀 System Started")
        try:
            prev_status = {}  # Track previous status to detect changes
            
            while self.running:

                # 🔥 GLOBAL FRAME SKIP
                if self.frame_count % self.FRAME_SKIP != 0:
                    self.frame_count += 1
                    continue

                results = self.process_frame()

                if not results:
                    time.sleep(0.01)
                    continue

                self.frame_count += 1

                if display:
                    for cam_id, data in results.items():
                        # ✅ FRAME IS ALREADY PROCESSED WITH DRAWINGS
                        display_frame = data["frame"]

                        # ===== FPS DISPLAY (top-left) =====
                        current_time = time.time()
                        fps = 0.9 * getattr(self, "fps", 0) + 0.1 * (1 / max(0.001, (current_time - self.last_time)))
                        self.fps = fps
                        self.last_time = current_time

                        cv2.putText(
                            display_frame, 
                            f"FPS: {int(fps)}", 
                            (20, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 
                            0.7, 
                            (0, 255, 255), 
                            2
                        )

                        # ===== SYSTEM INFO =====
                        alerts_count = len([s for s in data["scores"].values() if "🚨" in s.get("situation", "")])
                        info_text = f"Students: {len(data['tracks'])} | Alerts: {alerts_count}"
                        cv2.putText(
                            display_frame,
                            info_text,
                            (20, display_frame.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (200, 200, 200),
                            1
                        )

                        # ✅ DISPLAY PROCESSED FRAME (WITH ALL DRAWINGS)
                        cv2.imshow(f"Surveillance - {cam_id}", display_frame)
                        
                        # ✅ SAVE EVIDENCE FOR ALL SUSPICIOUS BEHAVIORS (not just alerts)
                        for tid, track_info in list(data["scores"].items()):
                            current_status = track_info.get("situation", "Normal")
                            
                            # ✅ SAVE IF: ANY BEHAVIOR DETECTED (Alert, Suspicious, or normal change)
                            if tid in prev_status:
                                prev_stat = prev_status[tid]
                                # Check if status CHANGED and NEW status is not "Normal"
                                if prev_stat != current_status and current_status != "Normal":
                                    score = track_info.get("score", 0)
                                    print(f"\n🔴 BEHAVIOR DETECTED → ID {tid}: {current_status}")
                                    self.evidence.save_screenshot(
                                        display_frame,  # ✅ SAVE PROCESSED FRAME WITH BOXES AND LABELS
                                        tid, 
                                        score, 
                                        [track_info.get("situation", "")]
                                    )
                                    print(f"   ✅ Evidence saved for ID {tid}")
                            
                            prev_status[tid] = current_status

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            self.stop()
            if display:
                cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Smart Exam Surveillance System")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-display", action="store_false", dest="display")

    args = parser.parse_args()

    system = ExamSurveillanceSystem(config_path=args.config, demo_mode=args.demo)

    def handler(sig, frame):
        print("\nStopping system...")
        system.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    system.run(display=args.display)


if __name__ == "__main__":
    main()