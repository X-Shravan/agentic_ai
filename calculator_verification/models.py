"""Data models and enums for standalone scientific calculator verification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class CalculatorClassification(str, Enum):
    """Raw Gemini Vision classification categories for calculator verification."""
    SCIENTIFIC_CALCULATOR = "scientific_calculator"
    NOT_SCIENTIFIC_CALCULATOR = "not_scientific_calculator"
    UNCERTAIN = "uncertain"


class CalculatorObjectType(str, Enum):
    """Standardized high-level object type categories."""
    SCIENTIFIC_CALCULATOR = "SCIENTIFIC_CALCULATOR"
    NOT_CALCULATOR = "NOT_CALCULATOR"
    UNKNOWN = "UNKNOWN"


@dataclass
class CalculatorCandidate:
    """A bounding box candidate identified for scientific calculator verification."""
    bbox: Tuple[int, int, int, int]
    confidence: float = 0.50
    source: str = "candidate"  # "yolo" or "candidate"
    track_id: Optional[int] = None

    @property
    def width(self) -> int:
        return max(0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> int:
        return max(0, self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        if self.width == 0:
            return 0.0
        return self.height / self.width


@dataclass
class CalculatorVerificationResult:
    """The structured decision produced by the calculator verification pipeline."""
    object_type: str  # SCIENTIFIC_CALCULATOR | NOT_CALCULATOR | UNKNOWN
    classification: str  # scientific_calculator | not_scientific_calculator | uncertain
    confidence: float
    safe: bool  # True only if object_type == SCIENTIFIC_CALCULATOR
    reason: str
    bbox: Tuple[int, int, int, int]
    timestamp: float
    track_id: Optional[int] = None
    verification_status: str = "verified"  # verified | temporarily_unavailable | uncertain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_type": self.object_type,
            "classification": self.classification,
            "confidence": round(self.confidence, 3),
            "safe": self.safe,
            "reason": self.reason,
            "bbox": list(self.bbox),
            "timestamp": self.timestamp,
            "track_id": self.track_id,
            "verification_status": self.verification_status,
        }
