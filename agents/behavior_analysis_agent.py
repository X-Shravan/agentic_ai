from __future__ import annotations

import time
import cv2
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Tuple
import mediapipe as mp
import math


# -------------------------------------------------
# GLOBAL PERSISTENT COUNTERS (for backend API)
# -------------------------------------------------
# These persist across HTTP requests and frames
GLOBAL_LOOK_AROUND_COUNT = defaultdict(int)
GLOBAL_LOOK_COPY_COUNT = defaultdict(int)
GLOBAL_LEAN_FRAME_COUNT = defaultdict(int)
GLOBAL_SHARING_COUNT = defaultdict(int)
GLOBAL_LAST_STATUS = defaultdict(str)
GLOBAL_LAST_ALERT_TIME = defaultdict(float)
GLOBAL_LOOK_AROUND_START_TIME = defaultdict(float)
GLOBAL_LOOK_COPY_START_TIME = defaultdict(float)
GLOBAL_STATUS_HISTORY = defaultdict(lambda: deque(maxlen=5))
GLOBAL_CONFIRMED_STATUS = defaultdict(str)
GLOBAL_SHARING_PAIRS = defaultdict(int)
GLOBAL_HEAD_POSITIONS = {}

# -------------------------------------------------
# Behavior Event
# -------------------------------------------------
@dataclass
class BehaviorEvent:
    event_type: str
    confidence: float
    timestamp: float
    situation: str = ""


# -------------------------------------------------
# Behavior Analysis Agent (IMPROVED VERSION)
# -------------------------------------------------
class BehaviorAnalysisAgent:
    """
    Advanced behavior detection with proper thresholds, counter decay,
    sharing detection, and priority-based alert system.
    """

    def __init__(self, config):
        # ========== THRESHOLDS PER SPECIFICATION ==========
        
        # 📱 MOBILE DETECTION
        self.MOBILE_CONF_THRESHOLD = 0.60
        self.MOBILE_AREA_THRESHOLD = 7000
        self.MOBILE_ASPECT_RATIO_MIN = 1.4
        self.MOBILE_ASPECT_RATIO_MAX = 2.5
        
        # 👀 LOOKING AROUND (PER SPEC)
        self.LOOK_AROUND_YAW = 20  # if abs(yaw) > 20
        self.LOOK_AROUND_COUNT_THRESHOLD = 3  # if count >= 3
        self.LOOK_AROUND_TIME_THRESHOLD = 1.0  # seconds
        
        # 📄 LOOKING TO COPY (PER SPEC)
        self.LOOK_COPY_PITCH = 15  # if pitch > 15
        self.LOOK_COPY_YAW = 10  # AND abs(yaw) > 10
        self.LOOK_COPY_COUNT_THRESHOLD = 3  # if count >= 3
        self.LOOK_COPY_TIME_THRESHOLD = 1.0  # seconds
        
        # 📏 LEANING (PER SPEC)
        self.LEAN_SHOULDER_DIFF = 10  # if shoulder_tilt > 10 (normalized to 0-100)
        self.LEAN_FRAMES_THRESHOLD = 15  # if frames >= 15
        
        # 🤝 SHARING DETECTION THRESHOLDS
        self.SHARING_DISTANCE_THRESHOLD = 150  # pixels
        self.SHARING_YAW_THRESHOLD = 25  # degrees (opposite direction)
        self.SHARING_COUNT_THRESHOLD = 3
        
        # ✅ STABILITY CHECK (NEW - IMPORTANT!)
        self.STABILITY_FRAMES = 3  # Must confirm behavior for 3+ frames before alert
        
        # Counter decay rate (gradual reset, not instant)
        self.COUNTER_DECAY = 1

        # Per-person state tracking
        # ✅ USE GLOBAL COUNTERS FOR PERSISTENCE ACROSS API REQUESTS
        self.look_around_count = GLOBAL_LOOK_AROUND_COUNT
        self.look_copy_count = GLOBAL_LOOK_COPY_COUNT
        self.lean_frame_count = GLOBAL_LEAN_FRAME_COUNT
        self.last_status = GLOBAL_LAST_STATUS
        self.last_alert_time = GLOBAL_LAST_ALERT_TIME
        self.alert_cooldown = 2.0  # seconds between same alerts
        
        # ⏱️ TIME-BASED TRACKING (NEW!)
        self.look_around_start_time = GLOBAL_LOOK_AROUND_START_TIME
        self.look_copy_start_time = GLOBAL_LOOK_COPY_START_TIME
        
        # 🔄 STABILITY TRACKING (NEW!)
        self.status_history = GLOBAL_STATUS_HISTORY
        self.confirmed_status = GLOBAL_CONFIRMED_STATUS
        
        # 🤝 SHARING DETECTION STATE
        self.sharing_count = GLOBAL_SHARING_COUNT
        self.head_positions = GLOBAL_HEAD_POSITIONS
        self.sharing_pairs = GLOBAL_SHARING_PAIRS

        # ✅ INITIALIZE MEDIAPIPE MODELS FOR BEHAVIOR DETECTION
        try:
            # Face Mesh - for head pose detection
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=10,
                min_detection_confidence=0.5
            )
            self.mp_face = True
            print("✅ MediaPipe FaceMesh initialized for head pose detection")
        except Exception as e:
            print(f"⚠️ FaceMesh initialization failed: {e}")
            self.face_mesh = None
            self.mp_face = False
        
        try:
            # Pose - for shoulder/leaning detection
            self.pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=0,  # 0=lite, 1=full (faster=lite)
                min_detection_confidence=0.5
            )
            self.mp_pose = True
            print("✅ MediaPipe Pose initialized for shoulder/lean detection")
        except Exception as e:
            print(f"⚠️ Pose initialization failed: {e}")
            self.pose = None
            self.mp_pose = False
        
        if not (self.mp_face and self.mp_pose):
            print("⚠️ INFO: Some MediaPipe models unavailable - using partial detection")

        self.config = config

    # -------------------------------------------------
    # HEAD POSE ANALYSIS
    # -------------------------------------------------
    def get_head_pose(self, face_landmarks, w, h) -> Tuple[float, float]:
        """
        Calculate head yaw and pitch from face landmarks.
        Returns: (yaw, pitch) in normalized coordinates
        """
        left_eye = face_landmarks.landmark[33]  # Left eye outer corner
        right_eye = face_landmarks.landmark[263]  # Right eye outer corner
        nose = face_landmarks.landmark[1]  # Nose tip

        lx = left_eye.x * w
        rx = right_eye.x * w
        nx = nose.x * w
        
        ly = left_eye.y * h
        ny = nose.y * h

        # Yaw: horizontal head rotation (left-right)
        eye_center_x = (lx + rx) / 2
        yaw = (nx - eye_center_x) / (w / 2) * 90  # Approximate degrees

        # Pitch: vertical head rotation (up-down)
        pitch = (ny - ly) / (h / 2) * 90  # Approximate degrees

        return yaw, pitch

    # -------------------------------------------------
    # SHOULDER ANALYSIS (LEANING)
    # -------------------------------------------------
    def get_shoulder_tilt(self, pose_landmarks) -> float:
        """
        Calculate shoulder tilt from pose landmarks.
        Returns: shoulder tilt on 0-100 scale (matches specification)
        """
        try:
            lm = pose_landmarks.landmark
            left_shoulder_y = lm[11].y
            right_shoulder_y = lm[12].y
            # Scale to 0-100
            return abs(left_shoulder_y - right_shoulder_y) * 100
        except:
            return 0

    # -------------------------------------------------
    # 🤝 SHARING DETECTION (MULTIPLE PERSONS)
    # -------------------------------------------------
    def detect_sharing(self, tracks: List[object]) -> Dict[int, bool]:
        """
        Detect when students are sharing answers based on:
        - Distance between persons
        - Opposite head directions (yaw)
        
        Returns: {track_id: is_sharing}
        """
        sharing_flags = defaultdict(bool)
        
        # Get all head positions from previous frame
        current_positions = {}
        
        if len(self.head_positions) < 2:
            return sharing_flags
        
        # Get track IDs and calculate distances between pairs
        track_ids = list(self.head_positions.keys())
        
        for i, tid1 in enumerate(track_ids):
            for tid2 in track_ids[i+1:]:
                pos1 = self.head_positions.get(tid1)
                pos2 = self.head_positions.get(tid2)
                
                if not pos1 or not pos2:
                    continue
                
                # Calculate distance between head centers
                x1, y1, yaw1 = pos1
                x2, y2, yaw2 = pos2
                
                distance = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
                yaw_diff = abs(yaw1 - yaw2)
                
                # Sharing condition: close + opposite direction
                if distance < self.SHARING_DISTANCE_THRESHOLD:
                    # Check if heads are facing opposite directions
                    # (high yaw difference = opposite directions)
                    if yaw_diff > self.SHARING_YAW_THRESHOLD:
                        pair_key = tuple(sorted([tid1, tid2]))
                        self.sharing_pairs[pair_key] += 1
                        
                        if self.sharing_pairs[pair_key] >= self.SHARING_COUNT_THRESHOLD:
                            sharing_flags[tid1] = True
                            sharing_flags[tid2] = True
                    else:
                        # Reset if conditions not met
                        pair_key = tuple(sorted([tid1, tid2]))
                        self.sharing_pairs[pair_key] = max(0, self.sharing_pairs[pair_key] - 1)
        
        return sharing_flags

    # -------------------------------------------------
    # COUNTER DECAY (NO INSTANT RESET)
    # -------------------------------------------------
    def decay_counter(self, current_val: int, decay_rate: int = 1) -> int:
        """Gradual counter decay instead of instant reset"""
        return max(0, current_val - decay_rate)

    # -------------------------------------------------
    # ✅ ASPECT RATIO CHECK (NEW - MOBILE VALIDATION)
    # -------------------------------------------------
    def is_valid_phone_shape(self, obj_bbox) -> bool:
        """
        Check if detected object has phone-like aspect ratio.
        Phones are taller than wide (~1.5-2.5 ratio).
        Papers are wider (~0.7-1.0 ratio).
        
        Returns: True if aspect ratio matches phone shape
        """
        try:
            x1, y1, x2, y2 = obj_bbox
            width = max(1, x2 - x1)
            height = max(1, y2 - y1)
            aspect_ratio = height / width
            
            # Valid phone ratio: 1.5 (tall) to 2.5 (very tall)
            is_valid = self.MOBILE_ASPECT_RATIO_MIN <= aspect_ratio <= self.MOBILE_ASPECT_RATIO_MAX
            
            return is_valid
        except:
            return False

    # -------------------------------------------------
    # ⏱️ TIME-BASED CONDITION CHECK (NEW)
    # -------------------------------------------------
    def has_condition_lasted(self, tid: int, condition_name: str, current_time: float, duration: float) -> bool:
        """
        Check if a condition has been sustained for the required duration.
        
        Args:
            tid: Track ID
            condition_name: "look_around", "look_copy", etc.
            current_time: Current timestamp
            duration: Required duration in seconds
        
        Returns: True if condition held for duration seconds
        """
        start_time_attr = f"{condition_name}_start_time"
        start_times = getattr(self, start_time_attr, defaultdict(float))
        
        if start_times[tid] == 0:
            # First time this condition detected
            start_times[tid] = current_time
            setattr(self, start_time_attr, start_times)
            return False
        
        elapsed = current_time - start_times[tid]
        return elapsed >= duration

    # -------------------------------------------------
    # ✅ STABILITY CHECK (NEW - CONFIRM ALERTS)
    # -------------------------------------------------
    def is_status_stable(self, tid: int, status: str) -> bool:
        """
        Check if status is stable (same for 3+ frames).
        Prevents one-frame false positives.
        
        Returns: True if status confirmed for STABILITY_FRAMES frames
        """
        self.status_history[tid].append(status)
        
        # If not enough history, not stable yet
        if len(self.status_history[tid]) < self.STABILITY_FRAMES:
            return False
        
        # Check if last STABILITY_FRAMES entries are the same
        recent = list(self.status_history[tid])[-self.STABILITY_FRAMES:]
        is_stable = all(s == status for s in recent)
        
        return is_stable

    # -------------------------------------------------
    # STATUS DETERMINATION (IMPROVED & STRICTER)
    # -------------------------------------------------
    def determine_status(
        self,
        tid: int,
        mobile: bool,
        mobile_conf: float,
        mobile_bbox: Tuple = None,
        yaw: float = 0,
        pitch: float = 0,
        shoulder_tilt: float = 0,
        sharing: bool = False,
        current_time: float = 0
    ) -> Tuple[str, float, bool]:
        """
        SIMPLIFIED Priority system per specification:
        
        1. if mobile: Using Mobile 🚨
        2. elif sharing: Sharing Answers 🤝
        3. elif copy_count >= 3: Looking to Copy 🚨
        4. elif look_count >= 3: Looking Around 👀
        5. elif lean_frames >= 15: Leaning ↘️
        6. else: Normal
        """
        
        # ===== PRIORITY 1: MOBILE DETECTION =====
        if mobile and mobile_conf >= self.MOBILE_CONF_THRESHOLD:
            if mobile_bbox and self.is_valid_phone_shape(mobile_bbox):
                return "Using Mobile 🚨", mobile_conf, True
        
        # ===== PRIORITY 2: SHARING ANSWERS =====
        if sharing:
            return "Sharing Answers 🤝", 0.90, True
        
        # Update counters based on conditions (NO complex time checks)
        
        # LOOKING TO COPY: if pitch > 15 AND abs(yaw) > 10
        if abs(pitch) > self.LOOK_COPY_PITCH and abs(yaw) > self.LOOK_COPY_YAW:
            self.look_copy_count[tid] += 1
        else:
            self.look_copy_count[tid] = self.decay_counter(self.look_copy_count[tid])
        
        # LOOKING AROUND: if abs(yaw) > 20
        if abs(yaw) > self.LOOK_AROUND_YAW:
            self.look_around_count[tid] += 1
        else:
            self.look_around_count[tid] = self.decay_counter(self.look_around_count[tid])
        
        # LEANING: if shoulder_tilt > 10
        if shoulder_tilt > self.LEAN_SHOULDER_DIFF:
            self.lean_frame_count[tid] += 1
        else:
            self.lean_frame_count[tid] = self.decay_counter(self.lean_frame_count[tid])
        
        # ===== PRIORITY 3: LOOKING TO COPY =====
        if self.look_copy_count[tid] >= self.LOOK_COPY_COUNT_THRESHOLD:
            return "Looking to Copy 🚨", 0.85, True
        
        # ===== PRIORITY 4: LOOKING AROUND =====
        if self.look_around_count[tid] >= self.LOOK_AROUND_COUNT_THRESHOLD:
            return "Looking Around 👀", 0.70, False
        
        # ===== PRIORITY 5: LEANING =====
        if self.lean_frame_count[tid] >= self.LEAN_FRAMES_THRESHOLD:
            return "Leaning ↘️", 0.60, False
        
        # ===== PRIORITY 6: NORMAL =====
        return "Normal", 0.0, False

    # -------------------------------------------------
    # MAIN ANALYSIS
    # -------------------------------------------------
    def analyze(self, frame, tracks: List[object], detections: List = None) -> Dict[int, List[BehaviorEvent]]:
        """
        Analyze behavior for all detected tracks.
        
        Args:
            frame: Video frame
            tracks: Tracked persons
            detections: YOLO detections (for mobile/book detection)
        
        Returns: {track_id: [BehaviorEvent]}
        """
        if detections is None:
            detections = []
        
        results = {}
        current_time = time.time()
        h, w = frame.shape[:2]
        
        # ✅ DEBUG: Show frame processing
        print(f"\n[ANALYZE] Processing {len(tracks)} tracks, {len(detections)} detections")
        
        # ✅ STORE HEAD POSITIONS FOR SHARING DETECTION
        self.head_positions.clear()
        
        # Check for mobile/book in detections
        mobile_in_frame = False
        for det in detections:
            if det.class_name == "cell phone":
                mobile_in_frame = True
                break

        # First pass: extract all head positions and analyze individual behavior
        for track in tracks:
            tid = track.track_id
            x1, y1, x2, y2 = map(int, track.bbox)
            
            # Calculate head center (approximate)
            head_x = (x1 + x2) // 2
            head_y = y1 + (y2 - y1) // 4  # Head is in upper part
            
            # Extract ROI
            roi = frame[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            # Resize for MediaPipe processing
            roi_resized = cv2.resize(roi, (320, 240))
            rgb = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2RGB)

            # Get face and pose analysis
            face_res = self.face_mesh.process(rgb) if self.face_mesh else None
            pose_res = self.pose.process(rgb) if self.pose else None

            yaw, pitch = 0, 0
            shoulder_tilt = 0

            # Extract head pose
            if face_res and face_res.multi_face_landmarks:
                for face_landmarks in face_res.multi_face_landmarks:
                    yaw, pitch = self.get_head_pose(face_landmarks, 320, 240)
                    break

            # Extract shoulder tilt
            if pose_res and pose_res.pose_landmarks:
                shoulder_tilt = self.get_shoulder_tilt(pose_res.pose_landmarks)
            
            # ✅ STORE HEAD POSITION FOR SHARING DETECTION
            self.head_positions[tid] = (head_x, head_y, yaw)

            # 🔥 Check for objects (mobile phone + book)
            mobile_detected = False
            mobile_conf = 0.0
            mobile_bbox = None
            mobile_area = 0
            
            book_detected = False  # ✅ NEW: Track if book is detected (NOT cheating)
            
            for obj in getattr(track, "objects_detected", []):
                obj_class = obj.get("class_name", "")
                
                # ✅ BOOK HANDLING - Mark as normal (NOT cheating)
                if obj_class == "book":
                    book_detected = True
                    print(f"📚 BOOK: Student ID {tid} - NO ALERT")
                    continue
                
                # 🔥 MOBILE PHONE HANDLING (only flag phone, not book)
                if obj_class == "cell phone":
                    mobile_conf = obj.get("confidence", 0.0)
                    obj_box = obj.get("bbox", (0, 0, 0, 0))
                    if len(obj_box) >= 4:
                        obj_area = (obj_box[2] - obj_box[0]) * (obj_box[3] - obj_box[1])
                        mobile_area = obj_area
                        # Only mark as mobile if it passed geometric validation in detection
                        if mobile_conf >= self.MOBILE_CONF_THRESHOLD and mobile_area > self.MOBILE_AREA_THRESHOLD:
                            mobile_detected = True
                            mobile_bbox = obj_box
                            print(f"📱 MOBILE: Student ID {tid} - ALERT")
                    break

            # ✅ IMPROVED: Determine status with all new parameters
            status, confidence, is_alert = self.determine_status(
                tid=tid,
                mobile=mobile_detected,
                mobile_conf=mobile_conf,
                mobile_bbox=mobile_bbox,
                yaw=yaw,
                pitch=pitch,
                shoulder_tilt=shoulder_tilt,
                sharing=False,  # Will update in second pass
                current_time=current_time
            )
            
            # ✅ DEBUG OUTPUT - Print counter state
            print(f"[DEBUG] ID: {tid} | Status: {status} | " +
                  f"Look_Count: {self.look_around_count[tid]} | " +
                  f"Copy_Count: {self.look_copy_count[tid]} | " +
                  f"Lean_Frames: {self.lean_frame_count[tid]} | " +
                  f"Yaw: {yaw:.1f}° Pitch: {pitch:.1f}° Shoulder: {shoulder_tilt:.1f}")
            
            # ✅ BOOK OVERRIDE: If book detected, force normal status
            if book_detected and not mobile_detected:
                status = "normal"
                is_alert = False
                confidence = 1.0

            # Store for output
            self.last_status[tid] = status

            # Create event
            event = BehaviorEvent(
                event_type="Alert 🚨" if is_alert else "Suspicious" if "👀" in status or "↘️" in status else "Normal",
                confidence=confidence,
                timestamp=current_time,
                situation=status
            )
            results[tid] = [event]
        
        # ✅ SECOND PASS: DETECT SHARING ANSWERS
        sharing_flags = self.detect_sharing(tracks)
        
        # ✅ UPDATE STATUS IF SHARING DETECTED
        for tid in results:
            if sharing_flags.get(tid, False):
                status, confidence, is_alert = "Sharing Answers 🤝", 0.90, True
                self.last_status[tid] = status
                event = BehaviorEvent(
                    event_type="Alert 🚨",
                    confidence=confidence,
                    timestamp=current_time,
                    situation=status
                )
                results[tid] = [event]
                print(f"🤝 SHARING DETECTED: ID {tid}")

        return results

    # -------------------------------------------------
    # GET COUNTER STATS (for debugging)
    # -------------------------------------------------
    def get_counter_stats(self) -> Dict:
        """Return current counter state for all tracked students"""
        stats = {}
        all_ids = set(self.look_around_count.keys()) | set(self.look_copy_count.keys()) | set(self.lean_frame_count.keys())
        
        for tid in all_ids:
            stats[tid] = {
                "look_around": self.look_around_count.get(tid, 0),
                "look_copy": self.look_copy_count.get(tid, 0),
                "lean_frames": self.lean_frame_count.get(tid, 0),
                "status": self.last_status.get(tid, "Unknown")
            }
        
        return stats

    # -------------------------------------------------
    # RESET
    # -------------------------------------------------
    def reset(self):
        """Reset all tracking data"""
        self.look_around_count.clear()
        self.look_copy_count.clear()
        self.lean_frame_count.clear()
        self.last_status.clear()
        self.last_alert_time.clear()
        self.head_positions.clear()
        self.sharing_pairs.clear()
        
        # ✅ NEW: Clear time-based and stability tracking
        self.look_around_start_time.clear()
        self.look_copy_start_time.clear()
        self.status_history.clear()
        self.confirmed_status.clear()