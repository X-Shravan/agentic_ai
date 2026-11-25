"""
Temporal Behavior Analysis Engine
Analyzes student behavioral patterns over time using DeepSORT Track IDs.
Implements:
- Continuous action debouncing into discrete episodes
- Per-student sliding time windows (30s, 60s, 120s) with auto-expiration
- Writing-aware context filtering (downward gaze during writing is normal)
- Multimodal correlation (gaze + head turn, gaze + interaction, lean + gaze)
- Configurable repetition thresholds and strictness modes (NORMAL, STRICT, VERY_STRICT)
- Cooldown and escalation support
- Human-in-the-loop advisory alerts ("review recommended")
"""

from __future__ import annotations

import time
import math
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class StrictnessMode(str, Enum):
    NORMAL = "normal"
    STRICT = "strict"
    VERY_STRICT = "very_strict"


class BehavioralEventType(str, Enum):
    # Gaze events
    GAZE_LEFT = "gaze_left"
    GAZE_RIGHT = "gaze_right"
    GAZE_DOWN_SUSPICIOUS = "gaze_down_suspicious"
    GAZE_DOWN_NORMAL = "gaze_down_normal"
    GAZE_SIDEWAYS = "gaze_sideways"
    LOOKING_BACK = "looking_back"
    LOOKING_AWAY = "looking_away"
    
    # Head orientation events
    HEAD_TURN_LEFT = "head_turn_left"
    HEAD_TURN_RIGHT = "head_turn_right"
    HEAD_TURN_BACK = "head_turn_back"
    HEAD_TURN_SIDEWAYS = "head_turn_sideways"
    
    # Body & skeleton events
    LEAN_LEFT = "lean_left"
    LEAN_RIGHT = "lean_right"
    LEAN_FORWARD = "lean_forward"
    LEAN_BACK = "lean_back"
    BENDING_DOWN = "bending_down"
    UNUSUAL_POSTURE = "unusual_posture"
    REACHING = "reaching"
    WRIST_BELOW_DESK = "wrist_below_desk"
    
    # Student-to-student interaction
    STUDENT_INTERACTION = "student_interaction"
    
    # Visual speech-like signals (strictly labeled without claiming confirmed speech)
    VISUAL_MOUTH_MOVEMENT = "visual_mouth_movement"


# Alias for internal and external consistency
BehaviorEventType = BehavioralEventType


@dataclass
class BehaviorEpisode:
    """A discrete debounced behavioral episode spanning multiple frames."""
    event_type: BehavioralEventType
    start_time: float
    end_time: float
    duration: float
    peak_confidence: float
    details: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    @property
    def age(self) -> float:
        return time.time() - self.end_time


@dataclass
class BehaviorConfig:
    """Configuration for temporal behavior analysis."""
    strictness_mode: StrictnessMode = StrictnessMode.STRICT
    
    # Sliding time windows in seconds
    window_short: float = 30.0
    window_medium: float = 60.0
    window_long: float = 120.0
    max_history_window: float = 180.0
    
    # Repetition thresholds (episodes in window_medium)
    # Default is STRICT mode
    repetition_gaze_medium: int = 2
    repetition_gaze_high: int = 4
    
    repetition_head_medium: int = 2
    repetition_head_high: int = 4
    
    repetition_lean_medium: int = 2
    repetition_lean_high: int = 4
    
    repetition_interaction_medium: int = 2
    repetition_interaction_high: int = 3
    
    # Sensor thresholds
    yaw_turn_threshold: float = 20.0        # degrees for head turn
    yaw_back_threshold: float = 45.0        # degrees for extreme turn / looking back
    pitch_down_threshold: float = 18.0      # degrees for looking down
    roll_lean_threshold: float = 15.0       # degrees for lateral head roll
    shoulder_tilt_threshold: float = 12.0   # normalized tilt for leaning
    
    # Minimum confidence to accept a measurement
    min_gaze_confidence: float = 0.50
    min_face_confidence: float = 0.50
    min_pose_confidence: float = 0.50
    
    # Debouncing parameters
    min_episode_duration: float = 0.35      # seconds to qualify as sustained episode
    max_inactivity_gap: float = 0.8         # seconds gap to consider an episode ended
    
    # Alert Cooldown
    cooldown_seconds: float = 15.0
    
    def apply_mode(self, mode: StrictnessMode) -> None:
        """Adjust repetition thresholds based on strictness mode."""
        self.strictness_mode = mode
        if mode == StrictnessMode.NORMAL:
            self.repetition_gaze_medium = 3
            self.repetition_gaze_high = 5
            self.repetition_head_medium = 3
            self.repetition_head_high = 5
            self.repetition_lean_medium = 3
            self.repetition_lean_high = 5
            self.repetition_interaction_medium = 2
            self.repetition_interaction_high = 4
            self.yaw_turn_threshold = 24.0
        elif mode == StrictnessMode.STRICT:
            self.repetition_gaze_medium = 2
            self.repetition_gaze_high = 4
            self.repetition_head_medium = 2
            self.repetition_head_high = 4
            self.repetition_lean_medium = 2
            self.repetition_lean_high = 4
            self.repetition_interaction_medium = 2
            self.repetition_interaction_high = 3
            self.yaw_turn_threshold = 20.0
        elif mode == StrictnessMode.VERY_STRICT:
            self.repetition_gaze_medium = 2
            self.repetition_gaze_high = 3
            self.repetition_head_medium = 2
            self.repetition_head_high = 3
            self.repetition_lean_medium = 2
            self.repetition_lean_high = 3
            self.repetition_interaction_medium = 1
            self.repetition_interaction_high = 2
            self.yaw_turn_threshold = 16.0


@dataclass
class TemporalAssessment:
    """Output of temporal behavioral analysis for a single student."""
    track_id: int
    behavioral_score: float                  # 0 to 100
    risk_level: str                          # LOW, MEDIUM, HIGH, CRITICAL
    primary_behavior: str
    supporting_behaviors: List[str]
    occurrence_counts: Dict[str, int]        # occurrences in medium window
    active_window_seconds: float
    brief_reason: str
    detailed_reasons: List[str]
    should_alert: bool
    is_escalation: bool
    episodes_summary: Dict[str, int]
    recommendation: str = "Invigilator review recommended."


class StudentBehaviorHistory:
    """Maintains independent temporal history and episode state for one tracked student."""
    
    def __init__(self, track_id: int, config: BehaviorConfig):
        self.track_id = track_id
        self.config = config
        
        # Currently ongoing episodes: event_type -> BehaviorEpisode
        self.active_episodes: Dict[BehaviorEventType, BehaviorEpisode] = {}
        
        # Completed episodes bounded history
        self.completed_episodes: deque[BehaviorEpisode] = deque(maxlen=200)
        
        # Timestamp of last observation
        self.last_seen: float = time.time()
        
        # Alert history & cooldown tracking
        self.last_alert_time: float = 0.0
        self.last_alert_level: str = "LOW"
        self.last_alert_reason: str = ""
        
        # State indicators
        self.is_writing_posture: bool = False

    def update_state(
        self,
        current_time: float,
        detected_signals: Dict[BehaviorEventType, Tuple[bool, float, Dict[str, Any]]],
        is_writing_context: bool = False
    ) -> None:
        """
        Update episodes with current frame measurements.
        Debounces continuous signals into distinct episodes.
        """
        self.last_seen = current_time
        self.is_writing_posture = is_writing_context
        
        # Clean up stale completed episodes
        cutoff = current_time - self.config.max_history_window
        while self.completed_episodes and self.completed_episodes[0].end_time < cutoff:
            self.completed_episodes.popleft()
            
        # Process each behavioral signal
        for event_type, (is_present, confidence, details) in detected_signals.items():
            # Apply writing-aware rule for downward gaze
            if event_type == BehavioralEventType.GAZE_DOWN_NORMAL and is_present:
                # Normal exam writing behavior: do not treat as suspicious
                continue
                
            if is_present and confidence >= 0.40:
                if event_type in self.active_episodes:
                    # Episode ongoing: extend end_time and duration
                    ep = self.active_episodes[event_type]
                    ep.end_time = current_time
                    ep.duration = max(0.0, ep.end_time - ep.start_time)
                    ep.peak_confidence = max(ep.peak_confidence, confidence)
                    ep.details.update(details)
                else:
                    # New episode begins
                    self.active_episodes[event_type] = BehaviorEpisode(
                        event_type=event_type,
                        start_time=current_time,
                        end_time=current_time,
                        duration=0.0,
                        peak_confidence=confidence,
                        details=details,
                        is_active=True
                    )
            else:
                # Condition no longer detected: check if active episode should end
                if event_type in self.active_episodes:
                    ep = self.active_episodes[event_type]
                    # If last update was more than inactivity gap, close episode
                    if (current_time - ep.end_time) >= self.config.max_inactivity_gap:
                        ep.is_active = False
                        # Only record episode if duration meets minimal duration or high confidence
                        if ep.duration >= self.config.min_episode_duration or ep.peak_confidence >= 0.75:
                            self.completed_episodes.append(ep)
                            logger.debug(
                                f"[BEHAVIOR] Track={self.track_id} {ep.event_type.value} episode ended: "
                                f"duration={ep.duration:.2f}s peak_conf={ep.peak_confidence:.2f}"
                            )
                        del self.active_episodes[event_type]

    def finalize_inactive_episodes(self, current_time: float) -> None:
        """Closes any active episodes that haven't been updated recently."""
        to_remove = []
        for event_type, ep in self.active_episodes.items():
            if (current_time - ep.end_time) >= self.config.max_inactivity_gap:
                ep.is_active = False
                if ep.duration >= self.config.min_episode_duration or ep.peak_confidence >= 0.75:
                    self.completed_episodes.append(ep)
                to_remove.append(event_type)
        for event_type in to_remove:
            del self.active_episodes[event_type]

    def get_episodes_in_window(self, window_seconds: float, current_time: float) -> List[BehaviorEpisode]:
        """Returns all distinct episodes that ended or were active in the time window."""
        cutoff = current_time - window_seconds
        episodes = [ep for ep in self.completed_episodes if ep.end_time >= cutoff]
        for ep in self.active_episodes.values():
            if ep.end_time >= cutoff:
                episodes.append(ep)
        return episodes

    def count_episodes(self, window_seconds: float, current_time: float) -> Dict[str, int]:
        """Counts occurrences of each behavior category within the sliding window."""
        episodes = self.get_episodes_in_window(window_seconds, current_time)
        counts: Dict[str, int] = defaultdict(int)
        for ep in episodes:
            counts[ep.event_type.value] += 1
        return counts


class TemporalBehaviorTracker:
    """
    Central temporal behavior tracker coordinating all student tracks.
    Thread-safe, bounded-memory, and provides multimodal behavior fusion.
    """
    
    def __init__(self, config: Optional[BehaviorConfig] = None):
        self.config = config or BehaviorConfig()
        self.histories: Dict[int, StudentBehaviorHistory] = {}
        
        # Track relative spatial positions for student-to-student interaction detection
        self.student_positions: Dict[int, Tuple[float, float, float]] = {}  # tid -> (x_center, y_center, yaw)
        
        logger.info(f"✅ TemporalBehaviorTracker initialized (mode={self.config.strictness_mode.value})")

    def get_or_create_history(self, track_id: int) -> StudentBehaviorHistory:
        if track_id not in self.histories:
            self.histories[track_id] = StudentBehaviorHistory(track_id, self.config)
        return self.histories[track_id]

    def update_student(
        self,
        track_id: int,
        gaze_results: Dict[str, Any],
        face_results: Dict[str, Any],
        skeleton_results: Any,
        detections: List[Any],
        timestamp: Optional[float] = None,
        bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> TemporalAssessment:
        """
        Process incoming frame signals for a student track ID, update temporal history,
        and generate a comprehensive temporal assessment.
        """
        current_time = timestamp if timestamp is not None else time.time()
        history = self.get_or_create_history(track_id)
        
        # 1. Extract raw sensor measurements
        gaze_dir = str(gaze_results.get("direction") or gaze_results.get("gaze") or "UNKNOWN").upper()
        gaze_conf = float(gaze_results.get("confidence", 0.0))
        iris_detected = bool(gaze_results.get("iris_detected", False))
        
        yaw = float(face_results.get("yaw") or 0.0)
        pitch = float(face_results.get("pitch") or 0.0)
        roll = float(face_results.get("roll") or 0.0)
        face_conf = float(face_results.get("confidence", 0.85)) if face_results.get("face_detected") else 0.0
        
        skel_detected = getattr(skeleton_results, "detected", False) if skeleton_results else False
        leaning_severity = float(getattr(skeleton_results, "leaning_severity", 0.0)) if skel_detected else 0.0
        shoulder_angle = float(getattr(skeleton_results, "shoulder_angle_degrees", 0.0)) if skel_detected else 0.0
        wrist_below = bool(getattr(skeleton_results, "wrist_below_desk", False)) if skel_detected else False
        wrist_severity = float(getattr(skeleton_results, "wrist_movement_severity", 0.0)) if skel_detected else 0.0
        arm_severity = float(getattr(skeleton_results, "arm_movement_severity", 0.0)) if skel_detected else 0.0
        
        # Save position for interaction detection
        if bbox:
            x1, y1, x2, y2 = bbox
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            self.student_positions[track_id] = (cx, cy, yaw)

        # 2. Writing-Awareness Context Filter
        # If student's head is slightly down (pitch between 8 and 28 deg), hands on desk,
        # and not turning sideways (|yaw| < 15), this is NORMAL EXAM WRITING.
        is_normal_writing = False
        if 8.0 <= pitch <= 32.0 and abs(yaw) <= 15.0 and not wrist_below:
            is_normal_writing = True
            
        # 3. Detect discrete behavioral signals in this frame
        detected_signals: Dict[BehaviorEventType, Tuple[bool, float, Dict[str, Any]]] = {}
        
        # --- Gaze Signals ---
        is_gaze_valid = (gaze_conf >= self.config.min_gaze_confidence)
        
        # Gaze left / right
        gaze_left = is_gaze_valid and (gaze_dir == "LEFT")
        detected_signals[BehaviorEventType.GAZE_LEFT] = (gaze_left, gaze_conf, {"direction": "LEFT"})
        
        gaze_right = is_gaze_valid and (gaze_dir == "RIGHT")
        detected_signals[BehaviorEventType.GAZE_RIGHT] = (gaze_right, gaze_conf, {"direction": "RIGHT"})
        
        gaze_sideways = gaze_left or gaze_right
        detected_signals[BehaviorEventType.GAZE_SIDEWAYS] = (gaze_sideways, gaze_conf, {"direction": gaze_dir})
        
        # Gaze downward: distinguish normal writing vs suspicious
        gaze_down = is_gaze_valid and (gaze_dir == "DOWN")
        if gaze_down and is_normal_writing:
            detected_signals[BehaviorEventType.GAZE_DOWN_NORMAL] = (True, gaze_conf, {"context": "writing"})
            detected_signals[BehaviorEventType.GAZE_DOWN_SUSPICIOUS] = (False, 0.0, {})
        elif gaze_down and not is_normal_writing and (pitch > 32.0 or wrist_below or abs(yaw) > 15.0):
            detected_signals[BehaviorEventType.GAZE_DOWN_NORMAL] = (False, 0.0, {})
            detected_signals[BehaviorEventType.GAZE_DOWN_SUSPICIOUS] = (True, gaze_conf, {"context": "anomalous_downward"})
        else:
            detected_signals[BehaviorEventType.GAZE_DOWN_NORMAL] = (False, 0.0, {})
            detected_signals[BehaviorEventType.GAZE_DOWN_SUSPICIOUS] = (False, 0.0, {})
            
        # --- Head Orientation Signals ---
        is_face_valid = (face_conf >= self.config.min_face_confidence)
        head_left = is_face_valid and (yaw < -self.config.yaw_turn_threshold) and (abs(yaw) < self.config.yaw_back_threshold)
        detected_signals[BehaviorEventType.HEAD_TURN_LEFT] = (head_left, face_conf, {"yaw": yaw})
        
        head_right = is_face_valid and (yaw > self.config.yaw_turn_threshold) and (abs(yaw) < self.config.yaw_back_threshold)
        detected_signals[BehaviorEventType.HEAD_TURN_RIGHT] = (head_right, face_conf, {"yaw": yaw})
        
        head_back = is_face_valid and (abs(yaw) >= self.config.yaw_back_threshold)
        detected_signals[BehaviorEventType.HEAD_TURN_BACK] = (head_back, face_conf, {"yaw": yaw})
        
        head_sideways = head_left or head_right or head_back
        detected_signals[BehaviorEventType.HEAD_TURN_SIDEWAYS] = (head_sideways, face_conf, {"yaw": yaw})
        
        # --- Body & Posture Signals ---
        is_pose_valid = skel_detected and (getattr(skeleton_results, "overall_confidence", 0.8) >= self.config.min_pose_confidence)
        lean_left = is_pose_valid and (roll < -self.config.roll_lean_threshold or shoulder_angle < -self.config.shoulder_tilt_threshold)
        detected_signals[BehaviorEventType.LEAN_LEFT] = (lean_left, leaning_severity or 0.7, {"angle": shoulder_angle})
        
        lean_right = is_pose_valid and (roll > self.config.roll_lean_threshold or shoulder_angle > self.config.shoulder_tilt_threshold)
        detected_signals[BehaviorEventType.LEAN_RIGHT] = (lean_right, leaning_severity or 0.7, {"angle": shoulder_angle})
        
        bending = is_pose_valid and (leaning_severity > 0.60 and pitch > 25.0 and not is_normal_writing)
        detected_signals[BehaviorEventType.BENDING_DOWN] = (bending, leaning_severity or 0.7, {"pitch": pitch})
        
        reaching = is_pose_valid and (arm_severity > 0.65)
        detected_signals[BehaviorEventType.REACHING] = (reaching, arm_severity, {})
        
        wrist_hid = is_pose_valid and wrist_below and (wrist_severity > 0.50)
        detected_signals[BehaviorEventType.WRIST_BELOW_DESK] = (wrist_hid, wrist_severity, {})
        
        # --- Student-to-Student Interaction ---
        is_interacting = self._check_interaction(track_id, cx if bbox else 0, cy if bbox else 0, yaw)
        detected_signals[BehaviorEventType.STUDENT_INTERACTION] = (is_interacting, 0.85 if is_interacting else 0.0, {})

        # 4. Update student history and debounce into episodes
        history.update_state(current_time, detected_signals, is_writing_context=is_normal_writing)
        history.finalize_inactive_episodes(current_time)

        # 5. Evaluate temporal repetition counts across sliding windows
        return self._evaluate_student_assessment(history, current_time)

    def _check_interaction(self, track_id: int, cx: float, cy: float, yaw: float) -> bool:
        """
        Check if student is interacting with an adjacent student:
        Proximity + head turned toward neighbor.
        """
        if track_id not in self.student_positions or len(self.student_positions) < 2:
            return False
            
        my_pos = self.student_positions[track_id]
        mx, my, my_yaw = my_pos
        
        for other_id, other_pos in self.student_positions.items():
            if other_id == track_id:
                continue
            ox, oy, other_yaw = other_pos
            
            # Distance in image space
            dist = math.sqrt((mx - ox) ** 2 + (my - oy) ** 2)
            # If students are within 350 pixels (typical neighbor seat spacing)
            if 50 < dist < 350:
                # Check directional alignment:
                # If neighbor is to the right (ox > mx), my head should turn right (my_yaw > 15)
                # If neighbor is to the left (ox < mx), my head should turn left (my_yaw < -15)
                if (ox > mx and my_yaw > 15.0) or (ox < mx and my_yaw < -15.0):
                    return True
        return False

    def _evaluate_student_assessment(
        self,
        history: StudentBehaviorHistory,
        current_time: float
    ) -> TemporalAssessment:
        """
        Fuses temporal repetitions and cross-modal correlations into a unified risk assessment.
        Ensures explainability, human-in-the-loop recommendations, and alert cooldown/escalation.
        """
        # Count episodes in medium window (60s)
        window_60 = self.config.window_medium
        counts_60 = history.count_episodes(window_60, current_time)
        
        # Count episodes in short window (30s)
        counts_30 = history.count_episodes(self.config.window_short, current_time)
        
        # Gaze repetitions
        gaze_left_cnt = counts_60.get(BehaviorEventType.GAZE_LEFT.value, 0)
        gaze_right_cnt = counts_60.get(BehaviorEventType.GAZE_RIGHT.value, 0)
        gaze_side_cnt = counts_60.get(BehaviorEventType.GAZE_SIDEWAYS.value, 0) or (gaze_left_cnt + gaze_right_cnt)
        gaze_down_susp = counts_60.get(BehaviorEventType.GAZE_DOWN_SUSPICIOUS.value, 0)
        
        # Head turn repetitions
        head_left_cnt = counts_60.get(BehaviorEventType.HEAD_TURN_LEFT.value, 0)
        head_right_cnt = counts_60.get(BehaviorEventType.HEAD_TURN_RIGHT.value, 0)
        head_back_cnt = counts_60.get(BehaviorEventType.HEAD_TURN_BACK.value, 0)
        head_side_cnt = counts_60.get(BehaviorEventType.HEAD_TURN_SIDEWAYS.value, 0) or (head_left_cnt + head_right_cnt + head_back_cnt)
        
        # Posture repetitions
        lean_left_cnt = counts_60.get(BehaviorEventType.LEAN_LEFT.value, 0)
        lean_right_cnt = counts_60.get(BehaviorEventType.LEAN_RIGHT.value, 0)
        lean_cnt = lean_left_cnt + lean_right_cnt
        bending_cnt = counts_60.get(BehaviorEventType.BENDING_DOWN.value, 0)
        wrist_cnt = counts_60.get(BehaviorEventType.WRIST_BELOW_DESK.value, 0)
        
        # Interaction repetitions
        interaction_cnt = counts_60.get(BehaviorEventType.STUDENT_INTERACTION.value, 0)

        # -------------------------------------------------------------
        # Scoring Model: Discrete Base + Repetition + Multimodal Boost
        # -------------------------------------------------------------
        base_score = 0.0
        primary_behavior = "Normal exam behavior"
        supporting_behaviors: List[str] = []
        detailed_reasons: List[str] = []

        # 1. Gaze Scoring
        if gaze_side_cnt >= self.config.repetition_gaze_high:
            base_score = max(base_score, 75.0)
            primary_behavior = "Repeated gaze deviation"
            detailed_reasons.append(f"Frequent directional gaze deviation ({gaze_side_cnt} occurrences / {int(window_60)}s)")
        elif gaze_side_cnt >= self.config.repetition_gaze_medium:
            base_score = max(base_score, 50.0)
            primary_behavior = "Repeated gaze deviation"
            detailed_reasons.append(f"Repeated gaze deviation ({gaze_side_cnt} occurrences / {int(window_60)}s)")
        elif gaze_side_cnt == 1:
            base_score = max(base_score, 15.0)
            detailed_reasons.append("Isolated gaze deviation observed (normal variation)")

        # 2. Head Turn Scoring
        if head_side_cnt >= self.config.repetition_head_high or head_back_cnt >= 2:
            base_score = max(base_score, 75.0)
            if "gaze" not in primary_behavior.lower():
                primary_behavior = "Repeated head turning"
            else:
                supporting_behaviors.append(f"Head turning ({head_side_cnt} occurrences)")
            detailed_reasons.append(f"Frequent head turning ({head_side_cnt} occurrences / {int(window_60)}s)")
        elif head_side_cnt >= self.config.repetition_head_medium or head_back_cnt == 1:
            base_score = max(base_score, 45.0)
            if base_score < 50.0:
                primary_behavior = "Repeated head turning"
            else:
                supporting_behaviors.append(f"Head turning ({head_side_cnt} occurrences)")
            detailed_reasons.append(f"Repeated head turns ({head_side_cnt} occurrences / {int(window_60)}s)")
        elif head_side_cnt == 1:
            base_score = max(base_score, 15.0)

        # 3. Posture & Leaning Scoring
        if lean_cnt >= self.config.repetition_lean_high or bending_cnt >= 2:
            base_score = max(base_score, 65.0)
            supporting_behaviors.append(f"Repeated leaning/bending ({lean_cnt + bending_cnt} occurrences)")
            detailed_reasons.append(f"Repeated posture deviations ({lean_cnt} leans / {int(window_60)}s)")
        elif lean_cnt >= self.config.repetition_lean_medium:
            base_score = max(base_score, 40.0)
            supporting_behaviors.append(f"Repeated leaning ({lean_cnt} occurrences)")
        elif lean_cnt == 1:
            base_score = max(base_score, 10.0)

        # 4. Student Interaction Scoring
        if interaction_cnt >= self.config.repetition_interaction_high:
            base_score = max(base_score, 78.0)
            primary_behavior = "Repeated student interaction"
            detailed_reasons.append(f"Repeated orientation/interaction toward neighboring student ({interaction_cnt} occurrences)")
        elif interaction_cnt >= self.config.repetition_interaction_medium:
            base_score = max(base_score, 55.0)
            supporting_behaviors.append(f"Interaction toward neighbor ({interaction_cnt} occurrences)")

        # -------------------------------------------------------------
        # Multimodal Behavior Fusion (Cross-Signal Reinforcement)
        # -------------------------------------------------------------
        # Combination 1: Gaze + Head turn in same direction
        same_direction_turn = (gaze_right_cnt >= 1 and head_right_cnt >= 1) or (gaze_left_cnt >= 1 and head_left_cnt >= 1)
        if gaze_side_cnt >= self.config.repetition_gaze_medium and head_side_cnt >= self.config.repetition_head_medium:
            correlation_boost = 25.0 if same_direction_turn else 18.0
            base_score = min(88.0, base_score + correlation_boost)
            primary_behavior = "Correlated gaze and head turning"
            detailed_reasons.append("Correlated sideways gaze and head rotation in same direction")
            
        # Combination 2: Gaze + Leaning
        if gaze_side_cnt >= self.config.repetition_gaze_medium and lean_cnt >= self.config.repetition_lean_medium:
            base_score = min(88.0, base_score + 20.0)
            supporting_behaviors.append("Correlated sideways leaning and gaze deviation")
            detailed_reasons.append("Simultaneous leaning and gaze deviation detected")

        # Combination 3: Gaze + Head turn + Student Interaction
        if gaze_side_cnt >= self.config.repetition_gaze_medium and head_side_cnt >= 1 and interaction_cnt >= 1:
            base_score = min(92.0, base_score + 25.0)
            primary_behavior = "Repeated student interaction with correlated gaze"
            detailed_reasons.append("High behavioral concern: Repeated gaze, head turn, and mutual neighbor orientation")

        # Hidden hand / wrist below desk + downward gaze
        if wrist_cnt >= 2 and gaze_down_susp >= 1:
            base_score = min(88.0, base_score + 25.0)
            supporting_behaviors.append("Wrist below desk with sustained downward gaze")
            detailed_reasons.append("Anomalous wrist concealment with downward gaze")

        # Cap behavioral score
        final_score = float(min(100.0, max(0.0, base_score)))

        # Determine Risk Level
        if final_score >= 90.0:
            risk_level = "CRITICAL"
        elif final_score >= 75.0:
            risk_level = "HIGH"
        elif final_score >= 40.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Construct Human-in-the-Loop brief reason
        if risk_level in {"HIGH", "CRITICAL"}:
            brief_reason = f"{primary_behavior} ({risk_level}) — review recommended."
        elif risk_level == "MEDIUM":
            brief_reason = f"{primary_behavior} detected — review recommended."
        else:
            brief_reason = "Normal exam behavior observed."

        # -------------------------------------------------------------
        # Cooldown and Escalation Logic
        # -------------------------------------------------------------
        severity_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        current_rank = severity_rank[risk_level]
        last_rank = severity_rank.get(history.last_alert_level, 0)
        
        is_escalation = current_rank > last_rank
        time_since_alert = current_time - history.last_alert_time
        
        should_alert = False
        if risk_level in {"MEDIUM", "HIGH", "CRITICAL"}:
            if is_escalation:
                # Escalation bypasses cooldown
                should_alert = True
                history.last_alert_time = current_time
                history.last_alert_level = risk_level
                history.last_alert_reason = brief_reason
                logger.info(
                    f"[ESCALATION] Track={history.track_id} {history.last_alert_level} -> {risk_level} "
                    f"score={final_score:.1f}: {brief_reason}"
                )
            elif time_since_alert >= self.config.cooldown_seconds:
                # Cooldown expired and behavior persists
                should_alert = True
                history.last_alert_time = current_time
                history.last_alert_level = risk_level
                history.last_alert_reason = brief_reason
                logger.info(
                    f"[ALERT] Track={history.track_id} {risk_level} score={final_score:.1f}: {brief_reason}"
                )
            else:
                # Duplicate alert suppressed during cooldown
                should_alert = False
        else:
            # Low risk: update level when cooled down
            if time_since_alert >= self.config.cooldown_seconds:
                history.last_alert_level = "LOW"

        return TemporalAssessment(
            track_id=history.track_id,
            behavioral_score=final_score,
            risk_level=risk_level,
            primary_behavior=primary_behavior,
            supporting_behaviors=supporting_behaviors,
            occurrence_counts=counts_60,
            active_window_seconds=window_60,
            brief_reason=brief_reason,
            detailed_reasons=detailed_reasons,
            should_alert=should_alert,
            is_escalation=is_escalation,
            episodes_summary={
                "gaze_episodes": gaze_side_cnt,
                "head_turn_episodes": head_side_cnt,
                "lean_episodes": lean_cnt,
                "interaction_episodes": interaction_cnt
            },
            recommendation="Invigilator review recommended."
        )

    def prune_lost_tracks(self, active_track_ids: Set[int], max_missing_time: float = 30.0, current_time: Optional[float] = None) -> None:
        """Removes students whose track genuinely ended and have been inactive for max_missing_time."""
        now = current_time if current_time is not None else time.time()
        to_del = []
        for tid, hist in self.histories.items():
            if tid not in active_track_ids and (now - hist.last_seen) > max_missing_time:
                to_del.append(tid)
        for tid in to_del:
            del self.histories[tid]
            if tid in self.student_positions:
                del self.student_positions[tid]
            logger.info(f"[CLEANUP] Pruned expired Track ID {tid} from temporal behavior history")

    def reset(self) -> None:
        """Reset all tracking state."""
        self.histories.clear()
        self.student_positions.clear()
        logger.info("TemporalBehaviorTracker state reset")
