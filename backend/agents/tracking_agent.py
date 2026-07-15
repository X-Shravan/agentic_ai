from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import cv2
import numpy as np


# --------------------------------------------------
# Track Data
# --------------------------------------------------
@dataclass
class Track:
    track_id: int
    bbox: Tuple[int, int, int, int]
    confidence: float

    hits: int = 1
    time_since_update: int = 0
    state: str = "tentative"

    history: List[Tuple[int, int]] = field(default_factory=list)
    max_history: int = 30

    objects_detected: List[str] = field(default_factory=list)
    neighbors: List[int] = field(default_factory=list)

    @property
    def is_confirmed(self):
        return self.state == "confirmed"

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def update_history(self):
        self.history.append(self.center)
        if len(self.history) > self.max_history:
            self.history.pop(0)


# --------------------------------------------------
# Utils
# --------------------------------------------------
def calculate_distance(a, b):
    return ((a[0] - b[0])**2 + (a[1] - b[1])**2)**0.5


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = ((ax2 - ax1) * (ay2 - ay1)) + ((bx2 - bx1) * (by2 - by1)) - inter

    return inter / union if union > 0 else 0


# --------------------------------------------------
# Tracking Agent
# --------------------------------------------------
class TrackingAgent:

    def __init__(self, config):

        tr = config.get("tracking", {})

        self.max_age = tr.get("max_age", 40)
        self.min_hits = tr.get("min_hits", 2)
        self.iou_threshold = tr.get("iou_threshold", 0.3)
        self.distance_threshold = 100

        self.tracks: Dict[int, Track] = {}
        self.next_id = 1

    # --------------------------------------------------
    def update(self, detections) -> List[Track]:

        persons = [d for d in detections if d.class_name == "person"]
        objects = [d for d in detections if d.class_name != "person"]

        assigned = set()

        # ---------------------------
        # Match tracks
        # ---------------------------
        for track in self.tracks.values():

            best_idx = -1
            best_score = 0

            for i, det in enumerate(persons):

                if i in assigned:
                    continue

                iou_score = iou(track.bbox, det.bbox)
                dist = calculate_distance(track.center, det.center)

                if iou_score > self.iou_threshold or dist < self.distance_threshold:

                    score = iou_score - (dist / 1000)

                    if score > best_score:
                        best_score = score
                        best_idx = i

            if best_idx >= 0:

                det = persons[best_idx]
                assigned.add(best_idx)

                track.bbox = det.bbox
                track.confidence = det.confidence

                track.hits += 1
                track.time_since_update = 0
                track.update_history()

                if track.hits >= self.min_hits:
                    track.state = "confirmed"

            else:
                track.time_since_update += 1

        # ---------------------------
        # Create new tracks
        # ---------------------------
        for i, det in enumerate(persons):

            if i in assigned:
                continue

            t = Track(
                track_id=self.next_id,
                bbox=det.bbox,
                confidence=det.confidence,
            )

            t.update_history()

            self.tracks[self.next_id] = t
            self.next_id += 1

        # ---------------------------
        # Assign objects (IMPROVED - handles mobile + books)
        # ---------------------------
        for track in self.tracks.values():

            track.objects_detected = []

            for obj in objects:

                dist = calculate_distance(track.center, obj.center)

                # 🔥 MOBILE PHONE DETECTION
                if obj.class_name == "cell phone":
                    if dist < 120 and obj.confidence >= 0.55:
                        # Calculate bounding box area
                        obj_area = (obj.bbox[2] - obj.bbox[0]) * (obj.bbox[3] - obj.bbox[1])
                        
                        # Pass full object data for behavior analysis
                        track.objects_detected.append({
                            "class_name": "cell phone",
                            "confidence": obj.confidence,
                            "bbox": obj.bbox,
                            "area": obj_area
                        })
                        print(f"🔗 MOBILE linked to track {track.track_id}")
                
                # ✅ BOOK DETECTION (NEW) - also assign to track
                elif obj.class_name == "book":
                    if dist < 200:  # Books can be further away
                        obj_area = (obj.bbox[2] - obj.bbox[0]) * (obj.bbox[3] - obj.bbox[1])
                        
                        track.objects_detected.append({
                            "class_name": "book",
                            "confidence": obj.confidence,
                            "bbox": obj.bbox,
                            "area": obj_area
                        })
                        print(f"📚 BOOK linked to track {track.track_id}")

        # ---------------------------
        # Detect neighbors (FIXED)
        # ---------------------------
        for t1 in self.tracks.values():

            t1.neighbors = []

            for t2 in self.tracks.values():

                if t1.track_id == t2.track_id:
                    continue

                dist = calculate_distance(t1.center, t2.center)

                if dist < 150:   # 👈 adjust if needed
                    t1.neighbors.append(t2.track_id)

        # ---------------------------
        # Remove old tracks
        # ---------------------------
        remove_ids = [
            tid for tid, t in self.tracks.items()
            if t.time_since_update > self.max_age
        ]

        for tid in remove_ids:
            del self.tracks[tid]

        return [t for t in self.tracks.values() if t.is_confirmed]

    # --------------------------------------------------
    def draw_tracks(self, frame, tracks=None):

        tracks = tracks or [t for t in self.tracks.values() if t.is_confirmed]

        out = frame.copy()

        for t in tracks:

            x1, y1, x2, y2 = t.bbox

            cv2.rectangle(out, (x1, y1), (x2, y2), (255, 255, 0), 2)

            cv2.putText(
                out,
                f"ID:{t.track_id}",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                2,
            )

        return out

    # --------------------------------------------------
    def reset(self):
        self.tracks = {}
        self.next_id = 1