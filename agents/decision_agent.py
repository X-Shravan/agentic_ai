from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List


# ------------------------------------------------
# Alert Levels
# ------------------------------------------------
class AlertLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ------------------------------------------------
# Decision Data
# ------------------------------------------------
@dataclass
class Decision:
    track_id: int
    risk_score: float
    level: AlertLevel
    should_alert: bool
    message: str
    events: List[str]
    timestamp: float = field(default_factory=time.time)


# ------------------------------------------------
# Decision Agent
# ------------------------------------------------
class DecisionAgent:

    def __init__(self, config):

        r = config.get("risk", {})

        self.threshold = r.get("threshold", 75)
        self.cooldown = r.get("alert_cooldown", 10)

        self.callbacks: List[Callable[[Decision], None]] = []

        self.decisions: Dict[int, Decision] = {}
        self.last_alert_time: Dict[int, float] = {}

        self.alert_history: List[Decision] = []

    # ---------------------------------------------
    def register_callback(self, cb: Callable[[Decision], None]):
        self.callbacks.append(cb)

    # ---------------------------------------------
    # 🔥 MAIN DECISION FUNCTION
    # ---------------------------------------------
    def decide(self, scores: Dict[int, dict]) -> Dict[int, Decision]:

        output = {}

        for track_id, data in scores.items():

            score = data.get("score", 0)
            events = data.get("events", [])

            level = self._get_level(score)

            now = time.time()
            should_alert = False

            # -----------------------------------------
            # 🚨 Alert Condition with Cooldown
            # -----------------------------------------
            if score >= self.threshold:

                last_time = self.last_alert_time.get(track_id, 0)

                if now - last_time > self.cooldown:
                    should_alert = True
                    self.last_alert_time[track_id] = now

            # -----------------------------------------
            # 🧠 Smart Message Formatting
            # -----------------------------------------
            event_text = self._format_events(events)

            message = (
                f"[{level.value.upper()}] "
                f"Student ID {track_id} | "
                f"Risk Score: {score:.1f} | "
                f"{event_text}"
            )

            decision = Decision(
                track_id=track_id,
                risk_score=score,
                level=level,
                should_alert=should_alert,
                message=message,
                events=events
            )

            output[track_id] = decision
            self.decisions[track_id] = decision

            # -----------------------------------------
            # 🔔 Trigger Alerts
            # -----------------------------------------
            if should_alert:

                self.alert_history.append(decision)

                for cb in self.callbacks:
                    cb(decision)

        return output

    # ---------------------------------------------
    def _get_level(self, score: float) -> AlertLevel:

        if score >= 90:
            return AlertLevel.CRITICAL

        elif score >= 75:
            return AlertLevel.HIGH

        elif score >= 40:
            return AlertLevel.MEDIUM

        else:
            return AlertLevel.LOW

    # ---------------------------------------------
    def _format_events(self, events: List[str]) -> str:

        if not events:
            return "No suspicious activity"

        # ✅ Match with RiskScoringAgent keys
        priority = [
            "using_mobile",
            "sharing_answers",
            "leaning_to_copy",
            "looking_around"
        ]

        # Sort events based on priority
        ordered = sorted(
            events,
            key=lambda x: priority.index(x) if x in priority else 99
        )

        # Make readable labels
        readable = {
            "using_mobile": "Mobile Usage",
            "sharing_answers": "Sharing Answers",
            "leaning_to_copy": "Copying Attempt",
            "looking_around": "Looking Around"
        }

        formatted = [readable.get(e, e) for e in ordered]

        return " | ".join(formatted)

    # ---------------------------------------------
    def get_statistics(self):

        active_alerts = sum(
            1 for d in self.decisions.values()
            if d.should_alert
        )

        return {
            "active_alerts": active_alerts,
            "total_decisions": len(self.decisions),
            "alert_history": len(self.alert_history),
        }

    # ---------------------------------------------
    def reset(self):

        self.decisions.clear()
        self.last_alert_time.clear()
        self.alert_history.clear()