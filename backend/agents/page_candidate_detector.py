"""Lightweight OpenCV-based Page Candidate Detector for Exam Surveillance.

Identifies potential paper/page-like regions in live camera frames
independently of YOLO, supporting both portrait and landscape orientations,
as well as tilted/rotated paper.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PageCandidate:
    """Represents a candidate paper/page region detected in a camera frame."""
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    score: float                     # Combined candidate score [0.0 - 1.0]
    area_ratio: float                # Bounding box area / frame area
    aspect_ratio: float              # long_side / short_side (>= 1.0)
    orientation: str                 # 'portrait' | 'landscape'
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def center(self) -> Tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return max(1, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> int:
        return max(1, self.bbox[3] - self.bbox[1])


class PageCandidateDetector:
    """
    Fast, lightweight OpenCV-based candidate detector for answer sheets.
    
    Operates independently of YOLO and evaluates:
    1. Brightness / Whiteness of paper in HSV and Grayscale.
    2. Contour geometry and aspect ratio (orientation-agnostic: long_side / short_side).
    3. Polygon shape (4-corner approximation / perspective tolerance).
    4. Ruled line structure (horizontal, vertical, or tilted line patterns).
    5. Frame area ratio (PAGE_MIN_AREA_RATIO to catch distant sheets).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        candidate_cfg = cfg.get("page_candidate_detector", {})
        
        # Configurable thresholds
        self.enabled = candidate_cfg.get("enabled", True)
        self.min_area_ratio = candidate_cfg.get("min_area_ratio", 0.015)   # ~4,600 px in 640x480
        self.max_area_ratio = candidate_cfg.get("max_area_ratio", 0.95)
        self.score_threshold = candidate_cfg.get("score_threshold", 0.40)
        self.min_dimension = candidate_cfg.get("min_dimension", 40)       # Min width/height in px
        self.max_candidates = candidate_cfg.get("max_candidates", 3)

    def detect_candidates(self, frame: np.ndarray) -> List[PageCandidate]:
        """
        Detect page-like candidate bounding boxes in the live frame.
        
        Args:
            frame: Live BGR camera frame.
            
        Returns:
            List of PageCandidate objects sorted by candidate score descending.
        """
        if not self.enabled or frame is None or frame.size == 0:
            return []

        h_frame, w_frame = frame.shape[:2]
        frame_area = float(h_frame * w_frame)
        if frame_area <= 0:
            return []

        # 1. Color / Whiteness Masking
        # Convert to HSV and Grayscale
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Classroom lighting white paper range:
        # Low saturation (paper is white/off-white) and moderate-to-high brightness
        lower_white = np.array([0, 0, 95], dtype=np.uint8)
        upper_white = np.array([180, 90, 255], dtype=np.uint8)
        white_mask = cv2.inRange(hsv, lower_white, upper_white)

        # Also combine with grayscale intensity threshold
        _, gray_thresh = cv2.threshold(gray, 115, 255, cv2.THRESH_BINARY)
        combined_mask = cv2.bitwise_and(white_mask, gray_thresh)

        # Morphological close to join paper across ruled lines and printed text
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        closed_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel_close)

        # 2. Find Contours
        contours, _ = cv2.findContours(closed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []

        candidates: List[PageCandidate] = []

        for cnt in contours:
            contour_area = cv2.contourArea(cnt)
            area_ratio = contour_area / frame_area

            # Area filtering
            if area_ratio < self.min_area_ratio or area_ratio > self.max_area_ratio:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if w < self.min_dimension or h < self.min_dimension:
                continue

            # Orientation computation (strictly neutral)
            short_side = float(min(w, h))
            long_side = float(max(w, h))
            aspect_ratio = (long_side / short_side) if short_side > 0 else 1.0
            orientation = "portrait" if h >= w else "landscape"

            # 3. Geometry & Solidity Score
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = (contour_area / hull_area) if hull_area > 0 else 0.0

            # Reasonable page aspect ratios (A4 is 1.41; perspective/partial views: 1.0 to 3.5)
            if aspect_ratio > 4.0:
                continue

            # Geometry score: rewards solid, rectangular-like shapes
            geometry_score = 0.0
            if 1.1 <= aspect_ratio <= 2.5:
                geometry_score += 0.5
            elif 1.0 <= aspect_ratio <= 3.5:
                geometry_score += 0.3

            if solidity >= 0.75:
                geometry_score += 0.5
            elif solidity >= 0.60:
                geometry_score += 0.3
            geometry_score = min(1.0, geometry_score)

            # 4. Rectangle / Polygon Approximation Score
            perimeter = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * perimeter, True)
            num_vertices = len(approx)

            rectangle_score = 0.0
            if num_vertices == 4:
                rectangle_score = 1.0  # Clear 4-corner perspective quad
            elif num_vertices in (5, 6):
                rectangle_score = 0.7  # Partial or perspective-clipped quad
            elif num_vertices in (7, 8):
                rectangle_score = 0.4
            else:
                rectangle_score = 0.2

            # 5. Whiteness inside bounding box
            crop_mask = white_mask[y:y+h, x:x+w]
            whiteness_ratio = float(np.sum(crop_mask > 0) / (w * h)) if (w * h) > 0 else 0.0
            whiteness_score = min(1.0, whiteness_ratio / 0.40)  # max at 40%+ white pixels

            # 6. Ruled Lines / Line Structure Score
            crop_gray = gray[y:y+h, x:x+w]
            line_structure_score = self._evaluate_line_structure(crop_gray, min(w, h))

            # 7. Combined Candidate Score
            # Geometry (30%), Whiteness (30%), Rectangle (20%), Line structure (20%)
            candidate_score = (
                0.30 * geometry_score
                + 0.30 * whiteness_score
                + 0.20 * rectangle_score
                + 0.20 * line_structure_score
            )

            # Boost score slightly if area is substantial
            if area_ratio >= 0.05:
                candidate_score = min(1.0, candidate_score + 0.10)

            if candidate_score >= self.score_threshold:
                # Clamp bbox to frame boundaries
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(w_frame, x + w)
                y2 = min(h_frame, y + h)

                cand = PageCandidate(
                    bbox=(x1, y1, x2, y2),
                    score=float(candidate_score),
                    area_ratio=float(area_ratio),
                    aspect_ratio=float(aspect_ratio),
                    orientation=orientation,
                    details={
                        "geometry_score": float(geometry_score),
                        "whiteness_score": float(whiteness_score),
                        "rectangle_score": float(rectangle_score),
                        "line_structure_score": float(line_structure_score),
                        "solidity": float(solidity),
                        "num_vertices": int(num_vertices),
                    }
                )
                candidates.append(cand)

        # Sort by candidate score descending and limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:self.max_candidates]

    def _evaluate_line_structure(self, crop_gray: np.ndarray, min_dim: int) -> float:
        """
        Evaluate horizontal, vertical, or tilted line structure as a supporting paper signal.
        Orientation agnostic: checks for repeating line patterns across any angle.
        """
        if crop_gray is None or crop_gray.size < 100 or min_dim < 20:
            return 0.0

        try:
            edges = cv2.Canny(crop_gray, 30, 100)
            min_line_len = max(15, int(min_dim * 0.18))
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180,
                threshold=25,
                minLineLength=min_line_len,
                maxLineGap=12
            )

            if lines is None or len(lines) == 0:
                return 0.1

            line_count = len(lines)
            if line_count >= 6:
                return 1.0
            elif line_count >= 3:
                return 0.7
            elif line_count >= 1:
                return 0.4
            return 0.1
        except Exception:
            return 0.0
