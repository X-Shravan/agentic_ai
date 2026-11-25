"""Isolated candidate detector for scientific calculators.
Belongs strictly to the calculator_verification module.
Does NOT modify or depend on Book or Answer Sheet detectors.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple
import cv2
import numpy as np

from calculator_verification.config import CalculatorConfig
from calculator_verification.models import CalculatorCandidate

logger = logging.getLogger(__name__)


class CalculatorCandidateDetector:
    """Detects or extracts scientific calculator candidates from frames or YOLO detections."""

    def __init__(self, config: Optional[CalculatorConfig] = None):
        self.config = config or CalculatorConfig()

    def detect_candidates(
        self,
        frame: np.ndarray,
        existing_detections: Optional[List[Any]] = None,
    ) -> List[CalculatorCandidate]:
        """
        Identify candidate calculator bounding boxes from:
        1. Direct YOLO detections if 'calculator' or 'scientific_calculator' exists.
        2. Isolated visual contour candidate detection if YOLO has no calculator detection.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        candidates: List[CalculatorCandidate] = []

        # -------------------------------------------------------------
        # Step 1: Check existing YOLO detections for calculator classes
        # -------------------------------------------------------------
        if existing_detections:
            for det in existing_detections:
                cname = getattr(det, "class_name", None) or (det.get("class_name") if isinstance(det, dict) else None)
                if cname in {"calculator", "scientific_calculator"}:
                    bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
                    conf = getattr(det, "confidence", None) or (det.get("confidence") if isinstance(det, dict) else 0.70)
                    tid = getattr(det, "track_id", None) or (det.get("track_id") if isinstance(det, dict) else None)
                    if bbox and len(bbox) == 4:
                        candidates.append(
                            CalculatorCandidate(
                                bbox=tuple(int(v) for v in bbox),
                                confidence=float(conf),
                                source="yolo",
                                track_id=tid,
                            )
                        )

        # If YOLO identified candidate calculator device(s), return them
        if candidates:
            return candidates

        # -------------------------------------------------------------
        # Step 2: Isolated visual candidate detector (fallback)
        # -------------------------------------------------------------
        visual_candidates = self._extract_visual_candidates(frame, existing_detections)
        return visual_candidates

    def _extract_visual_candidates(
        self,
        frame: np.ndarray,
        existing_detections: Optional[List[Any]] = None,
    ) -> List[CalculatorCandidate]:
        """
        Extract rectangular handheld candidates from the live camera frame.
        Excludes regions containing human faces/heads, mobile phones, or smartwatches.
        """
        h_f, w_f = frame.shape[:2]
        frame_area = float(w_f * h_f)

        # Build exclusion boxes from other objects
        exclusions = []
        if existing_detections:
            for det in existing_detections:
                cname = getattr(det, "class_name", None) or (det.get("class_name") if isinstance(det, dict) else "")
                bbox = getattr(det, "bbox", None) or (det.get("bbox") if isinstance(det, dict) else None)
                if not bbox or len(bbox) != 4:
                    continue
                bx1, by1, bx2, by2 = bbox
                if cname == "person":
                    # Exclude head/upper chest region of person
                    head_h = int((by2 - by1) * 0.40)
                    exclusions.append((bx1, by1, bx2, by1 + head_h))
                elif cname in {"smart watch"}:
                    exclusions.append((bx1, by1, bx2, by2))

        # Convert to grayscale and apply bilateral filter for edge preservation
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Adaptive threshold / Canny edge to find distinct physical boundaries
        edges = cv2.Canny(blurred, 40, 140)

        # Close gaps in contours
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        raw_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.config.candidate_min_area * 0.5:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            box_area = w * h

            # Validate area bounds
            if not (self.config.candidate_min_area <= box_area <= self.config.candidate_max_area):
                continue

            # Check aspect ratio (orientation agnostic)
            short_side = max(1, min(w, h))
            long_side = max(w, h)
            aspect = float(long_side) / float(short_side)
            if not (self.config.candidate_min_aspect_ratio <= aspect <= self.config.candidate_max_aspect_ratio):
                continue

            # Fill factor check (contour area vs bounding box area)
            fill_factor = float(area) / float(box_area)
            if fill_factor < self.config.candidate_min_fill_factor:
                continue

            # Exclude extreme top of screen (ceiling/wall)
            if (y + h // 2) < (h_f * 0.20):
                continue

            # Check overlap with exclusions (avoids duplicating phone or person head)
            cand_box = (x, y, x + w, y + h)
            overlap_found = False
            for ex_box in exclusions:
                iou_val = self._compute_iou(cand_box, ex_box)
                ix1 = max(cand_box[0], ex_box[0])
                iy1 = max(cand_box[1], ex_box[1])
                ix2 = min(cand_box[2], ex_box[2])
                iy2 = min(cand_box[3], ex_box[3])
                inter_area = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                cand_sub_ratio = inter_area / float(max(1, box_area))
                # Exclude if candidate is primarily (>65%) the excluded phone or head, or high IoU (>0.45)
                if iou_val > 0.45 or cand_sub_ratio > 0.65:
                    overlap_found = True
                    break
            if overlap_found:
                continue

            raw_candidates.append(
                CalculatorCandidate(
                    bbox=cand_box,
                    confidence=0.55,
                    source="candidate",
                )
            )

        # Apply NMS to eliminate overlapping candidates
        return self._nms_candidates(raw_candidates, iou_thresh=0.35)

    @staticmethod
    def _compute_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        area1 = max(1, (x2_1 - x1_1) * (y2_1 - y1_1))
        area2 = max(1, (x2_2 - x1_2) * (y2_2 - y1_2))
        union_area = area1 + area2 - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def _nms_candidates(self, candidates: List[CalculatorCandidate], iou_thresh: float = 0.35) -> List[CalculatorCandidate]:
        if not candidates:
            return []
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        keep = []
        for cand in candidates:
            suppressed = False
            for kept in keep:
                if self._compute_iou(cand.bbox, kept.bbox) > iou_thresh:
                    suppressed = True
                    break
            if not suppressed:
                keep.append(cand)
        return keep
