"""Enterprise evidence capture for alerts, screenshots, clips, and metadata."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import cv2
import numpy as np


@dataclass
class EvidenceRecord:
    evidence_id: str
    incident_id: str
    student_id: str
    student: str  # For backwards compatibility
    tracking_id: Optional[int]
    camera_id: str
    timestamp: str
    behaviour: str
    event: str  # For backwards compatibility
    confidence: float
    risk_score: float
    evidence_image_path: Optional[str]
    alert_id: Optional[str] = None
    image_path: Optional[str] = None
    evidence_video_path: Optional[str] = None
    gemini_summary: Optional[str] = None
    reviewer_status: str = "pending"
    session_id: str = "LIVE"
    original_frame_path: Optional[str] = None
    annotated_frame_path: Optional[str] = None
    annotated_image_path: Optional[str] = None
    original_image_path: Optional[str] = None
    metadata_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceAgent:
    """Stores local-only evidence with JSON metadata; no video leaves the machine."""

    def __init__(self, root_dir: str = "storage/evidence"):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        # Keep legacy directories for fallback backwards compatibility if needed
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
        clip_frames: Optional[List[np.ndarray]] = None,
        gemini_summary: Optional[str] = None,
        reviewer_status: str = "pending",
        session_id: str = "LIVE",
        metadata: Optional[Dict[str, Any]] = None,
        alert_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        print("Detection Triggered")
        # Format dates and IDs safely for nesting structure
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_camera = self._safe_name(camera_id).lower()
        safe_student = self._safe_name(student_id).lower()
        
        # Target directory: storage/evidence/YYYY-MM-DD/camera_id/student_id/
        target_dir = self.root / date_str / safe_camera / safe_student
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_part = uuid.uuid4().hex[:5].upper()
        evidence_id = f"EV_{timestamp_str}_{uuid_part}"

        # Ensure uniqueness of filename to never overwrite
        while (target_dir / f"{evidence_id}.jpg").exists():
            time.sleep(0.01)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            uuid_part = uuid.uuid4().hex[:5].upper()
            evidence_id = f"EV_{timestamp_str}_{uuid_part}"

        original_name = f"{evidence_id}_original.jpg"
        annotated_name = f"{evidence_id}.jpg"
        video_name = f"{evidence_id}_clip.mp4"
        manifest_name = f"{evidence_id}_clip_manifest.json"
        metadata_name = f"{evidence_id}_metadata.json"

        # Copy the frame immediately to avoid referencing modified canvases
        local_frame = frame.copy() if frame is not None else None
        local_annotated = annotated_frame.copy() if annotated_frame is not None else None

        if local_frame is not None:
            print(f"Captured Frame Size:\n{local_frame.shape[1]}x{local_frame.shape[0]}")
        else:
            print("Captured Frame Size:\nNo Frame")

        original_path = self._save_frame_silent(local_frame, target_dir / original_name)
        
        # Annotate with all 9 elements
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        annotated = local_annotated if local_annotated is not None else local_frame
        annotated = self._annotate(
            annotated,
            student_id=student_id,
            event=event,
            risk_score=risk_score,
            confidence=confidence,
            camera_id=camera_id,
            tracking_id=tracking_id,
            timestamp=timestamp_str
        )
        
        annotated_path = self._save_frame(annotated, target_dir / annotated_name)
        
        # Absolute path log for unique evidence image
        abs_evidence_saved = ""
        if annotated_path:
            abs_evidence_saved = str(Path(annotated_path).resolve())
            print(f"Captured Frame:\n{abs_evidence_saved}")
            print(f"Saved Evidence Path:\n{abs_evidence_saved}")
            print(f"Database Path:\n{abs_evidence_saved}")
        
        video_path = None
        if clip_frames:
            video_file = target_dir / video_name
            video_path = self.save_video_clip(video_file, clip_frames)
            
            # Save manifest file
            manifest_file = target_dir / manifest_name
            frame_names = [f"frame_{i}.jpg" for i in range(len(clip_frames))]
            self.save_clip_metadata_path(manifest_file, evidence_id, frame_names)

        metadata_path = target_dir / metadata_name

        record = EvidenceRecord(
            evidence_id=evidence_id,
            incident_id=evidence_id,
            alert_id=alert_id,
            student_id=str(student_id),
            student=str(student_id),
            tracking_id=tracking_id,
            camera_id=camera_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            behaviour=event,
            event=event,
            confidence=float(confidence or 0.0),
            risk_score=float(risk_score or 0.0),
            evidence_image_path=annotated_path,
            image_path=abs_evidence_saved if abs_evidence_saved else None,
            evidence_video_path=video_path,
            gemini_summary=gemini_summary,
            reviewer_status=reviewer_status,
            session_id=session_id,
            original_frame_path=original_path,
            annotated_frame_path=annotated_path,
            annotated_image_path=abs_evidence_saved if abs_evidence_saved else None,
            original_image_path=str(Path(original_path).resolve()) if original_path else None,
            metadata_path=str(metadata_path),
        )
        payload = record.to_dict()
        payload["metadata"] = metadata or {}
        
        # Write metadata file
        metadata_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"Evidence metadata saved: {metadata_path}")
        return payload

    def save_video_clip(self, target_path: Path, frames: List[np.ndarray], fps: int = 10) -> Optional[str]:
        if not frames:
            return None
        h, w = frames[0].shape[:2]
        # Standard cross-platform fallback video codecs (mp4v, openh264)
        for codec in ("mp4v", "XVID", "MJPG"):
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                out = cv2.VideoWriter(str(target_path), fourcc, fps, (w, h))
                if out.isOpened():
                    for frame in frames:
                        out.write(frame)
                    out.release()
                    print(f"Video clip saved: {target_path}")
                    return str(target_path)
            except Exception as e:
                print(f"[WARNING] Video writer with codec {codec} failed: {e}")
        return None

    def save_clip_metadata(self, path: Path, evidence_id: str, frames: Iterable[str], fps: int = 15) -> str:
        path.write_text(json.dumps({"evidence_id": evidence_id, "fps": fps, "frames": list(frames)}, indent=2), encoding="utf-8")
        return str(path)

    def save_clip_metadata_path(self, target_path: Path, evidence_id: str, frames: Iterable[str], fps: int = 15) -> str:
        target_path.write_text(json.dumps({"evidence_id": evidence_id, "fps": fps, "frames": list(frames)}, indent=2), encoding="utf-8")
        return str(target_path)

    def _save_frame(self, frame: Optional[np.ndarray], path: Path) -> Optional[str]:
        if frame is None:
            return None
        abs_path = str(path.resolve())
        print(f"Saving Evidence:\n{abs_path}")
        success = cv2.imwrite(str(path), frame)
        print(f"Save Success:\n{success}")
        if not success:
            print(f"[ERROR] Failed to save frame to {abs_path}")
        return str(path)

    def _save_frame_silent(self, frame: Optional[np.ndarray], path: Path) -> Optional[str]:
        if frame is None:
            return None
        cv2.imwrite(str(path), frame)
        return str(path)

    def _annotate(
        self,
        frame: Optional[np.ndarray],
        student_id: str,
        event: str,
        risk_score: float,
        confidence: float,
        camera_id: str,
        tracking_id: Optional[int],
        timestamp: str
    ) -> Optional[np.ndarray]:
        if frame is None:
            return None
        img = frame.copy()
        cv2.rectangle(img, (10, 10), (min(img.shape[1] - 10, 760), 160), (0, 0, 0), -1)
        lines = [
            f"Evidence Alert: {event} | Camera: {camera_id}",
            f"Student: {student_id} | Track ID: {tracking_id} | Risk: {risk_score:.1f}/100",
            f"Confidence: {confidence:.2f} | Time: {timestamp}",
        ]
        for idx, line in enumerate(lines):
            cv2.putText(img, line, (24, 42 + idx * 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        return img

    def _safe_name(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value).upper())[:80]


class EvidenceCapture(EvidenceAgent):
    """Backward-compatible wrapper used by the legacy runner."""

    def __init__(self, save_dir: str = "storage/evidence/screenshots"):
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
