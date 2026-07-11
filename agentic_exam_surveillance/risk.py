from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

RISK_WEIGHTS = {
    "mobile_detected": 60.0,
    "head_turning": 20.0,
    "sharing_answers": 25.0,
    "leaning_to_copy": 15.0,
    "hidden_phone": 30.0,
}

@dataclass
class Alert:
    track_id: int
    risk_score: float
    event_types: list[str]

class RiskScoringEngine:
    def __init__(self, min_confidence: float = 0.7, persistence_seconds: int = 3):
        self.min_confidence = min_confidence
        self.persistence_seconds = persistence_seconds
        self.events = []

    def add_events(self, events):
        self.events.extend(events)

    def calculate(self, track_id: int) -> float:
        now = datetime.utcnow()
        total = 0.0
        for event in self.events:
            if event.track_id != track_id or event.confidence < self.min_confidence:
                continue
            age = (now - event.timestamp).total_seconds()
            if age > self.persistence_seconds:
                continue
            total += RISK_WEIGHTS.get(event.event_type, 0.0)
        return total

class DecisionAgent:
    def __init__(self, threshold: float = 70):
        self.threshold = threshold

    def decide(self, track_id: int, risk_score: float, event_types: list[str]):
        if risk_score < self.threshold:
            return None
        return Alert(track_id=track_id, risk_score=risk_score, event_types=event_types)
