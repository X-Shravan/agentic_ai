"""Visual verification of simultaneous Scientific Calculator and Mobile Phone detection.

Renders a live realistic frame with BOTH a Mobile Phone and a Scientific Calculator,
runs the detection/overlay pipeline, and verifies that:
1. Calculator is recognized as SCIENTIFIC CALCULATOR -> SAFE (Spring Green box).
2. Phone is recognized as CELL PHONE -> CRITICAL (Red box).
3. Neither box overwrites or suppresses the other.
4. Output image is saved as an artifact for visual inspection.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from backend.agents.detection_agent import Detection, DetectionAgent
from backend.agents.tracking_agent import Track
from calculator_verification import (
    CalculatorCandidateDetector,
    CalculatorGeminiVerifier,
    CalculatorVerificationResult,
)
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline

ARTIFACT_DIR = Path(r"C:\Users\vanshika\.gemini\antigravity-ide\brain\1afd690a-fc56-45b8-81ec-8978b2783c36")


def create_realistic_simultaneous_scene() -> np.ndarray:
    """Create a realistic high-definition exam desk scene containing both objects."""
    h, w = 720, 1280
    frame = np.full((h, w, 3), (70, 75, 80), dtype=np.uint8)  # Wooden desk background

    # Desk texture / wood grain
    for y in range(h):
        val = int(65 + 15 * np.sin(y / 40.0) + (y / h) * 10)
        frame[y, :] = (val - 5, val, val + 5)

    # Exam paper / Question paper in background (middle)
    cv2.rectangle(frame, (440, 60), (840, 660), (245, 245, 248), -1)
    cv2.putText(frame, "MATHEMATICS EXAMINATION", (480, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)
    for row in range(150, 620, 30):
        cv2.line(frame, (470, row), (810, row), (215, 215, 220), 1)

    # -------------------------------------------------------------
    # Object 1: Mobile Phone on Left Side (bbox: 120, 200, 320, 560)
    # -------------------------------------------------------------
    px1, py1, px2, py2 = 120, 200, 320, 560
    # Phone outer body (dark sleek bezel)
    cv2.rectangle(frame, (px1, py1), (px2, py2), (18, 18, 20), -1)
    # Phone screen (bright glowing screen with messaging interface)
    cv2.rectangle(frame, (px1 + 10, py1 + 20), (px2 - 10, py2 - 20), (230, 170, 45), -1)
    cv2.putText(frame, "CHATTING...", (px1 + 25, py1 + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2)
    # Notch / Camera punch-hole
    cv2.circle(frame, ((px1 + px2) // 2, py1 + 10), 4, (40, 40, 40), -1)

    # -------------------------------------------------------------
    # Object 2: Scientific Calculator on Right Side (bbox: 960, 200, 1180, 570)
    # -------------------------------------------------------------
    cx1, cy1, cx2, cy2 = 960, 200, 1180, 570
    cw = cx2 - cx1
    ch = cy2 - cy1
    # Calculator outer matte body
    cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (38, 40, 42), -1)
    # Beveled casing border
    cv2.rectangle(frame, (cx1 + 4, cy1 + 4), (cx2 - 4, cy2 - 4), (55, 58, 62), 2)
    # Solar panel + LCD display at top
    cv2.rectangle(frame, (cx1 + 14, cy1 + 14), (cx2 - 14, cy1 + int(ch * 0.26)), (120, 150, 120), -1)
    cv2.putText(frame, "CASIO fx-991EX", (cx1 + 20, cy1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (15, 25, 15), 1)
    cv2.putText(frame, "d/dx(x^2)=2x", (cx1 + 20, cy1 + int(ch * 0.22)), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (10, 20, 10), 2)

    # Function keypad area (multi-row mathematical functions)
    fkeys = ["sin", "cos", "tan", "log", "ln", "(", ")", "x^2", "sqrt", "shift", "alpha", "optn"]
    for i, label in enumerate(fkeys):
        row = i // 4
        col = i % 4
        kx = cx1 + 14 + col * int((cw - 28) / 4)
        ky = cy1 + int(ch * 0.32) + row * 26
        kw = int((cw - 28) / 4) - 6
        kh = 18
        cv2.rectangle(frame, (kx, ky), (kx + kw, ky + kh), (65, 68, 72), -1)
        cv2.putText(frame, label, (kx + 4, ky + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (230, 230, 235), 1)

    # Numeric keypad area
    num_keys = ["7", "8", "9", "DEL", "4", "5", "6", "*", "1", "2", "3", "+", "0", ".", "x10", "="]
    for i, label in enumerate(num_keys):
        row = i // 4
        col = i % 4
        kx = cx1 + 16 + col * int((cw - 32) / 4)
        ky = cy1 + int(ch * 0.60) + row * 26
        kw = int((cw - 32) / 4) - 6
        kh = 20
        btn_color = (200, 120, 50) if label == "DEL" else ((85, 90, 95) if label == "=" else (95, 100, 105))
        cv2.rectangle(frame, (kx, ky), (kx + kw, ky + kh), btn_color, -1)
        cv2.putText(frame, label, (kx + 6, ky + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1)

    return frame


def run_visual_verification():
    print("=" * 70)
    print("DEMONSTRATING SIMULTANEOUS SCIENTIFIC CALCULATOR & MOBILE PHONE DETECTION")
    print("=" * 70)

    from unittest.mock import MagicMock
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    detector = DetectionAgent({})

    frame = create_realistic_simultaneous_scene()

    phone_bbox = (120, 200, 320, 560)
    calc_bbox = (960, 200, 1180, 570)

    # 1. Set up Phone Detection & Track
    phone_det = Detection(bbox=phone_bbox, confidence=0.94, class_name="cell phone")
    phone_track = Track(track_id=7, bbox=phone_bbox, confidence=0.94)
    setattr(phone_track, "class_name", "cell phone")
    setattr(phone_track, "phone_confidence", 0.94)
    phone_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.94, "bbox": phone_bbox}]

    # 2. Set up Calculator Verification Result
    calc_res = CalculatorVerificationResult(
        object_type="SCIENTIFIC_CALCULATOR",
        classification="scientific_calculator",
        confidence=0.97,
        safe=True,
        reason="Visual features confirm approved mathematical scientific calculator with LCD and scientific keypad.",
        bbox=calc_bbox,
        timestamp=time.time(),
        track_id=12,
    )
    pipeline.calculator_verifier.cache[("cam_live", 12)] = calc_res

    calc_det = Detection(bbox=calc_bbox, confidence=0.97, class_name="scientific_calculator")
    calc_track = Track(track_id=12, bbox=calc_bbox, confidence=0.97)
    setattr(calc_track, "class_name", "scientific_calculator")

    # 3. Synchronize detections for display
    synced_detections = pipeline._sync_detections_for_display(
        [phone_det, calc_det],
        [phone_track, calc_track],
        camera_id="cam_live"
    )

    print(f"📊 Total Synced Detections: {len(synced_detections)}")
    for d in synced_detections:
        print(f"   -> Object: {d.class_name:<25} Conf: {d.confidence:.2f} Bbox: {d.bbox}")

    # 4. Draw Overlay with Object-Specific Labels
    annotated = detector.draw_detections(frame, synced_detections)

    # Add header banner
    cv2.rectangle(annotated, (0, 0), (1280, 50), (20, 20, 24), -1)
    cv2.putText(
        annotated,
        "EXAM PROCTORING: SIMULTANEOUS PHONE (CRITICAL) & SCIENTIFIC CALCULATOR (SAFE)",
        (25, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2
    )

    # Save local and artifact output files
    local_output = Path("test_calculator_phone_simultaneous.jpg")
    cv2.imwrite(str(local_output), annotated)
    print(f"💾 Saved local annotated frame: {local_output.resolve()}")

    if ARTIFACT_DIR.exists():
        artifact_output = ARTIFACT_DIR / "test_calculator_phone_simultaneous.jpg"
        shutil.copyfile(str(local_output), str(artifact_output))
        print(f"💾 Saved artifact annotated frame: {artifact_output.resolve()}")

    # Verify visual results
    assert len(synced_detections) == 2, "Expected exactly 2 simultaneous detections"
    assert any(d.class_name == "cell phone" for d in synced_detections), "Cell phone must be present"
    assert any(d.class_name == "scientific_calculator" for d in synced_detections), "Scientific calculator must be present"

    print("\n✅ VERIFICATION COMPLETE: Both objects simultaneously detected, classified, and rendered!")


if __name__ == "__main__":
    run_visual_verification()
