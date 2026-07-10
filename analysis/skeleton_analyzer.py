"""
Enhanced Skeleton/Pose Analysis Module
Uses MediaPipe Pose Lite for 33-keypoint body detection
Detects suspicious body movements for exam invigilation
"""

from __future__ import annotations
import cv2
import numpy as np
import mediapipe as mp
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PoseKeypoint:
    name: str
    x: float
    y: float
    z: float
    visibility: float


@dataclass
class SkeletonAnalysis:
    detected: bool
    keypoints: Dict[str, PoseKeypoint]
    
    # Behavior flags
    leaning_detected: bool = False
    leaning_severity: float = 0.0
    
    excessive_arm_movement: bool = False
    arm_movement_severity: float = 0.0
    
    wrist_below_desk: bool = False
    wrist_movement_severity: float = 0.0
    
    shoulder_movement: bool = False
    shoulder_angle_degrees: float = 0.0
    
    hidden_phone_likely: bool = False
    phone_confidence: float = 0.0
    
    paper_sharing_likely: bool = False
    sharing_distance: float = 999.0  # Distance to nearest neighbor
    
    overall_confidence: float = 0.0
    anomaly_score: float = 0.0  # 0-100


class SkeletonAnalyzer:
    """
    Analyzes full-body skeleton for suspicious movements
    Uses MediaPipe Pose Lite (33 keypoints)
    """
    
    # Keypoint indices
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    
    def __init__(self, frame_width: int = 640, frame_height: int = 480, desk_y_ratio: float = 0.7):
        """
        Initialize skeleton analyzer
        
        Args:
            frame_width: Video frame width
            frame_height: Video frame height
            desk_y_ratio: Y-coordinate ratio where desk is located (0-1)
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.desk_y_ratio = desk_y_ratio  # Desk is typically lower 30% of frame
        self.desk_y = int(frame_height * desk_y_ratio)
        
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,  # Lite model for speed
            smooth_landmarks=True,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )
        
        # History for temporal smoothing
        self.keypoint_history: Dict[int, List[Tuple[float, float]]] = {}
        self.max_history = 10
        
        logger.info(f"✅ Skeleton analyzer initialized (desk_y: {self.desk_y})")
    
    def analyze(self, frame: np.ndarray, face_mesh_results=None) -> SkeletonAnalysis:
        """
        Analyze skeleton/pose in frame
        
        Args:
            frame: Input image (BGR)
            face_mesh_results: Optional face mesh results for context
        
        Returns:
            SkeletonAnalysis with detected behaviors
        """
        h, w, _ = frame.shape
        
        # Run pose detection
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        if not results.pose_landmarks:
            return SkeletonAnalysis(detected=False, keypoints={})
        
        # Extract keypoints
        keypoints = self._extract_keypoints(results.pose_landmarks, w, h)
        
        # Analyze behaviors
        analysis = SkeletonAnalysis(
            detected=True,
            keypoints=keypoints,
        )
        
        # Run behavior detections
        analysis.leaning_detected, analysis.leaning_severity = self._detect_leaning(keypoints)
        analysis.shoulder_movement, analysis.shoulder_angle_degrees = self._detect_shoulder_movement(keypoints)
        analysis.wrist_below_desk, analysis.wrist_movement_severity = self._detect_wrist_below_desk(keypoints)
        analysis.excessive_arm_movement, analysis.arm_movement_severity = self._detect_arm_movement(keypoints)
        analysis.hidden_phone_likely, analysis.phone_confidence = self._detect_hidden_phone(keypoints)
        
        # Calculate overall anomaly score
        analysis.overall_confidence = self._calculate_confidence(results.pose_landmarks)
        analysis.anomaly_score = self._calculate_anomaly_score(analysis)
        
        return analysis
    
    def _extract_keypoints(self, landmarks, frame_width: int, frame_height: int) -> Dict[str, PoseKeypoint]:
        """Extract keypoints from pose landmarks"""
        keypoint_names = [
            "nose", "left_eye_inner", "left_eye", "left_eye_outer",
            "right_eye_inner", "right_eye", "right_eye_outer",
            "left_ear", "right_ear", "mouth_left", "mouth_right",
            "left_shoulder", "right_shoulder",
            "left_elbow", "right_elbow",
            "left_wrist", "right_wrist",
            "left_pinky", "right_pinky",
            "left_index", "right_index",
            "left_thumb", "right_thumb",
            "left_hip", "right_hip",
            "left_knee", "right_knee",
            "left_ankle", "right_ankle",
            "left_heel", "right_heel",
            "left_foot_index", "right_foot_index"
        ]
        
        keypoints = {}
        for idx, landmark in enumerate(landmarks):
            if idx < len(keypoint_names):
                keypoints[keypoint_names[idx]] = PoseKeypoint(
                    name=keypoint_names[idx],
                    x=landmark.x * frame_width,
                    y=landmark.y * frame_height,
                    z=landmark.z,
                    visibility=landmark.visibility
                )
        
        return keypoints
    
    def _detect_leaning(self, keypoints: Dict[str, PoseKeypoint]) -> Tuple[bool, float]:
        """
        Detect if student is leaning (forward or sideways)
        Severe: shoulder moved > 15cm from neutral position
        """
        if "left_shoulder" not in keypoints or "right_shoulder" not in keypoints:
            return False, 0.0
        
        left_shoulder = keypoints["left_shoulder"]
        right_shoulder = keypoints["right_shoulder"]
        
        # Calculate shoulder tilt angle (should be roughly horizontal)
        shoulder_dx = right_shoulder.x - left_shoulder.x
        shoulder_dy = right_shoulder.y - left_shoulder.y
        
        if shoulder_dx == 0:
            angle = 90.0 if shoulder_dy > 0 else -90.0
        else:
            angle = np.degrees(np.arctan(shoulder_dy / shoulder_dx))
        
        # Normal shoulder angle ~0-5 degrees, leaning if > 15 degrees
        leaning_threshold = 15.0
        is_leaning = abs(angle) > leaning_threshold
        severity = min(abs(angle) / 45.0, 1.0)  # Normalize to 0-1
        
        return is_leaning, severity
    
    def _detect_shoulder_movement(self, keypoints: Dict[str, PoseKeypoint]) -> Tuple[bool, float]:
        """
        Detect excessive shoulder movement (shrugging, fidgeting)
        """
        if "left_shoulder" not in keypoints or "right_shoulder" not in keypoints:
            return False, 0.0
        
        left_shoulder = keypoints["left_shoulder"]
        right_shoulder = keypoints["right_shoulder"]
        
        # Compare shoulder height - they should be level
        shoulder_height_diff = abs(left_shoulder.y - right_shoulder.y)
        
        # Height difference > 30px is suspicious
        threshold = 30.0
        is_moving = shoulder_height_diff > threshold
        severity = min(shoulder_height_diff / 80.0, 1.0)
        
        return is_moving, severity
    
    def _detect_wrist_below_desk(self, keypoints: Dict[str, PoseKeypoint]) -> Tuple[bool, float]:
        """
        Detect if wrists are below desk level (hidden phone usage)
        Critical indicator: wrist below desk + head down
        """
        if "left_wrist" not in keypoints or "right_wrist" not in keypoints:
            return False, 0.0
        
        left_wrist = keypoints["left_wrist"]
        right_wrist = keypoints["right_wrist"]
        
        # Check if wrist is below desk threshold
        left_below = left_wrist.y > self.desk_y
        right_below = right_wrist.y > self.desk_y
        
        # Both wrists below is more suspicious
        wrist_below_factor = sum([left_below, right_below]) / 2.0
        
        # Distance below desk
        left_depth = max(0, left_wrist.y - self.desk_y) if left_below else 0
        right_depth = max(0, right_wrist.y - self.desk_y) if right_below else 0
        avg_depth = (left_depth + right_depth) / 2.0
        
        # Normalize depth (frame_height/4 = very deep)
        severity = min(avg_depth / (self.frame_height / 4.0), 1.0)
        
        is_below = wrist_below_factor > 0.5
        return is_below, severity
    
    def _detect_arm_movement(self, keypoints: Dict[str, PoseKeypoint]) -> Tuple[bool, float]:
        """
        Detect excessive arm movement (reaching, gesturing)
        """
        if not all(k in keypoints for k in ["left_elbow", "right_elbow", "left_shoulder", "right_shoulder"]):
            return False, 0.0
        
        left_elbow = keypoints["left_elbow"]
        right_elbow = keypoints["right_elbow"]
        left_shoulder = keypoints["left_shoulder"]
        right_shoulder = keypoints["right_shoulder"]
        
        # Calculate arm angles (should be mostly along body)
        left_arm_angle = self._calculate_angle(
            left_shoulder, left_elbow, keypoints.get("left_wrist", left_elbow)
        )
        right_arm_angle = self._calculate_angle(
            right_shoulder, right_elbow, keypoints.get("right_wrist", right_elbow)
        )
        
        # Arms extended > 120 degrees is suspicious (should be ~90-110)
        extension_threshold = 120.0
        left_extended = left_arm_angle > extension_threshold
        right_extended = right_arm_angle > extension_threshold
        
        is_moving = left_extended or right_extended
        severity = max((left_arm_angle - 110.0) / 70.0, (right_arm_angle - 110.0) / 70.0, 0.0)
        severity = min(severity, 1.0)
        
        return is_moving, severity
    
    def _detect_hidden_phone(self, keypoints: Dict[str, PoseKeypoint]) -> Tuple[bool, float]:
        """
        Detect hidden phone usage pattern:
        - Wrist below desk
        - Head pitched down
        - Arm bent at suspicious angle
        """
        if not all(k in keypoints for k in ["left_wrist", "right_wrist"]):
            return False, 0.0
        
        left_wrist = keypoints["left_wrist"]
        right_wrist = keypoints["right_wrist"]
        
        # Combined with face mesh pitch would be ideal, but we can check here
        # If wrist is significantly below hip level and arm is bent, it's suspicious
        
        left_below_desk = left_wrist.y > self.desk_y
        right_below_desk = right_wrist.y > self.desk_y
        
        # Check arm bend angle is suspicious (too acute)
        if "left_elbow" in keypoints:
            left_angle = self._calculate_angle(
                keypoints["left_shoulder"],
                keypoints["left_elbow"],
                left_wrist
            )
            left_acute = left_angle < 75.0  # Very bent
        else:
            left_acute = False
        
        if "right_elbow" in keypoints:
            right_angle = self._calculate_angle(
                keypoints["right_shoulder"],
                keypoints["right_elbow"],
                right_wrist
            )
            right_acute = right_angle < 75.0
        else:
            right_acute = False
        
        # Hidden phone likely if: below desk + bent arms
        hidden_likely = (left_below_desk and left_acute) or (right_below_desk and right_acute)
        confidence = 0.7 if hidden_likely else 0.0
        
        return hidden_likely, confidence
    
    def _calculate_angle(self, point1: PoseKeypoint, point2: PoseKeypoint, point3: PoseKeypoint) -> float:
        """
        Calculate angle between three points (point2 is vertex)
        Returns angle in degrees
        """
        a = np.array([point1.x, point1.y])
        b = np.array([point2.x, point2.y])
        c = np.array([point3.x, point3.y])
        
        ba = a - b
        bc = c - b
        
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        cosine_angle = np.clip(cosine_angle, -1, 1)
        angle = np.degrees(np.arccos(cosine_angle))
        
        return angle
    
    def _calculate_confidence(self, landmarks) -> float:
        """Calculate overall confidence of pose detection"""
        if not landmarks:
            return 0.0
        
        # Average visibility of all landmarks
        visibilities = [lm.visibility for lm in landmarks]
        avg_visibility = np.mean(visibilities)
        
        return float(avg_visibility)
    
    def _calculate_anomaly_score(self, analysis: SkeletonAnalysis) -> float:
        """
        Calculate overall anomaly score (0-100)
        Higher score = more suspicious behavior
        """
        if not analysis.detected:
            return 0.0
        
        score = 0.0
        
        # Behavior contributions
        if analysis.leaning_detected:
            score += 15 * analysis.leaning_severity
        
        if analysis.shoulder_movement:
            score += 8 * analysis.shoulder_angle_degrees / 45.0
        
        if analysis.wrist_below_desk:
            score += 20 * analysis.wrist_movement_severity
        
        if analysis.excessive_arm_movement:
            score += 10 * analysis.arm_movement_severity
        
        if analysis.hidden_phone_likely:
            score += 30 * analysis.phone_confidence
        
        # Normalize to 0-100
        score = min(score, 100.0)
        
        return score
    
    def draw_skeleton(self, frame: np.ndarray, analysis: SkeletonAnalysis, draw_anomalies: bool = True) -> np.ndarray:
        """Draw skeleton and detected behaviors on frame"""
        if not analysis.detected:
            return frame
        
        frame_copy = frame.copy()
        
        # Draw keypoints
        for name, keypoint in analysis.keypoints.items():
            if keypoint.visibility > 0.5:
                x, y = int(keypoint.x), int(keypoint.y)
                cv2.circle(frame_copy, (x, y), 5, (0, 255, 0), -1)
        
        # Draw skeleton connections
        connections = [
            ("left_shoulder", "left_elbow"),
            ("left_elbow", "left_wrist"),
            ("right_shoulder", "right_elbow"),
            ("right_elbow", "right_wrist"),
            ("left_shoulder", "left_hip"),
            ("right_shoulder", "right_hip"),
            ("left_hip", "right_hip"),
            ("left_hip", "left_knee"),
            ("left_knee", "left_ankle"),
            ("right_hip", "right_knee"),
            ("right_knee", "right_ankle"),
        ]
        
        for start, end in connections:
            if start in analysis.keypoints and end in analysis.keypoints:
                p1 = analysis.keypoints[start]
                p2 = analysis.keypoints[end]
                if p1.visibility > 0.5 and p2.visibility > 0.5:
                    cv2.line(
                        frame_copy,
                        (int(p1.x), int(p1.y)),
                        (int(p2.x), int(p2.y)),
                        (0, 255, 0),
                        2
                    )
        
        # Draw desk line
        cv2.line(frame_copy, (0, self.desk_y), (frame_copy.shape[1], self.desk_y), (0, 0, 255), 1)
        cv2.putText(frame_copy, "DESK", (5, self.desk_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Draw anomaly indicators
        if draw_anomalies:
            y_offset = 30
            if analysis.leaning_detected:
                cv2.putText(frame_copy, f"LEANING: {analysis.leaning_severity:.1%}", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_offset += 30
            
            if analysis.wrist_below_desk:
                cv2.putText(frame_copy, f"WRIST BELOW DESK: {analysis.wrist_movement_severity:.1%}", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_offset += 30
            
            if analysis.hidden_phone_likely:
                cv2.putText(frame_copy, f"HIDDEN PHONE: {analysis.phone_confidence:.1%}", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_offset += 30
            
            if analysis.excessive_arm_movement:
                cv2.putText(frame_copy, f"ARM MOVEMENT: {analysis.arm_movement_severity:.1%}", (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Draw anomaly score
        cv2.putText(frame_copy, f"ANOMALY: {analysis.anomaly_score:.0f}/100", 
                   (frame_copy.shape[1] - 300, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        return frame_copy
    
    def release(self):
        """Release resources"""
        self.pose.close()
