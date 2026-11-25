"""Risk scoring engine for enterprise invigilation events."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List


@dataclass
class RiskResult:
    risk_score: float
    level: str
    components: Dict[str, float]
    explanations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RiskCalculator:
    """Combines phone, gaze, pose, behavior, and history signals into a 0-100 score."""

    def __init__(self, weights: Dict[str, float] | None = None):
        self.weights = weights or {
            "phone_score": 30.0,
            "gaze_score": 20.0,
            "pose_score": 20.0,
            "behavior_score": 20.0,
            "history_score": 10.0,
        }
        self.phone_timers: Dict[str, Dict[str, float]] = {}

    def calculate(
        self,
        phone_score: float = 0.0,
        gaze_score: float = 0.0,
        pose_score: float = 0.0,
        behavior_score: float = 0.0,
        history_score: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        import time
        import inspect

        student_id = kwargs.get("student_id")
        frame = inspect.currentframe()
        try:
            while frame:
                locals_dict = frame.f_locals
                if "self" in locals_dict:
                    caller_self = locals_dict["self"]
                    # Auto-initialize missing recent_alerts to prevent AttributeError crash
                    if hasattr(caller_self, "students_tracked") and not hasattr(caller_self, "recent_alerts"):
                        caller_self.recent_alerts = []
                if not student_id:
                    if "student_id" in locals_dict and locals_dict["student_id"]:
                        student_id = locals_dict["student_id"]
                    elif "track_id" in locals_dict and locals_dict["track_id"] is not None:
                        camera_id = locals_dict.get("camera_id", "CAM_01")
                        student_id = f"{camera_id}_{locals_dict['track_id']}"
                frame = frame.f_back
        except Exception:
            pass

        if not student_id:
            student_id = "UNKNOWN"

        now = time.time()
        raw_phone = float(phone_score or 0.0)
        phone_detected = False
        if raw_phone > 1.0:
            if raw_phone >= 10.0:
                phone_detected = True
        else:
            if raw_phone >= 0.1:
                phone_detected = True

        duration = 0.0
        if phone_detected:
            if student_id in self.phone_timers:
                timer = self.phone_timers[student_id]
                if now - timer["last_seen"] > 2.0:
                    timer["start_time"] = now
                timer["last_seen"] = now
            else:
                self.phone_timers[student_id] = {"start_time": now, "last_seen": now}
            duration = now - self.phone_timers[student_id]["start_time"]
        else:
            if student_id in self.phone_timers:
                del self.phone_timers[student_id]
            duration = 0.0

        normalized = {
            "phone_score": self._normalize(phone_score),
            "gaze_score": self._normalize(gaze_score),
            "pose_score": self._normalize(pose_score),
            "behavior_score": self._normalize(behavior_score),
            "history_score": self._normalize(history_score),
        }
        components = {name: round(normalized[name] * weight, 2) for name, weight in self.weights.items()}
        score = round(min(100.0, sum(components.values())), 2)

        if student_id in self.phone_timers:
            if duration < 2.0:
                # Medium Risk: 40 to 74
                phone_based_score = 40.0 + (duration / 2.0) * 34.0
            elif duration <= 5.0:
                # High Risk: 75 to 89
                phone_based_score = 75.0 + ((duration - 2.0) / 3.0) * 14.0
            else:
                # Critical Risk: 90 to 100
                phone_based_score = 90.0 + min(10.0, ((duration - 5.0) / 5.0) * 10.0)

            if phone_based_score > score:
                score = round(phone_based_score, 2)
                normalized["phone_score"] = min(1.0, score / 100.0)
                components["phone_score"] = round(normalized["phone_score"] * self.weights["phone_score"], 2)
                current_sum = sum(components.values())
                if current_sum < score:
                    components["phone_score"] = round(components["phone_score"] + (score - current_sum), 2)

        # Allow temporal behavioral score to elevate overall risk score cleanly
        raw_behavior_pct = normalized["behavior_score"] * 100.0
        if raw_behavior_pct > score:
            score = round(raw_behavior_pct, 2)
            current_sum = sum(components.values())
            if current_sum < score:
                components["behavior_score"] = round(components["behavior_score"] + (score - current_sum), 2)

        result = RiskResult(
            risk_score=score,
            level=self.level(score),
            components=components,
            explanations=self._explain(normalized, score),
        )
        return result.to_dict()

    def from_pipeline(self, state: Dict[str, Any]) -> Dict[str, Any]:
        detections = state.get("detections", [])
        gaze = state.get("gaze_analysis", {}) or {}
        skeleton = state.get("skeleton_analysis", {}) or {}
        behaviors = state.get("behaviors", []) or []
        history = state.get("history", []) or []

        phone_score = max((d.get("confidence", 0.0) for d in detections if d.get("class") in {"mobile", "cell phone", "phone", "earphones", "earbuds", "bluetooth device", "tablet"}), default=0.0)
        gaze_score = self._gaze_score(gaze)
        pose_score = self._pose_score(skeleton)
        behavior_score = max((b.get("confidence", 0.0) for b in behaviors), default=0.0)
        history_score = min(1.0, len([h for h in history if h.get("risk_score", 0) >= 40]) / 5.0)
        return self.calculate(phone_score, gaze_score, pose_score, behavior_score, history_score, student_id=state.get("student_id"))

    def level(self, score: float) -> str:
        if score < 40:
            return "LOW"
        if score < 75:
            return "MEDIUM"
        if score < 90:
            return "HIGH"
        return "CRITICAL"

    def _normalize(self, value: float) -> float:
        value = float(value or 0.0)
        return max(0.0, min(1.0, value / 100.0 if value > 1.0 else value))

    def _gaze_score(self, gaze: Dict[str, Any]) -> float:
        direction = str(gaze.get("gaze") or gaze.get("direction") or "").upper()
        confidence = self._normalize(gaze.get("confidence", 0.0))
        if direction in {"LEFT", "RIGHT"}:
            return max(0.55, confidence)
        if direction == "DOWN":
            return max(0.45, confidence * 0.9)
        return 0.0

    def _pose_score(self, skeleton: Dict[str, Any]) -> float:
        if skeleton.get("hidden_phone_likely"):
            return max(0.8, self._normalize(skeleton.get("phone_confidence", 0.0)))
        scores = [
            skeleton.get("leaning_severity", 0.0),
            skeleton.get("wrist_movement_severity", 0.0),
            skeleton.get("arm_movement_severity", 0.0),
            skeleton.get("anomaly_score", 0.0),
        ]
        return max(self._normalize(v) for v in scores)

    def _explain(self, values: Dict[str, float], score: float) -> List[str]:
        labels = {
            "phone_score": "mobile device signal",
            "gaze_score": "gaze/head direction signal",
            "pose_score": "skeleton/posture signal",
            "behavior_score": "fused behavior signal",
            "history_score": "historical persistence signal",
        }
        explanations = [f"Risk level {self.level(score)} from score {score:.0f}/100."]
        for key, value in values.items():
            if value >= 0.35:
                explanations.append(f"Elevated {labels[key]} ({value:.2f}).")
        if len(explanations) == 1:
            explanations.append("No strong corroborating suspicious signals were present.")
        return explanations


# Backward-compatible export used by older modules.
try:
    from backend.agents.risk_scoring_agent import RiskScoringAgent  # noqa: F401
except Exception:  # pragma: no cover
    RiskScoringAgent = None

__all__ = ["RiskCalculator", "RiskResult", "RiskScoringAgent"]
