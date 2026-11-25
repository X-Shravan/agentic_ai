from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)

# Class compatibility groups for class-aware tracking
DEVICE_CLASSES = {
    "cell phone", "phone", "mobile", "calculator", "scientific_calculator",
    "tablet", "earphones", "bluetooth device"
}
PAPER_CLASSES = {
    "book", "answer book", "notebook", "paper sheet", "answer_sheet"
}
WATCH_CLASSES = {
    "smart watch", "smartwatch", "analog watch", "digital watch", "watch"
}
PERSON_CLASSES = {"person"}


def are_classes_compatible(c1: str, c2: str) -> bool:
    """Check if two class labels can refer to the same physical object track.

    Allows semantic reclassification (e.g., cell phone <-> scientific_calculator,
    or book <-> answer_sheet) while strictly forbidding cross-category swaps
    (e.g., person cannot match a phone or book).
    """
    c1 = (c1 or "").lower().strip()
    c2 = (c2 or "").lower().strip()
    if c1 == c2:
        return True
    if c1 in DEVICE_CLASSES and c2 in DEVICE_CLASSES:
        return True
    if c1 in PAPER_CLASSES and c2 in PAPER_CLASSES:
        return True
    if c1 in WATCH_CLASSES and c2 in WATCH_CLASSES:
        return True
    return False


def calculate_distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Euclidean distance between two 2D points."""
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """Intersection over Union (IoU) between two bounding boxes (x1, y1, x2, y2)."""
    if not (isinstance(a, (list, tuple)) and len(a) == 4 and isinstance(b, (list, tuple)) and len(b) == 4):
        return 0.0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = ((ax2 - ax1) * (ay2 - ay1)) + ((bx2 - bx1) * (by2 - by1)) - inter

    return float(inter / union) if union > 0 else 0.0


def extract_appearance_feature(frame: Optional[np.ndarray], bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """Extract a fast, normalized HSV color histogram feature from an image crop."""
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return None
    x1, y1, x2, y2 = bbox
    h_f, w_f = frame.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w_f, int(x2)), min(h_f, int(y2))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
    norm = float(np.linalg.norm(hist))
    if norm > 0:
        hist = hist / norm
    return hist.flatten()


def cosine_distance(feat1: Optional[np.ndarray], feat2: Optional[np.ndarray]) -> float:
    """Cosine distance in range [0.0, 1.0]."""
    if feat1 is None or feat2 is None:
        return 0.5
    dot = float(np.dot(feat1, feat2))
    return float(np.clip(1.0 - dot, 0.0, 1.0))


def deduplicate_detections(detections: List[Any], iou_thresh: float = 0.50) -> List[Any]:
    """Pre-tracking Non-Maximum Suppression to eliminate duplicate YOLO boxes.

    Uses IoU, center distance, bounding-box containment, and class equality to
    suppress genuine duplicates of the same physical person or object, while
    preserving distinct people sitting close together.
    """
    if len(detections) <= 1:
        return detections

    def get_conf(d: Any) -> float:
        return float(getattr(d, "confidence", 0.0) if hasattr(d, "confidence") else (d.get("confidence", 0.0) if isinstance(d, dict) else 0.0))

    sorted_dets = sorted(detections, key=get_conf, reverse=True)
    kept = []
    for det in sorted_dets:
        det_bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
        det_cls = getattr(det, "class_name", "") or (det.get("class_name", "") if isinstance(det, dict) else "")
        if not det_bbox or len(det_bbox) != 4:
            continue
        dx1, dy1, dx2, dy2 = det_bbox
        d_w = max(1.0, float(dx2 - dx1))
        d_h = max(1.0, float(dy2 - dy1))
        d_area = d_w * d_h
        d_center = ((dx1 + dx2) / 2.0, (dy1 + dy2) / 2.0)

        is_dup = False
        for k in kept:
            k_bbox = getattr(k, "bbox", None) or (k.get("bbox") if isinstance(k, dict) else None)
            k_cls = getattr(k, "class_name", "") or (k.get("class_name", "") if isinstance(k, dict) else "")
            if not are_classes_compatible(det_cls, k_cls):
                continue

            kx1, ky1, kx2, ky2 = k_bbox
            k_w = max(1.0, float(kx2 - kx1))
            k_h = max(1.0, float(ky2 - ky1))
            k_area = k_w * k_h
            k_center = ((kx1 + kx2) / 2.0, (ky1 + ky2) / 2.0)

            cur_iou = iou(det_bbox, k_bbox)

            # Calculate intersection and containment ratio
            ix1 = max(dx1, kx1)
            iy1 = max(dy1, ky1)
            ix2 = min(dx2, kx2)
            iy2 = min(dy2, ky2)
            inter_area = max(0.0, float(ix2 - ix1)) * max(0.0, float(iy2 - iy1))
            min_area = min(d_area, k_area)
            containment = (inter_area / min_area) if min_area > 0 else 0.0

            center_dist = calculate_distance(d_center, k_center)
            min_dim = min(d_w, d_h, k_w, k_h)

            is_person = (det_cls.lower().strip() in PERSON_CLASSES and k_cls.lower().strip() in PERSON_CLASSES)

            if is_person:
                # Deduplication criteria for duplicate person boxes:
                # 1. Standard IoU overlap > 0.45
                # 2. High containment (> 0.65) where one box is largely inside the other (e.g. torso vs full body)
                #    and centers are reasonably aligned
                # 3. Very close centers (< 40px) and moderate IoU (> 0.30)
                if cur_iou > 0.45:
                    is_dup = True
                    break
                if containment > 0.65 and center_dist < min_dim * 0.65:
                    is_dup = True
                    break
                if center_dist < 40.0 and cur_iou > 0.30:
                    is_dup = True
                    break
            else:
                # General objects (phones, calculators, books)
                if cur_iou > iou_thresh:
                    is_dup = True
                    break
                if containment > 0.70 and center_dist < min_dim * 0.5:
                    is_dup = True
                    break

        if not is_dup:
            kept.append(det)
    return kept


# --------------------------------------------------
# 8-Dimensional Kalman Filter for Bounding Boxes
# --------------------------------------------------
class KalmanBoxTracker:
    """DeepSORT-standard 8D Kalman Filter for bounding box tracking.

    State: [cx, cy, w, h, v_cx, v_cy, v_w, v_h]
    """

    def __init__(self, bbox: Tuple[int, int, int, int]):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        w = max(1.0, float(x2 - x1))
        h = max(1.0, float(y2 - y1))

        self.x = np.array([cx, cy, w, h, 0.0, 0.0, 0.0, 0.0], dtype=float)

        self.F = np.eye(8, dtype=float)
        for i in range(4):
            self.F[i, i + 4] = 1.0

        self.H = np.zeros((4, 8), dtype=float)
        for i in range(4):
            self.H[i, i] = 1.0

        self.P = np.diag([10.0, 10.0, 10.0, 10.0, 100.0, 100.0, 100.0, 100.0])
        self.Q = np.diag([1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0])
        self.R = np.diag([1.0, 1.0, 2.0, 2.0])

    def predict(self) -> Tuple[int, int, int, int]:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.get_bbox()

    def update(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        w = max(1.0, float(x2 - x1))
        h = max(1.0, float(y2 - y1))

        z = np.array([cx, cy, w, h], dtype=float)
        y = z - (self.H @ self.x)
        S = (self.H @ self.P @ self.H.T) + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I = np.eye(8, dtype=float)
        self.P = (I - K @ self.H) @ self.P
        return self.get_bbox()

    def get_bbox(self) -> Tuple[int, int, int, int]:
        cx = self.x[0]
        cy = self.x[1]
        w = max(1.0, self.x[2])
        h = max(1.0, self.x[3])
        return (
            int(round(cx - w / 2.0)),
            int(round(cy - h / 2.0)),
            int(round(cx + w / 2.0)),
            int(round(cy + h / 2.0)),
        )


# --------------------------------------------------
# Track Data Structure
# --------------------------------------------------
@dataclass
class Track:
    track_id: int
    bbox: Tuple[int, int, int, int]
    confidence: float
    class_name: str = "person"

    hits: int = 1
    time_since_update: int = 0
    state: str = "confirmed"

    last_detection_frame: int = 0
    last_detection_timestamp: float = 0.0
    time_since_detection: int = 0
    is_currently_detected: bool = True

    history: List[Tuple[int, int]] = field(default_factory=list)
    max_history: int = 30

    objects_detected: List[Any] = field(default_factory=list)
    neighbors: List[int] = field(default_factory=list)

    safe: bool = False
    phone_confidence: float = 0.0

    features: deque = field(default_factory=lambda: deque(maxlen=30))
    kf: Optional[KalmanBoxTracker] = None

    def __post_init__(self):
        if self.kf is None:
            self.kf = KalmanBoxTracker(self.bbox)

    @property
    def is_confirmed(self) -> bool:
        return self.state == "confirmed"

    @property
    def is_active(self) -> bool:
        return self.time_since_update <= 40

    @property
    def center(self) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def update_history(self) -> None:
        self.history.append(self.center)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def predict(self) -> Tuple[int, int, int, int]:
        if self.kf is not None:
            self.bbox = self.kf.predict()
        return self.bbox

    def update_measurement(
        self,
        bbox: Tuple[int, int, int, int],
        confidence: float,
        class_name: Optional[str] = None,
        feature: Optional[np.ndarray] = None,
    ) -> None:
        if self.kf is not None:
            self.bbox = self.kf.update(bbox)
        else:
            self.bbox = bbox

        self.confidence = float(confidence)
        self.hits += 1
        self.time_since_update = 0
        self.time_since_detection = 0
        self.is_currently_detected = True
        self.update_history()

        if feature is not None:
            self.features.append(feature)

        # Semantic class persistence: verified specialized classes survive YOLO generic labels
        if class_name:
            current_c = self.class_name.lower().strip()
            new_c = class_name.lower().strip()
            # LAPTOP is strictly forbidden from overwriting any track
            if new_c == "laptop":
                pass
            # Do not downgrade confirmed scientific calculator to cell phone
            elif current_c in {"scientific_calculator", "calculator"} and new_c in {"cell phone", "phone", "mobile"}:
                pass
            # Do not downgrade confirmed answer sheet to raw book
            elif current_c == "answer_sheet" and new_c in {"book", "paper sheet"}:
                pass
            else:
                self.class_name = class_name
                if new_c in {"cell phone", "phone", "mobile"}:
                    self.phone_confidence = float(confidence)
                elif new_c in {"scientific_calculator", "calculator"}:
                    self.phone_confidence = 0.0


# --------------------------------------------------
# Tracking Agent
# --------------------------------------------------
class TrackingAgent:
    """DeepSORT Real-Time Multi-Object Tracking Agent.

    Maintains stable identities across consecutive frames with Kalman motion prediction,
    Hungarian bipartite matching, appearance cosine distance re-ID, and class-aware gating.
    """

    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        tr = cfg.get("tracking", {})

        self.max_age: int = int(tr.get("max_age", 40))
        self.min_hits: int = int(tr.get("min_hits", 1))
        self.iou_threshold: float = float(tr.get("iou_threshold", 0.30))
        self.distance_threshold: float = float(tr.get("distance_threshold", 150.0))
        self.matching_threshold: float = float(tr.get("matching_threshold", 0.75))
        self.person_object_max_dist: float = float(tr.get("person_object_max_dist", 220.0))

        self.tracks: Dict[int, Track] = {}
        self.next_id: int = 1
        self.frame_count: int = 0

    def update(self, detections: List[Any], frame: Optional[np.ndarray] = None) -> List[Track]:
        """Update tracker with new frame detections.

        Args:
            detections: List of Detection objects or dicts from YOLO / perception layers.
            frame: Optional BGR frame image for appearance feature extraction.

        Returns:
            List of confirmed Track objects that are CURRENTLY DETECTED in this frame.
        """
        import time as _time
        self.frame_count += 1
        now_ts = _time.time()

        # 1. Coordinate sanitation and validation
        valid_dets = []
        for d in detections:
            cname = (getattr(d, "class_name", "") or (d.get("class_name", "") if isinstance(d, dict) else "")).lower().strip()
            if cname == "laptop":
                continue
            bbox = getattr(d, "bbox", None) or (d.get("bbox") if isinstance(d, dict) else None)
            conf = getattr(d, "confidence", 0.0) or (d.get("confidence", 0.0) if isinstance(d, dict) else 0.0)
            if not bbox or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            if not (np.isfinite(x1) and np.isfinite(y1) and np.isfinite(x2) and np.isfinite(y2) and np.isfinite(conf)):
                continue
            x1, y1, x2, y2 = int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))
            if frame is not None:
                h_f, w_f = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_f, x2), min(h_f, y2)
            if x2 <= x1 or y2 <= y1 or (x2 - x1) * (y2 - y1) < 16:
                continue
            valid_dets.append(d)

        # 2. Pre-tracking NMS deduplication (suppresses duplicate person and object boxes)
        deduped_dets = deduplicate_detections(valid_dets, iou_thresh=0.50)

        # 3. Kalman prediction step for active tracks
        for track in self.tracks.values():
            track.predict()

        # 4. Extract appearance features from frame crops if available
        det_features = []
        for d in deduped_dets:
            dbbox = getattr(d, "bbox", None) or (d.get("bbox") if isinstance(d, dict) else None)
            f = extract_appearance_feature(frame, dbbox) if (frame is not None and dbbox) else None
            det_features.append(f)

        # 5. Global optimal Hungarian association
        track_list = list(self.tracks.values())
        N = len(track_list)
        M = len(deduped_dets)

        matched_tracks = set()
        matched_dets = set()

        if N > 0 and M > 0:
            cost_matrix = np.full((N, M), 1000.0, dtype=float)
            for i, track in enumerate(track_list):
                for j, det in enumerate(deduped_dets):
                    det_cls = getattr(det, "class_name", "") or (det.get("class_name", "") if isinstance(det, dict) else "")
                    if not are_classes_compatible(track.class_name, det_cls):
                        continue

                    det_bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
                    iou_score = iou(track.bbox, det_bbox)
                    det_center = ((det_bbox[0] + det_bbox[2]) // 2, (det_bbox[1] + det_bbox[3]) // 2)
                    dist = calculate_distance(track.center, det_center)

                    if iou_score == 0.0 and dist > self.distance_threshold:
                        continue

                    d_iou = 1.0 - iou_score
                    d_dist = min(1.0, dist / max(100.0, self.distance_threshold))

                    feat = det_features[j]
                    if feat is not None and len(track.features) > 0:
                        d_app = min(cosine_distance(f, feat) for f in track.features)
                        # Soften appearance gate so minor lighting/pose shifts don't reject valid spatial match
                        if d_app > 0.70 and iou_score < 0.20:
                            continue
                        cost = 0.5 * d_iou + 0.3 * d_app + 0.2 * d_dist
                    else:
                        cost = 0.7 * d_iou + 0.3 * d_dist

                    cost_matrix[i, j] = cost

            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] < self.matching_threshold:
                    track = track_list[r]
                    det = deduped_dets[c]
                    det_bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
                    det_conf = getattr(det, "confidence", 0.0) or (det.get("confidence", 0.0) if isinstance(det, dict) else 0.0)
                    det_cls = getattr(det, "class_name", "") or (det.get("class_name", "") if isinstance(det, dict) else "")
                    track.update_measurement(det_bbox, det_conf, class_name=det_cls, feature=det_features[c])
                    track.last_detection_frame = self.frame_count
                    track.last_detection_timestamp = now_ts
                    track.time_since_detection = 0
                    track.is_currently_detected = True
                    if hasattr(det, "track_id"):
                        det.track_id = track.track_id
                    matched_tracks.add(track.track_id)
                    matched_dets.add(c)
                    logger.debug(f"[TRACKER] Track {track.track_id} ({track.class_name}) matched detection (cost={cost_matrix[r, c]:.2f})")

        # 6. Unmatched tracks: advance time_since_update and mark not currently detected
        for track in track_list:
            if track.track_id not in matched_tracks:
                track.time_since_update += 1
                track.time_since_detection += 1
                track.is_currently_detected = False
                logger.debug(f"[TRACKER] Track {track.track_id} unmatched (TimeSinceUpdate={track.time_since_update})")

        # 7. Unmatched detections: create new track
        for j, det in enumerate(deduped_dets):
            if j not in matched_dets:
                det_bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
                det_conf = getattr(det, "confidence", 0.0) or (det.get("confidence", 0.0) if isinstance(det, dict) else 0.0)
                det_cls = getattr(det, "class_name", "") or (det.get("class_name", "person") if isinstance(det, dict) else "person")
                p_conf = float(det_conf) if det_cls in {"cell phone", "phone", "mobile"} else 0.0
                t = Track(
                    track_id=self.next_id,
                    bbox=det_bbox,
                    confidence=det_conf,
                    class_name=det_cls,
                    hits=1,
                    time_since_update=0,
                    time_since_detection=0,
                    is_currently_detected=True,
                    last_detection_frame=self.frame_count,
                    last_detection_timestamp=now_ts,
                    state="confirmed" if self.min_hits <= 1 else "tentative",
                    phone_confidence=p_conf,
                )
                if det_features[j] is not None:
                    t.features.append(det_features[j])
                t.update_history()
                if hasattr(det, "track_id"):
                    det.track_id = t.track_id
                self.tracks[self.next_id] = t
                logger.debug(f"[TRACKER] Created new Track {self.next_id} ({det_cls}) at {det_bbox}")
                self.next_id += 1

        # 8. Person-object spatial linking (preserves student-device context)
        # ONLY link CURRENTLY DETECTED objects to CURRENTLY DETECTED persons
        person_tracks = [t for t in self.tracks.values() if t.class_name == "person" and t.is_confirmed and t.is_currently_detected]
        object_tracks = [t for t in self.tracks.values() if t.class_name != "person" and t.is_confirmed and t.is_currently_detected]
        for p in person_tracks:
            p.objects_detected = []

        for obj in object_tracks:
            if obj.confidence < 0.25:
                continue

            ox1, oy1, ox2, oy2 = obj.bbox
            ocx, ocy = obj.center
            is_large_object = obj.class_name in {"book", "answer book", "notebook", "paper sheet", "answer_sheet", "desk", "chair"}
            max_allowed_dist = 260.0 if is_large_object else self.person_object_max_dist

            best_p = None
            min_p_dist = float('inf')

            for p in person_tracks:
                px1, py1, px2, py2 = p.bbox
                # Distance from object center to person bounding box
                dx = max(0, px1 - ocx, ocx - px2)
                dy = max(0, py1 - ocy, ocy - py2)
                box_dist = float((dx ** 2 + dy ** 2) ** 0.5)
                center_dist = calculate_distance(p.center, (ocx, ocy))

                eff_dist = min(box_dist, center_dist)
                if eff_dist < max_allowed_dist and eff_dist < min_p_dist:
                    min_p_dist = eff_dist
                    best_p = p

            if best_p is not None:
                obj_area = (ox2 - ox1) * (oy2 - oy1)
                p_conf = float(
                    getattr(obj, "phone_confidence", 0.0)
                    or (obj.confidence if obj.class_name in {"cell phone", "phone", "mobile"} else 0.0)
                )
                best_p.objects_detected.append({
                    "class_name": obj.class_name,
                    "confidence": obj.confidence,
                    "bbox": obj.bbox,
                    "area": obj_area,
                    "track_id": obj.track_id,
                    "safe": getattr(obj, "safe", False),
                    "phone_confidence": p_conf,
                })

        # 9. Spatial neighbor graph
        for t1 in self.tracks.values():
            t1.neighbors = []
            for t2 in self.tracks.values():
                if t1.track_id == t2.track_id:
                    continue
                if calculate_distance(t1.center, t2.center) < 150:
                    t1.neighbors.append(t2.track_id)

        # 10. Delete expired tracks
        remove_ids = [
            tid for tid, t in self.tracks.items()
            if t.time_since_update > self.max_age
        ]
        for tid in remove_ids:
            logger.debug(f"[TRACKER] Deleted expired Track {tid} ({self.tracks[tid].class_name})")
            del self.tracks[tid]

        # 🔍 Lightweight throttled diagnostic logging
        if self.frame_count % 30 == 0 or any(t.class_name in {"cell phone", "calculator"} for t in self.tracks.values()):
            active_trks = [t for t in self.tracks.values() if t.is_confirmed and t.is_currently_detected]
            trk_str = ", ".join([f"ID:{t.track_id}({t.class_name}:{t.confidence:.2f})" for t in active_trks]) or "none"
            logger.debug(f"[DIAGNOSTIC] Frame {self.frame_count} | TRACKS: [{trk_str}]")

        # Public tracking results contain ONLY confirmed tracks with CURRENT-FRAME detection.
        # Internal tracker maintains history/Kalman state in self.tracks for re-identification.
        return [t for t in self.tracks.values() if t.is_confirmed and t.is_currently_detected]

    def draw_tracks(self, frame: np.ndarray, tracks: Optional[List[Track]] = None) -> np.ndarray:
        """Render track identifiers on the frame adhering strictly to the Display Rule:
        ONLY DRAW A TRACK IF:
        1. It is confirmed
        2. It has a current-frame detection (is_currently_detected == True)
        3. The detection has valid class information
        4. The detection has valid coordinates (x2 > x1 and y2 > y1)
        5. The detection has not expired
        Do NOT draw a predicted Kalman box as though it were a confirmed current detection.
        """
        if tracks is None:
            tracks = [t for t in self.tracks.values() if t.is_confirmed and t.is_currently_detected]
        out = frame.copy()

        for t in tracks:
            # Display rule enforcement:
            if not getattr(t, "is_confirmed", False) or not getattr(t, "is_currently_detected", False):
                continue
            if getattr(t, "class_name", "").lower().strip() == "laptop":
                continue

            bbox = getattr(t, "bbox", None)
            if not bbox or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = [int(v) for v in bbox]
            if x2 <= x1 or y2 <= y1:
                continue

            cname = getattr(t, "class_name", "person").lower()

            if cname in {"cell phone", "phone", "mobile"}:
                color = (0, 0, 255)       # Red
                text_color = (255, 255, 255)
            elif cname in {"scientific_calculator", "calculator"}:
                color = (0, 255, 128)     # Spring Green
                text_color = (0, 0, 0)
            elif cname == "answer_sheet":
                color = (0, 215, 255)     # Cyan
                text_color = (0, 0, 0)
            elif cname in {"book", "paper sheet", "notebook"}:
                color = (0, 165, 255)     # Orange
                text_color = (255, 255, 255)
            elif cname == "person":
                color = (0, 255, 0)       # Green
                text_color = (0, 0, 0)
            else:
                color = (200, 200, 200)
                text_color = (0, 0, 0)

            # Draw bounding box
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

            # Formulate full label: ID: {id} | {CLASS} | {conf:.2f}
            cls_display = t.class_name.upper()
            label = f"ID:{t.track_id} | {cls_display} | {t.confidence:.2f}"

            text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            tx = x1
            if tx + text_size[0] + 8 > out.shape[1]:
                tx = max(0, out.shape[1] - text_size[0] - 10)
            ty = max(24, y1)

            cv2.rectangle(out, (tx, ty - 24), (tx + text_size[0] + 8, ty), color, -1)
            cv2.putText(
                out,
                label,
                (tx + 4, ty - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                text_color,
                2,
            )

        return out

    def update_track_class(self, track_id: int, new_class: str, safe: Optional[bool] = None) -> bool:
        """Update the semantic classification of a track (e.g. from Gemini re-verification)."""
        if (new_class or "").lower().strip() == "laptop":
            return False
        track = self.tracks.get(track_id)
        if track:
            track.class_name = new_class
            if safe is not None:
                track.safe = safe
            return True
        return False

    def get_track(self, track_id: int) -> Optional[Track]:
        """Retrieve an active track by ID."""
        return self.tracks.get(track_id)

    def reset(self) -> None:
        """Reset tracker state."""
        self.tracks = {}
        self.next_id = 1
        self.frame_count = 0