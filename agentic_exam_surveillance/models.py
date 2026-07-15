from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class BehaviorEvent:
    track_id: int
    event_type: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
