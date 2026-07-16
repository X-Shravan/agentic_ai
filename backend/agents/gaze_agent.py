"""MediaPipe Iris gaze tracking with privacy-safe structured output."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Any, Deque, Dict, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None


@dataclass
class GazeResult:
    iris_detected: bool
    gaze: str = "UNKNOWN"
    direction: str = "UNKNOWN"
    confidence: float = 0.0
    fixation: float = 0.0
    left_ratio: Optional[float] = None
    right_ratio: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GazeAgent:
    """Classifies gaze as LEFT, RIGHT, DOWN, or CENTER using local Face Mesh iris landmarks."""

    LEFT_EYE = (33, 133)
    RIGHT_EYE = (362, 263)
    LEFT_IRIS = [468, 469, 470, 471]
    RIGHT_IRIS = [473, 474, 475, 476]

    def __init__(self, history_size: int = 30):
        self.history: Dict[str, Deque[str]] = defaultdict(lambda: deque(maxlen=history_size))
        self.mp_face_mesh = mp.solutions.face_mesh if mp else None
        self.face_mesh = None
        if self.mp_face_mesh:
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    def analyze(self, frame: np.ndarray, face: Any = None, track: Any = None) -> Dict[str, Any]:
        if frame is None or self.face_mesh is None:
            return GazeResult(iris_detected=False).to_dict()

        crop = self._crop_track(frame, track)
        h, w = crop.shape[:2]
        if h < 20 or w < 20:
            return GazeResult(iris_detected=False).to_dict()

        results = self.face_mesh.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        if not results.multi_face_landmarks:
            return GazeResult(iris_detected=False).to_dict()
        landmarks = results.multi_face_landmarks[0].landmark
        if len(landmarks) < 477:
            return GazeResult(iris_detected=False).to_dict()

        left_ratio = self._eye_ratio(landmarks, self.LEFT_EYE, self.LEFT_IRIS)
        right_ratio = self._eye_ratio(landmarks, self.RIGHT_EYE, self.RIGHT_IRIS)
        avg_ratio = (left_ratio + right_ratio) / 2.0
        iris_y = np.mean([landmarks[i].y for i in self.LEFT_IRIS + self.RIGHT_IRIS])
        eye_y = np.mean([landmarks[i].y for i in [33, 133, 362, 263]])

        if iris_y - eye_y > 0.018:
            gaze = "DOWN"
        elif avg_ratio < 0.42:
            gaze = "LEFT"
        elif avg_ratio > 0.58:
            gaze = "RIGHT"
        else:
            gaze = "CENTER"

        key = self._track_key(track)
        self.history[key].append(gaze)
        fixation = self._fixation_score(self.history[key], gaze)
        confidence = min(0.98, 0.65 + abs(avg_ratio - 0.5) * 1.4 + (0.12 if gaze == "DOWN" else 0.0))
        if gaze == "CENTER":
            confidence = 0.82

        return GazeResult(
            iris_detected=True,
            gaze=gaze,
            direction=gaze,
            confidence=float(confidence),
            fixation=float(fixation),
            left_ratio=float(left_ratio),
            right_ratio=float(right_ratio),
        ).to_dict()

    def _eye_ratio(self, landmarks: Any, eye_ids: Tuple[int, int], iris_ids: list[int]) -> float:
        x1 = landmarks[eye_ids[0]].x
        x2 = landmarks[eye_ids[1]].x
        iris_x = float(np.mean([landmarks[i].x for i in iris_ids]))
        lo, hi = sorted((x1, x2))
        return float(np.clip((iris_x - lo) / max(hi - lo, 1e-6), 0.0, 1.0))

    def _crop_track(self, frame: np.ndarray, track: Any) -> np.ndarray:
        bbox = getattr(track, "bbox", None) or (track or {}).get("bbox") if isinstance(track, dict) else None
        if not bbox:
            return frame
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        return frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]

    def _track_key(self, track: Any) -> str:
        if isinstance(track, dict):
            return str(track.get("student_id") or track.get("tracking_id") or track.get("track_id") or "global")
        return str(getattr(track, "student_id", None) or getattr(track, "track_id", "global"))

    def _fixation_score(self, history: Deque[str], gaze: str) -> float:
        if not history:
            return 0.0
        return sum(1 for item in history if item == gaze) / len(history)

    def release(self) -> None:
        if self.face_mesh:
            self.face_mesh.close()
