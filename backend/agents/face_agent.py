"""MediaPipe Face Mesh based head-pose and movement analysis."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Any, Deque, Dict, Iterable, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:  # pragma: no cover - allows API startup without CV deps installed
    mp = None


@dataclass
class FaceAnalysisResult:
    face_detected: bool
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    head_pose: str = "UNKNOWN"
    looking_left: bool = False
    looking_right: bool = False
    looking_down: bool = False
    repeated_head_movement: bool = False
    confidence: float = 0.0
    landmarks: Optional[list[list[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FaceAnalysisAgent:
    """Runs Face Mesh locally and estimates privacy-safe head-pose signals."""

    # Nose, chin, eye corners, mouth corners from MediaPipe Face Mesh.
    FACE_3D_MODEL = np.array(
        [
            (0.0, 0.0, 0.0),
            (0.0, -63.6, -12.5),
            (-43.3, 32.7, -26.0),
            (43.3, 32.7, -26.0),
            (-28.9, -28.9, -24.1),
            (28.9, -28.9, -24.1),
        ],
        dtype=np.float64,
    )
    LANDMARK_IDS = [1, 152, 33, 263, 61, 291]

    def __init__(self, max_history: int = 45, yaw_threshold: float = 18.0, pitch_threshold: float = 15.0):
        self.max_history = max_history
        self.yaw_threshold = yaw_threshold
        self.pitch_threshold = pitch_threshold
        self.history: Dict[str, Deque[Tuple[float, float, float]]] = defaultdict(lambda: deque(maxlen=max_history))
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

    def analyze(self, frame: np.ndarray, track: Any = None) -> Dict[str, Any]:
        if frame is None or self.face_mesh is None:
            return FaceAnalysisResult(face_detected=False).to_dict()

        crop, offset = self._crop_track(frame, track)
        h, w = crop.shape[:2]
        if h < 20 or w < 20:
            return FaceAnalysisResult(face_detected=False).to_dict()

        results = self.face_mesh.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        if not results.multi_face_landmarks:
            return FaceAnalysisResult(face_detected=False).to_dict()

        landmarks = results.multi_face_landmarks[0].landmark
        image_points = np.array([(landmarks[i].x * w, landmarks[i].y * h) for i in self.LANDMARK_IDS], dtype=np.float64)
        yaw, pitch, roll = self._estimate_pose(image_points, w, h)
        key = self._track_key(track)
        self.history[key].append((yaw, pitch, roll))

        repeated = self._repeated_movement(self.history[key])
        head_pose = self._pose_label(yaw, pitch)
        landmark_sample = [[float(lm.x), float(lm.y), float(lm.z)] for lm in landmarks[::12]]

        return FaceAnalysisResult(
            face_detected=True,
            yaw=float(yaw),
            pitch=float(pitch),
            roll=float(roll),
            head_pose=head_pose,
            looking_left=yaw < -self.yaw_threshold,
            looking_right=yaw > self.yaw_threshold,
            looking_down=pitch > self.pitch_threshold,
            repeated_head_movement=repeated,
            confidence=0.85,
            landmarks=landmark_sample,
        ).to_dict()

    def _estimate_pose(self, image_points: np.ndarray, width: int, height: int) -> Tuple[float, float, float]:
        focal_length = width
        camera_matrix = np.array([[focal_length, 0, width / 2], [0, focal_length, height / 2], [0, 0, 1]], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))
        ok, rotation_vec, _ = cv2.solvePnP(self.FACE_3D_MODEL, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            return 0.0, 0.0, 0.0
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)
        angles, *_ = cv2.RQDecomp3x3(rotation_mat)
        pitch, yaw, roll = [float(a) for a in angles]
        return yaw, pitch, roll

    def _crop_track(self, frame: np.ndarray, track: Any) -> Tuple[np.ndarray, Tuple[int, int]]:
        bbox = getattr(track, "bbox", None) or (track or {}).get("bbox") if isinstance(track, dict) else None
        if not bbox:
            return frame, (0, 0)
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        pad_x, pad_y = int((x2 - x1) * 0.08), int((y2 - y1) * 0.08)
        x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
        x2, y2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
        return frame[y1:y2, x1:x2], (x1, y1)

    def _track_key(self, track: Any) -> str:
        if isinstance(track, dict):
            return str(track.get("student_id") or track.get("tracking_id") or track.get("track_id") or "global")
        return str(getattr(track, "student_id", None) or getattr(track, "track_id", "global"))

    def _pose_label(self, yaw: float, pitch: float) -> str:
        if pitch > self.pitch_threshold:
            return "DOWN"
        if yaw < -self.yaw_threshold:
            return "LEFT"
        if yaw > self.yaw_threshold:
            return "RIGHT"
        return "CENTER"

    def _repeated_movement(self, values: Iterable[Tuple[float, float, float]]) -> bool:
        seq = list(values)
        if len(seq) < 12:
            return False
        yaws = np.array([v[0] for v in seq[-12:]])
        signs = np.sign(yaws)
        changes = np.sum(np.abs(np.diff(signs)) > 1)
        return bool(changes >= 3 and np.std(yaws) > 12)

    def release(self) -> None:
        if self.face_mesh:
            self.face_mesh.close()
