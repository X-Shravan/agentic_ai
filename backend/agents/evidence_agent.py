"""Enterprise evidence capture for alerts, screenshots, clips, and metadata."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import cv2
import numpy as np


@dataclass
class EvidenceRecord:
    evidence_id: str
    student: str
    event: str
    timestamp: str
    camera_id: str
    tracking_id: Optional[int]
    seat: Optional[str]
    confidence: float
    risk_score: float
    original_frame_path: Optional[str]
    annotated_frame_path: Optional[str]
    metadata_path: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceAgent:
    """Stores local-only evidence with JSON metadata; no video leaves the machine."""

    def __init__(self, root_dir: str = "backend/storage/evidence"):
        self.root = Path(root_dir)
        self.screenshots_dir = self.root / "screenshots"
        self.clips_dir = self.root / "clips"
        self.metadata_dir = self.root / "metadata"
        for directory in (self.screenshots_dir, self.clips_dir, self.metadata_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        frame: Optional[np.ndarray],
        annotated_frame: Optional[np.ndarray] = None,
        *,
        student_id: str = "UNKNOWN",
        event: str = "SUSPICIOUS_BEHAVIOR",
        camera_id: str = "CAM_01",
        tracking_id: Optional[int] = None,
        seat: Optional[str] = None,
        confidence: float = 0.0,
        risk_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        evidence_id = f"EV{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8].upper()}"
        safe_event = self._safe_name(event)
        base_name = f"{evidence_id}_{student_id}_{safe_event}"

        original_path = self._save_frame(frame, self.screenshots_dir / f"{base_name}_original.jpg")
        annotated = annotated_frame if annotated_frame is not None else self._annotate(frame, student_id, event, risk_score, confidence)
        annotated_path = self._save_frame(annotated, self.screenshots_dir / f"{base_name}_annotated.jpg")
        metadata_path = self.metadata_dir / f"{base_name}.json"

        record = EvidenceRecord(
            evidence_id=evidence_id,
            student=str(student_id),
            event=event,
            timestamp=datetime.now(timezone.utc).isoformat(),
            camera_id=camera_id,
            tracking_id=tracking_id,
            seat=seat,
            confidence=float(confidence or 0.0),
            risk_score=float(risk_score or 0.0),
            original_frame_path=original_path,
            annotated_frame_path=annotated_path,
            metadata_path=str(metadata_path),
        )
        payload = record.to_dict()
        payload["metadata"] = metadata or {}
        metadata_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return payload

    def save_clip_metadata(self, evidence_id: str, frames: Iterable[str], fps: int = 15) -> str:
        path = self.clips_dir / f"{evidence_id}_clip_manifest.json"
        path.write_text(json.dumps({"evidence_id": evidence_id, "fps": fps, "frames": list(frames)}, indent=2), encoding="utf-8")
        return str(path)

    def _save_frame(self, frame: Optional[np.ndarray], path: Path) -> Optional[str]:
        if frame is None:
            return None
        cv2.imwrite(str(path), frame)
        return str(path)

    def _annotate(self, frame: Optional[np.ndarray], student_id: str, event: str, risk_score: float, confidence: float) -> Optional[np.ndarray]:
        if frame is None:
            return None
        img = frame.copy()
        cv2.rectangle(img, (10, 10), (min(img.shape[1] - 10, 760), 118), (0, 0, 0), -1)
        lines = [
            f"Evidence Alert: {event}",
            f"Student: {student_id} | Risk: {risk_score:.0f}/100 | Confidence: {confidence:.2f}",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        for idx, line in enumerate(lines):
            cv2.putText(img, line, (24, 42 + idx * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 255, 255), 2)
        return img

    def _safe_name(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value).upper())[:80]


class EvidenceCapture(EvidenceAgent):
    """Backward-compatible wrapper used by the legacy runner."""

    def __init__(self, save_dir: str = "backend/storage/evidence/screenshots"):
        super().__init__(root_dir=str(Path(save_dir).parent if Path(save_dir).name == "screenshots" else save_dir))

    def save_screenshot(self, frame, track_id, score, events):
        event = str(events[0]) if events else "SUSPICIOUS_BEHAVIOR"
        return self.capture(
            frame,
            student_id=str(track_id),
            event=event,
            tracking_id=int(track_id) if str(track_id).isdigit() else None,
            confidence=float(score or 0.0),
            risk_score=float(score or 0.0) * 100 if float(score or 0.0) <= 1 else float(score or 0.0),
            metadata={"legacy_events": events or []},
        )
