"""
Multi-Modal Fusion Engine
Combines face mesh, gaze tracking, body pose, and phone detection
into unified confidence scores and risk assessment
"""

from __future__ import annotations
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import logging
from collections import deque

from backend.agents.temporal_behavior import (
    BehaviorConfig,
    BehavioralEventType,
    StrictnessMode,
    TemporalAssessment,
    TemporalBehaviorTracker,
)

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FusionInput:
    """Input from all detection modalities"""
    
    # Face Mesh Analysis (0-1)
    gaze_left_score: float = 0.0      # Looking left
    gaze_right_score: float = 0.0     # Looking right
    gaze_down_score: float = 0.0      # Looking down
    head_yaw_degrees: float = 0.0     # Head yaw angle
    head_pitch_degrees: float = 0.0   # Head pitch (down = positive)
    head_roll_degrees: float = 0.0    # Head roll angle
    
    # Skeleton/Pose Analysis (0-1)
    leaning_score: float = 0.0
    wrist_below_desk_score: float = 0.0
    arm_extension_score: float = 0.0
    shoulder_movement_score: float = 0.0
    
    # Phone Detection (0-1)
    phone_visible_score: float = 0.0
    
    # Movement History
    movement_variance: float = 0.0    # Stability (0-1)
    
    # Timestamp for temporal analysis
    timestamp: float = 0.0

    # Per-Student Identity & Spatial Context
    track_id: Optional[int] = None
    bbox: Optional[Tuple[int, int, int, int]] = None
    is_writing_context: bool = False


@dataclass
class FusionOutput:
    """Output from multi-modal fusion"""
    
    # Overall scores
    overall_risk_score: float          # 0-100
    risk_level: RiskLevel
    
    # Component scores with weights
    component_scores: Dict[str, float]  # {gaze: 0.3, pose: 0.25, ...}
    component_weights: Dict[str, float]
    
    # Detected behaviors
    primary_behaviors: List[str]
    secondary_behaviors: List[str]
    
    # Explanations
    brief_reason: str
    detailed_reasons: List[str]
    
    # Confidence metrics
    overall_confidence: float  # 0-1
    modality_confidences: Dict[str, float]

    # Temporal assessment metadata
    temporal_assessment: Optional[TemporalAssessment] = None
    episodes_summary: Dict[str, int] = field(default_factory=dict)


class MultiModalFusionEngine:
    """
    Fuses multiple detection modalities into unified risk assessment.
    Incorporates temporal behavior analysis, episode debouncing, sliding windows,
    and cross-modal correlation across DeepSORT tracks.
    """
    
    def __init__(
        self,
        temporal_window: int = 15,
        persistence_threshold: int = 10,
        behavior_config: Optional[BehaviorConfig] = None,
    ):
        """
        Initialize fusion engine
        
        Args:
            temporal_window: Number of frames for temporal smoothing
            persistence_threshold: Frames required for behavior confirmation
            behavior_config: Optional configuration for temporal analysis
        """
        self.temporal_window = temporal_window
        self.persistence_threshold = persistence_threshold
        self.behavior_config = behavior_config or BehaviorConfig()
        self.temporal_tracker = TemporalBehaviorTracker(self.behavior_config)
        
        # Default weights for modalities
        self.weights = {
            "gaze": 0.30,
            "pose": 0.25,
            "phone": 0.20,
            "leaning": 0.15,
            "movement": 0.10,
        }
        
        # History for temporal smoothing
        self.score_history: deque = deque(maxlen=temporal_window)
        self.gaze_history: deque = deque(maxlen=temporal_window)
        self.phone_history: deque = deque(maxlen=temporal_window)
        self.pose_history: deque = deque(maxlen=temporal_window)
        
        # Behavior persistence tracking
        self.behavior_persistence: Dict[str, int] = {}
        
        logger.info(f"✅ Multi-modal fusion engine initialized with TemporalBehaviorTracker")
    
    def fuse(self, fusion_input: FusionInput, track_id: Optional[int] = None) -> FusionOutput:
        """
        Fuse all modalities into unified output using temporal behavior tracking.
        
        Args:
            fusion_input: Input from all detection systems
            track_id: Optional student DeepSORT Track ID (overrides fusion_input.track_id)
        
        Returns:
            FusionOutput with risk assessment
        """
        # Resolve student track ID
        student_track_id = track_id if track_id is not None else (fusion_input.track_id if fusion_input.track_id is not None else 1)
        
        # Calculate individual modality scores for backward compatibility
        gaze_score = self._calculate_gaze_score(fusion_input)
        pose_score = self._calculate_pose_score(fusion_input)
        phone_score = self._calculate_phone_score(fusion_input)
        leaning_score = self._calculate_leaning_score(fusion_input)
        movement_score = self._calculate_movement_score(fusion_input)
        
        component_scores = {
            "gaze": gaze_score,
            "pose": pose_score,
            "phone": phone_score,
            "leaning": leaning_score,
            "movement": movement_score,
        }
        self.score_history.append(component_scores)

        # ------------------------------------------------------------------
        # Temporal Behavior Analysis with Debouncing and Sliding Windows
        # ------------------------------------------------------------------
        import time as _time
        curr_t = fusion_input.timestamp if fusion_input.timestamp > 0 else _time.time()
        
        gaze_dir = "CENTER"
        if fusion_input.gaze_left_score > 0:
            gaze_dir = "LEFT"
        elif fusion_input.gaze_right_score > 0:
            gaze_dir = "RIGHT"
        elif fusion_input.gaze_down_score > 0:
            gaze_dir = "DOWN"
            
        gaze_results = {
            "direction": gaze_dir,
            "confidence": max(fusion_input.gaze_left_score, fusion_input.gaze_right_score, fusion_input.gaze_down_score, 0.8),
            "iris_detected": (fusion_input.gaze_left_score > 0 or fusion_input.gaze_right_score > 0 or fusion_input.gaze_down_score > 0),
        }
        
        face_results = {
            "yaw": fusion_input.head_yaw_degrees,
            "pitch": fusion_input.head_pitch_degrees,
            "roll": fusion_input.head_roll_degrees,
            "face_detected": True,
            "confidence": 0.85,
        }
        
        # Skeleton simulation class for tracker interface
        class _SkelMock:
            detected = True
            leaning_severity = fusion_input.leaning_score
            wrist_below_desk = fusion_input.wrist_below_desk_score > 0.5
            wrist_movement_severity = fusion_input.wrist_below_desk_score
            arm_movement_severity = fusion_input.arm_extension_score
            shoulder_angle_degrees = fusion_input.shoulder_movement_score * 45.0
            overall_confidence = 0.85
            
        temporal_assessment = self.temporal_tracker.update_student(
            track_id=student_track_id,
            gaze_results=gaze_results,
            face_results=face_results,
            skeleton_results=_SkelMock(),
            detections=[],
            timestamp=curr_t,
            bbox=fusion_input.bbox
        )
        
        # Risk calculation:
        # If a prohibited phone is visible, object risk applies (90+ CRITICAL).
        # Otherwise, behavioral score is driven by temporal assessment.
        if phone_score >= 0.60:
            overall_score = 90.0 + min(10.0, phone_score * 10.0)
            risk_level = RiskLevel.CRITICAL
            brief_reason = "📱 Mobile phone detected in vicinity - HIGH RISK"
            detailed_reasons = ["Mobile phone detected in vicinity - HIGH RISK"]
            primary_behaviors = ["phone_detected"]
        else:
            overall_score = temporal_assessment.behavioral_score
            risk_level = RiskLevel(temporal_assessment.risk_level.lower())
            brief_reason = temporal_assessment.brief_reason
            detailed_reasons = temporal_assessment.detailed_reasons
            
            primary_behaviors = []
            if temporal_assessment.risk_level != "LOW":
                primary_behaviors.append(temporal_assessment.primary_behavior.lower().replace(" ", "_"))
                for s in temporal_assessment.supporting_behaviors:
                    norm_s = s.lower().split("(")[0].strip().replace(" ", "_")
                    if norm_s and norm_s not in primary_behaviors:
                        primary_behaviors.append(norm_s)
                        
        secondary_behaviors = self._detect_secondary_behaviors(fusion_input, component_scores)
        
        # Modality confidences
        modality_confidences = {
            "gaze": self._calculate_modality_confidence("gaze"),
            "pose": self._calculate_modality_confidence("pose"),
            "phone": self._calculate_modality_confidence("phone"),
            "leaning": self._calculate_modality_confidence("leaning"),
            "movement": self._calculate_modality_confidence("movement"),
        }
        overall_confidence = float(np.mean(list(modality_confidences.values())))
        
        return FusionOutput(
            overall_risk_score=overall_score,
            risk_level=risk_level,
            component_scores=component_scores,
            component_weights=self.weights,
            primary_behaviors=primary_behaviors,
            secondary_behaviors=secondary_behaviors,
            brief_reason=brief_reason,
            detailed_reasons=detailed_reasons,
            overall_confidence=overall_confidence,
            modality_confidences=modality_confidences,
            temporal_assessment=temporal_assessment,
            episodes_summary=temporal_assessment.episodes_summary
        )
    
    def _calculate_gaze_score(self, fusion_input: FusionInput) -> float:
        """
        Calculate gaze-based risk score (0-1)
        
        Suspicious patterns:
        - Repeated glancing left/right (peeking)
        - Sustained gaze downward (trying to hide)
        - Extreme head yaw (looking way off-screen)
        """
        
        # Lateral gaze (looking at neighbor)
        lateral_score = max(fusion_input.gaze_left_score, fusion_input.gaze_right_score)
        
        # Head yaw angle (extreme turning is suspicious)
        yaw_threshold = 30.0  # degrees
        yaw_score = min(abs(fusion_input.head_yaw_degrees) / (2 * yaw_threshold), 1.0)
        
        # Downward gaze (could be reading notes)
        downward_score = fusion_input.gaze_down_score
        
        # Combined score
        score = max(
            0.7 * lateral_score,      # Peeking at neighbors
            0.6 * downward_score,     # Looking down (notes/phone)
            0.5 * yaw_score,          # Extreme head turning
        )
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _calculate_pose_score(self, fusion_input: FusionInput) -> float:
        """
        Calculate body pose risk score (0-1)
        
        Suspicious patterns:
        - Wrist below desk level
        - Excessive arm extension
        - Shoulder height mismatch (shrugging)
        """
        
        # Wrist below desk is very suspicious (phone/notes)
        wrist_score = fusion_input.wrist_below_desk_score * 0.5
        
        # Arm extension beyond normal
        arm_extension_score = fusion_input.arm_extension_score * 0.3
        
        # Shoulder movement
        shoulder_score = fusion_input.shoulder_movement_score * 0.2
        
        score = wrist_score + arm_extension_score + shoulder_score
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _calculate_phone_score(self, fusion_input: FusionInput) -> float:
        """
        Calculate phone detection risk score (0-1)
        
        Mobile phone visible = HIGH risk
        """
        return float(np.clip(fusion_input.phone_visible_score, 0.0, 1.0))
    
    def _calculate_leaning_score(self, fusion_input: FusionInput) -> float:
        """
        Calculate leaning risk score (0-1)
        
        Forward leaning with downward gaze = copying
        Sideways leaning = peeking at neighbor
        """
        
        # Forward lean (pitch > 10 degrees) + downward gaze
        forward_lean = max(0, fusion_input.head_pitch_degrees - 10.0) / 30.0  # Normalize
        gaze_down = fusion_input.gaze_down_score
        copying_score = forward_lean * 0.5 + gaze_down * 0.3
        
        # Sideways lean + lateral gaze
        sideways_lean = abs(fusion_input.head_roll_degrees) / 30.0
        lateral_gaze = max(fusion_input.gaze_left_score, fusion_input.gaze_right_score)
        peeking_score = sideways_lean * 0.5 + lateral_gaze * 0.3
        
        score = max(copying_score, peeking_score)
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _calculate_movement_score(self, fusion_input: FusionInput) -> float:
        """
        Calculate movement instability score (0-1)
        
        High variance in movement = fidgeting/nervousness
        Low variance = stable/calm
        """
        
        # Invert variance (high variance = high score)
        movement_score = fusion_input.movement_variance
        
        return float(np.clip(movement_score, 0.0, 1.0))
    
    def _apply_temporal_smoothing(self, current_score: float) -> float:
        """
        Apply temporal smoothing to reduce false positives
        Uses exponential moving average
        """
        if len(self.score_history) == 0:
            return current_score
        
        # Exponential moving average (alpha=0.3 for recent bias)
        alpha = 0.3
        
        # Sum weighted scores
        weighted_sum = current_score * alpha
        weight_sum = alpha
        
        # Add historical scores with exponentially decreasing weights
        for i, hist_scores in enumerate(reversed(list(self.score_history)[:-1])):
            hist_score = (
                hist_scores["gaze"] * self.weights["gaze"] +
                hist_scores["pose"] * self.weights["pose"] +
                hist_scores["phone"] * self.weights["phone"] +
                hist_scores["leaning"] * self.weights["leaning"] +
                hist_scores["movement"] * self.weights["movement"]
            ) * 100.0
            
            decay = (1 - alpha) ** (i + 1)
            weighted_sum += hist_score * decay
            weight_sum += decay
        
        smoothed = weighted_sum / weight_sum if weight_sum > 0 else current_score
        return float(np.clip(smoothed, 0.0, 100.0))
    
    def _detect_primary_behaviors(self, fusion_input: FusionInput, scores: Dict[str, float]) -> List[str]:
        """
        Detect primary suspicious behaviors
        Must have high confidence (score > 0.6)
        """
        behaviors = []
        
        # Phone detected
        if scores["phone"] > 0.6:
            behaviors.append("phone_detected")
        
        # Peeking (lateral gaze + head turn)
        if scores["gaze"] > 0.6 and fusion_input.head_yaw_degrees > 20:
            behaviors.append("peeking_at_neighbor")
        
        # Hidden hand/phone (wrist below desk + head down)
        if scores["pose"] > 0.6 and fusion_input.gaze_down_score > 0.5:
            behaviors.append("hidden_hand_below_desk")
        
        # Leaning
        if scores["leaning"] > 0.6:
            if fusion_input.head_pitch_degrees > 15:
                behaviors.append("forward_leaning")
            if abs(fusion_input.head_roll_degrees) > 15:
                behaviors.append("sideways_leaning")
        
        # Fidgeting
        if scores["movement"] > 0.7:
            behaviors.append("excessive_movement")
        
        return behaviors
    
    def _detect_secondary_behaviors(self, fusion_input: FusionInput, scores: Dict[str, float]) -> List[str]:
        """
        Detect secondary behaviors (lower confidence)
        Score 0.3-0.6
        """
        behaviors = []
        
        if 0.3 < scores["gaze"] < 0.6:
            behaviors.append("frequent_gaze_shifts")
        
        if 0.3 < scores["pose"] < 0.6:
            behaviors.append("unusual_arm_positioning")
        
        if 0.3 < scores["movement"] < 0.7:
            behaviors.append("fidgeting_detected")
        
        if abs(fusion_input.head_yaw_degrees) > 15:
            behaviors.append("head_turned_to_side")
        
        return behaviors
    
    def _generate_explanations(self, fusion_input: FusionInput, scores: Dict[str, float], 
                               behaviors: List[str]) -> Tuple[str, List[str]]:
        """Generate brief and detailed explanations"""
        
        if not behaviors:
            return "No suspicious behavior detected", []
        
        detailed = []
        
        if "phone_detected" in behaviors:
            detailed.append("📱 Mobile phone detected in vicinity - HIGH RISK")
        
        if "peeking_at_neighbor" in behaviors:
            detailed.append(f"👁️ Student repeatedly looking sideways (yaw: {fusion_input.head_yaw_degrees:.1f}°)")
        
        if "hidden_hand_below_desk" in behaviors:
            detailed.append(f"🖐️ Wrist position below desk level + downward gaze (possible phone/notes)")
        
        if "forward_leaning" in behaviors:
            detailed.append(f"📝 Forward leaning with downward gaze (pitch: {fusion_input.head_pitch_degrees:.1f}°)")
        
        if "sideways_leaning" in behaviors:
            detailed.append(f"➡️ Sideways leaning with lateral gaze (roll: {fusion_input.head_roll_degrees:.1f}°)")
        
        if "excessive_movement" in behaviors:
            detailed.append("🔄 Excessive fidgeting or movement detected")
        
        # Brief reason
        if len(behaviors) == 1:
            brief = f"Detected: {behaviors[0].replace('_', ' ')}"
        else:
            brief = f"Multiple suspicious behaviors detected ({len(behaviors)})"
        
        return brief, detailed
    
    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert score to risk level"""
        if score < 20:
            return RiskLevel.LOW
        elif score < 40:
            return RiskLevel.MEDIUM
        elif score < 60:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _calculate_modality_confidence(self, modality: str) -> float:
        """
        Calculate confidence for a specific modality
        Based on consistency across temporal window
        """
        if not self.score_history:
            return 0.5
        
        modality_scores = [h.get(modality, 0.5) for h in self.score_history]
        
        if not modality_scores:
            return 0.5
        
        # Confidence = inverse of variance (high consistency = high confidence)
        variance = np.var(modality_scores)
        confidence = 1.0 - min(variance, 0.5)  # Cap at 0.5 variance
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update fusion weights"""
        total = sum(new_weights.values())
        self.weights = {k: v / total for k, v in new_weights.items()}
        logger.info(f"✅ Fusion weights updated: {self.weights}")
