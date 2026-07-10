"""
Simplified Behavior Analysis - Direct implementation per specifications
Uses temporal logic with counter decay (no instant resets)
"""
from __future__ import annotations
import time
import cv2
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple
import mediapipe as mp
import math


@dataclass
class BehaviorEvent:
    event_type: str
    confidence: float
    timestamp: float
    situation: str = ""


class SimpleBehaviorAnalysis:
    """Direct behavior analysis per user specifications"""
    
    def __init__(self, config=None):
        # Thresholds (PER SPECIFICATION)
        self.LOOK_AROUND_YAW = 20  # degrees
        self.LOOK_AROUND_COUNT = 3  # frames
        
        self.LOOK_COPY_PITCH = 15  # degrees
        self.LOOK_COPY_YAW = 10  # degrees
        self.LOOK_COPY_COUNT = 3  # frames
        
        self.LEAN_SHOULDER_DIFF = 10  # normalized units
        self.LEAN_FRAMES = 15  # frames
        
        self.MOBILE_CONF = 0.6
        self.MOBILE_AREA = 7000
        self.MOBILE_ASPECT_MIN = 1.4
        self.MOBILE_ASPECT_MAX = 2.5
        
        self.SHARING_DISTANCE = 150  # pixels
        self.SHARING_YAW_DIFF = 25  # degrees (opposite direction)
        self.SHARING_COUNT = 3
        
        # Temporal tracking (NO INSTANT RESET)
        self.look_count = defaultdict(int)
        self.copy_count = defaultdict(int)
        self.lean_frames = defaultdict(int)
        self.sharing_count = defaultdict(int)
        
        # Previous status for consistency
        self.prev_status = defaultdict(str)
        
        # MediaPipe
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=10,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=0,  # lite
            min_detection_confidence=0.5
        )
        
        print("✅ SimpleBehaviorAnalysis initialized")
    
    def get_head_pose(self, face_landmarks, w: int, h: int) -> Tuple[float, float]:
        """
        Calculate yaw (left-right) and pitch (up-down) from face landmarks
        Returns: (yaw, pitch) in degrees
        """
        try:
            left_eye = face_landmarks.landmark[33]  # Left eye outer
            right_eye = face_landmarks.landmark[263]  # Right eye outer
            nose = face_landmarks.landmark[1]  # Nose tip
            
            # Get pixel coordinates
            lx = left_eye.x * w
            rx = right_eye.x * w
            nx = nose.x * w
            ly = left_eye.y * h
            ny = nose.y * h
            
            # Yaw: horizontal head rotation
            eye_center_x = (lx + rx) / 2
            yaw = (nx - eye_center_x) / (w / 2) * 90
            
            # Pitch: vertical head rotation
            pitch = (ny - ly) / (h / 2) * 90
            
            return yaw, pitch
        except:
            return 0, 0
    
    def get_shoulder_tilt(self, pose_landmarks) -> float:
        """Calculate shoulder tilt from pose landmarks"""
        try:
            lm = pose_landmarks.landmark
            left_shoulder_y = lm[11].y
            right_shoulder_y = lm[12].y
            return abs(left_shoulder_y - right_shoulder_y) * 100  # Scale to 0-100
        except:
            return 0
    
    def check_mobile(self, detections: List) -> bool:
        """Check if phone detected with proper validation"""
        for det in detections:
            if det.get("class_name") == "cell phone":
                conf = det.get("confidence", 0)
                bbox = det.get("bbox", [])
                
                if conf < self.MOBILE_CONF:
                    continue
                
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    width = x2 - x1
                    height = y2 - y1
                    area = width * height
                    ratio = height / width if width > 0 else 0
                    
                    # Check all conditions
                    if (area > self.MOBILE_AREA and 
                        self.MOBILE_ASPECT_MIN < ratio < self.MOBILE_ASPECT_MAX):
                        return True
        return False
    
    def decay_counter(self, count: int) -> int:
        """Gradual decay (not instant reset)"""
        return max(0, count - 1)
    
    def analyze(self, frame, tracks: List, detections: List = None) -> Dict:
        """
        Main analysis per specification
        
        Frame → Resize → YOLO → Per-person:
            - Extract ROI
            - MediaPipe (face + pose)
            - Calculate yaw/pitch/shoulder
            - Update counters
        → Decide status with temporal logic
        → Return results
        """
        if detections is None:
            detections = []
        
        results = {}
        h, w = frame.shape[:2]
        mobile_detected = self.check_mobile(detections)
        
        for track in tracks:
            tid = track.track_id
            x1, y1, x2, y2 = map(int, track.bbox)
            
            # Extract ROI
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            
            # Resize for MediaPipe
            roi_resized = cv2.resize(roi, (320, 240))
            rgb = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2RGB)
            
            # Process with MediaPipe
            yaw, pitch = 0, 0
            shoulder_tilt = 0
            
            face_res = self.face_mesh.process(rgb)
            if face_res and face_res.multi_face_landmarks:
                for face_landmarks in face_res.multi_face_landmarks:
                    yaw, pitch = self.get_head_pose(face_landmarks, 320, 240)
                    break
            
            pose_res = self.pose.process(rgb)
            if pose_res and pose_res.pose_landmarks:
                shoulder_tilt = self.get_shoulder_tilt(pose_res.pose_landmarks)
            
            # ===== BEHAVIOR COUNTERS (PER SPEC) =====
            
            # LOOKING AROUND
            if abs(yaw) > self.LOOK_AROUND_YAW:
                self.look_count[tid] += 1
            else:
                self.look_count[tid] = self.decay_counter(self.look_count[tid])
            
            # LOOKING TO COPY
            if abs(pitch) > self.LOOK_COPY_PITCH and abs(yaw) > self.LOOK_COPY_YAW:
                self.copy_count[tid] += 1
            else:
                self.copy_count[tid] = self.decay_counter(self.copy_count[tid])
            
            # LEANING
            if shoulder_tilt > self.LEAN_SHOULDER_DIFF:
                self.lean_frames[tid] += 1
            else:
                self.lean_frames[tid] = self.decay_counter(self.lean_frames[tid])
            
            # ===== PRIORITY SYSTEM (PER SPEC) =====
            status = "Normal"
            confidence = 0.0
            is_alert = False
            
            if mobile_detected:
                status = "Using Mobile 🚨"
                confidence = 0.95
                is_alert = True
            elif self.copy_count[tid] >= self.LOOK_COPY_COUNT:
                status = "Looking to Copy 🚨"
                confidence = 0.85
                is_alert = True
            elif self.look_count[tid] >= self.LOOK_AROUND_COUNT:
                status = "Looking Around 👀"
                confidence = 0.70
                is_alert = False
            elif self.lean_frames[tid] >= self.LEAN_FRAMES:
                status = "Leaning ↘️"
                confidence = 0.60
                is_alert = False
            
            # Store result
            event = BehaviorEvent(
                event_type="Alert" if is_alert else "Normal",
                confidence=confidence,
                timestamp=time.time(),
                situation=status
            )
            
            results[tid] = {
                "status": status,
                "confidence": confidence,
                "is_alert": is_alert,
                "event": event,
                "yaw": yaw,
                "pitch": pitch,
                "shoulder_tilt": shoulder_tilt,
                "look_count": self.look_count[tid],
                "copy_count": self.copy_count[tid],
                "lean_frames": self.lean_frames[tid]
            }
        
        return results
    
    def reset(self):
        """Reset all state"""
        self.look_count.clear()
        self.copy_count.clear()
        self.lean_frames.clear()
        self.sharing_count.clear()
        self.prev_status.clear()
