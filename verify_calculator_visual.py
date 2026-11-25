#!/usr/bin/env python3
"""
Visual and Functional Multi-Object Scene Verification.
Demonstrates the standalone scientific calculator feature operating independently alongside:
- Book detection (frozen)
- Answer sheet detection (frozen)
- Mobile phone detection (frozen)
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from backend.agents.detection_agent import Detection, DetectionAgent
from calculator_verification import (
    CalculatorCandidate,
    CalculatorCandidateDetector,
    CalculatorConfig,
    CalculatorGeminiVerifier,
    CalculatorVerificationResult,
)


def create_exam_desk_scene() -> np.ndarray:
    """Create a realistic exam desk scene with calculator, textbook, answer sheet, and phone."""
    desk = np.full((720, 1280, 3), (70, 80, 95), dtype=np.uint8)  # Wood-tone desk

    # 1. Answer Sheet (top-left / center): 400x500 white ruled page
    cv2.rectangle(desk, (80, 80), (480, 620), (248, 248, 248), -1)
    cv2.putText(desk, "SEMESTER EXAMINATION ANSWER SHEET", (100, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2)
    for y in range(160, 600, 28):
        cv2.line(desk, (100, y), (460, y), (210, 210, 210), 1)

    # 2. Textbook (top-right): colorful textbook cover
    cv2.rectangle(desk, (540, 80), (840, 480), (30, 40, 190), -1)  # Red cover
    cv2.rectangle(desk, (540, 80), (840, 200), (180, 60, 30), -1)  # Blue band
    cv2.putText(desk, "COMPUTER ARCHITECTURE", (555, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)
    cv2.putText(desk, "VOLUME II", (610, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # 3. Scientific Calculator (bottom-right): Casio-style handheld calculator
    cx1, cy1, cx2, cy2 = 920, 380, 1080, 660
    cv2.rectangle(desk, (cx1, cy1), (cx2, cy2), (40, 42, 45), -1)  # Dark body
    # LCD Display
    cv2.rectangle(desk, (cx1 + 12, cy1 + 18), (cx2 - 12, cy1 + 80), (150, 175, 150), -1)
    cv2.putText(desk, "fx-991EX", (cx1 + 16, cy1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 40, 20), 1)
    cv2.putText(desk, "cos(0) = 1.000", (cx1 + 16, cy1 + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 20, 10), 1)
    # Buttons
    for r in range(5):
        by = cy1 + 100 + r * 30
        for c in range(4):
            bx = cx1 + 14 + c * 35
            cv2.rectangle(desk, (bx, by), (bx + 26, by + 20), (80, 85, 90), -1)

    # 4. Mobile Phone (bottom-center desk): modern smartphone
    px1, py1, px2, py2 = 560, 520, 670, 680
    cv2.rectangle(desk, (px1, py1), (px2, py2), (15, 15, 18), -1)
    cv2.rectangle(desk, (px1 + 5, py1 + 8), (px2 - 5, py2 - 8), (230, 160, 40), -1)  # Screen

    return desk


def main():
    print("=" * 70)
    print("🔬 RUNNING MULTI-OBJECT SCENE VERIFICATION WITH SCIENTIFIC CALCULATOR")
    print("=" * 70)

    desk_frame = create_exam_desk_scene()
    detector = DetectionAgent({})

    # 1. Standalone Scientific Calculator Verification
    calc_config = CalculatorConfig(enabled=True)
    calc_verifier = CalculatorGeminiVerifier(calc_config)

    # Mock Gemini Vision response for calculator crop
    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "scientific_calculator", "confidence": 0.94, "reason": "Scientific calculator with 2-line mathematical display and function keys."}'
    calc_verifier.model = MagicMock()
    calc_verifier.model.generate_content = MagicMock(return_value=mock_resp)

    # Crop calculator from LIVE frame
    calc_bbox = (920, 380, 1080, 660)
    calc_crop = calc_verifier.crop_candidate_from_frame(desk_frame, calc_bbox)
    assert calc_crop is not None

    calc_res = asyncio.run(calc_verifier.verify_crop(calc_crop, bbox=calc_bbox, track_id=20))
    print(f"🧮 Calculator Result: {calc_res.object_type} | Classification: {calc_res.classification} | Safe: {calc_res.safe} | Conf: {calc_res.confidence}")
    assert calc_res.object_type == "SCIENTIFIC_CALCULATOR"
    assert calc_res.safe is True

    # 2. Build multi-object detections for simultaneous rendering
    detections = [
        # Confirmed Scientific Calculator (SAFE)
        Detection(bbox=calc_bbox, confidence=calc_res.confidence, class_name="scientific_calculator"),
        # Answer Sheet (Cyan)
        Detection(bbox=(80, 80, 480, 620), confidence=0.96, class_name="answer_sheet"),
        # Textbook (Orange)
        Detection(bbox=(540, 80, 840, 480), confidence=0.88, class_name="book"),
        # Mobile Phone (Red - Suspicious)
        Detection(bbox=(560, 520, 670, 680), confidence=0.91, class_name="cell phone"),
    ]

    # Render on frame
    annotated = detector.draw_detections(desk_frame.copy(), detections)

    # Save output
    os.makedirs(ROOT_DIR / "runtime_logs", exist_ok=True)
    out_path = ROOT_DIR / "runtime_logs" / "test_calculator_multiobject_overlay.jpg"
    cv2.imwrite(str(out_path), annotated)
    print(f"✅ Rendered multi-object overlay saved to: {out_path}")

    # Copy to artifacts directory
    artifact_dir = Path(r"C:\Users\vanshika\.gemini\antigravity-ide\brain\4665fc03-faab-426e-9837-c3941077c941")
    if artifact_dir.exists():
        import shutil
        shutil.copy(out_path, artifact_dir / "test_calculator_multiobject_overlay.jpg")
        print(f"✅ Copied image to artifact directory: {artifact_dir / 'test_calculator_multiobject_overlay.jpg'}")

    print("\n🎉 MULTI-OBJECT VISUAL SCENE VERIFICATION COMPLETE!")


if __name__ == "__main__":
    main()
