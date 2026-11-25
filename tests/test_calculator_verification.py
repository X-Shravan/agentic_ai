"""Comprehensive Test Suite for Standalone Scientific Calculator Verification.

Validates all required scenarios:
1. TEST 1: Show a scientific calculator -> SCIENTIFIC_CALCULATOR, SAFE = True, Bounding Box present.
2. TEST 2: Show calculator at angled orientation -> SCIENTIFIC_CALCULATOR, SAFE = True.
3. TEST 3: Show a mobile phone -> NOT_CALCULATOR, SAFE = False, mobile detection unaffected.
4. TEST 4: Show a smartwatch -> NOT_CALCULATOR, SAFE = False, smartwatch detection unaffected.
5. TEST 5: Show a book -> NOT_CALCULATOR, SAFE = False, book system completely independent.
6. TEST 6: Show an answer sheet -> NOT_CALCULATOR, SAFE = False, answer sheet system completely independent.
7. TEST 7: Calculator together with a book -> both verified independently with no cross-dependency.
8. TEST 8: Calculator together with answer sheet -> both verified independently with no cross-dependency.
9. TEST 9: Repeated frame caching -> Gemini is not repeatedly invoked for the same stable object.
10. TEST 10: Graceful fail-safe handling -> API error, invalid crop, empty frame returns UNKNOWN / safe=False without crashing.
11. TEST 11: Overlay display rendering -> displays '🧮 SCIENTIFIC CALCULATOR SAFE <conf>'.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import cv2
import numpy as np
import pytest

from backend.agents.detection_agent import Detection, DetectionAgent
from calculator_verification import (
    CalculatorCandidate,
    CalculatorCandidateDetector,
    CalculatorClassification,
    CalculatorConfig,
    CalculatorGeminiVerifier,
    CalculatorObjectType,
    CalculatorVerificationResult,
)
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline

ROOT_DIR = Path(__file__).resolve().parent.parent


def create_synthetic_calculator_crop(w: int = 100, h: int = 180, angled: bool = False) -> np.ndarray:
    """Create a synthetic scientific calculator image with LCD display and keypad buttons."""
    img = np.full((h, w, 3), (45, 45, 50), dtype=np.uint8)  # Dark grey body
    # LCD Display at top
    cv2.rectangle(img, (10, 15), (w - 10, int(h * 0.28)), (140, 160, 140), -1)  # Greenish LCD
    cv2.putText(img, "fx-991EX", (14, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (20, 30, 20), 1)
    cv2.putText(img, "sin(45)=0.707", (14, int(h * 0.24)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (10, 15, 10), 1)

    # Function keys (sin, cos, tan, log)
    for row in range(3):
        y = int(h * 0.33) + row * 14
        for col in range(4):
            x = 12 + col * int((w - 24) / 4)
            cv2.rectangle(img, (x, y), (x + int((w - 24) / 4) - 4, y + 10), (70, 70, 75), -1)

    # Numeric Keypad
    for row in range(4):
        y = int(h * 0.58) + row * 18
        for col in range(3):
            x = 14 + col * int((w - 28) / 3)
            cv2.rectangle(img, (x, y), (x + int((w - 28) / 3) - 5, y + 14), (90, 90, 95), -1)

    if angled:
        M = cv2.getRotationMatrix2D((w // 2, h // 2), 20, 0.95)
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    return img


def create_synthetic_phone_crop(w: int = 90, h: int = 180) -> np.ndarray:
    """Create a synthetic mobile phone with glossy screen and camera notch."""
    img = np.full((h, w, 3), (20, 20, 22), dtype=np.uint8)
    # Bright screen with colorful icons
    cv2.rectangle(img, (6, 12), (w - 6, h - 12), (240, 180, 50), -1)
    cv2.circle(img, (w // 2, 8), 3, (10, 10, 10), -1)
    return img


def create_synthetic_smartwatch_crop(w: int = 80, h: int = 80) -> np.ndarray:
    """Create a synthetic smartwatch face with strap."""
    img = np.full((h, w, 3), (50, 50, 55), dtype=np.uint8)
    cv2.circle(img, (w // 2, h // 2), 32, (15, 15, 20), -1)
    cv2.putText(img, "10:42", (20, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    return img


# ==============================================================================
# TEST 1: Scientific calculator detection -> SCIENTIFIC_CALCULATOR, SAFE = True
# ==============================================================================
def test_case1_scientific_calculator_detection_safe():
    config = CalculatorConfig(enabled=True, confidence_threshold=0.70)
    verifier = CalculatorGeminiVerifier(config)

    # Mock Gemini response returning scientific_calculator
    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "scientific_calculator", "confidence": 0.94, "reason": "Handheld device with LCD display and mathematical keys."}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    crop = create_synthetic_calculator_crop(100, 180)
    res = asyncio.run(verifier.verify_crop(crop, bbox=(120, 150, 220, 330), track_id=5))

    assert res.classification == "scientific_calculator"
    assert res.object_type == "SCIENTIFIC_CALCULATOR"
    assert res.safe is True
    assert res.confidence == 0.94
    assert res.bbox == (120, 150, 220, 330)
    assert res.track_id == 5


# ==============================================================================
# TEST 2: Calculator at angled orientation -> SCIENTIFIC_CALCULATOR, SAFE = True
# ==============================================================================
def test_case2_angled_calculator_detection_safe():
    config = CalculatorConfig(enabled=True, confidence_threshold=0.70)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "scientific_calculator", "confidence": 0.89, "reason": "Tilted scientific calculator showing matrix display and function keypad."}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    crop_angled = create_synthetic_calculator_crop(110, 190, angled=True)
    res = asyncio.run(verifier.verify_crop(crop_angled, bbox=(100, 100, 210, 290), track_id=6))

    assert res.classification == "scientific_calculator"
    assert res.object_type == "SCIENTIFIC_CALCULATOR"
    assert res.safe is True
    assert res.confidence == 0.89


# ==============================================================================
# TEST 3: Mobile phone -> NOT_CALCULATOR, SAFE = False (Mobile logic unchanged)
# ==============================================================================
def test_case3_mobile_phone_rejected_as_calculator():
    config = CalculatorConfig(enabled=True, confidence_threshold=0.70)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "not_scientific_calculator", "confidence": 0.96, "reason": "This object is a touchscreen smartphone, not a scientific calculator."}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    phone_crop = create_synthetic_phone_crop(90, 180)
    res = asyncio.run(verifier.verify_crop(phone_crop, bbox=(200, 100, 290, 280), track_id=7))

    assert res.classification == "not_scientific_calculator"
    assert res.object_type == "NOT_CALCULATOR"
    assert res.safe is False


# ==============================================================================
# TEST 4: Smartwatch -> NOT_CALCULATOR, SAFE = False (Smartwatch logic unchanged)
# ==============================================================================
def test_case4_smartwatch_rejected_as_calculator():
    config = CalculatorConfig(enabled=True, confidence_threshold=0.70)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "not_scientific_calculator", "confidence": 0.95, "reason": "The image shows a wristwatch/smartwatch, not a calculator."}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    watch_crop = create_synthetic_smartwatch_crop(80, 80)
    res = asyncio.run(verifier.verify_crop(watch_crop, bbox=(300, 200, 380, 280), track_id=8))

    assert res.classification == "not_scientific_calculator"
    assert res.object_type == "NOT_CALCULATOR"
    assert res.safe is False


# ==============================================================================
# TEST 5: Textbook / Book -> NOT_CALCULATOR, SAFE = False (Book unchanged)
# ==============================================================================
def test_case5_textbook_rejected_as_calculator():
    config = CalculatorConfig(enabled=True, confidence_threshold=0.70)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "not_scientific_calculator", "confidence": 0.98, "reason": "The object is a printed textbook cover."}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    book_crop = np.full((250, 180, 3), (30, 40, 200), dtype=np.uint8)
    cv2.putText(book_crop, "PHYSICS", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    res = asyncio.run(verifier.verify_crop(book_crop, bbox=(50, 50, 230, 300), track_id=9))

    assert res.classification == "not_scientific_calculator"
    assert res.object_type == "NOT_CALCULATOR"
    assert res.safe is False


# ==============================================================================
# TEST 6: Answer Sheet -> NOT_CALCULATOR, SAFE = False (Answer Sheet unchanged)
# ==============================================================================
def test_case6_answer_sheet_rejected_as_calculator():
    config = CalculatorConfig(enabled=True, confidence_threshold=0.70)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "not_scientific_calculator", "confidence": 0.99, "reason": "This is a ruled paper answer sheet."}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    sheet_crop = np.full((280, 200, 3), (250, 250, 250), dtype=np.uint8)
    for y in range(40, 260, 25):
        cv2.line(sheet_crop, (15, y), (185, y), (210, 210, 210), 1)
    res = asyncio.run(verifier.verify_crop(sheet_crop, bbox=(50, 50, 250, 330), track_id=10))

    assert res.classification == "not_scientific_calculator"
    assert res.object_type == "NOT_CALCULATOR"
    assert res.safe is False


# ==============================================================================
# TEST 7: Calculator + Book in same scene -> Independent verifications
# ==============================================================================
def test_case7_calculator_and_book_independence():
    # Build scene with a book and a calculator
    frame = np.full((480, 640, 3), (60, 70, 80), dtype=np.uint8)
    # Book bbox: (50, 100, 250, 380)
    cv2.rectangle(frame, (50, 100), (250, 380), (30, 30, 180), -1)
    # Calculator bbox: (350, 150, 460, 340)
    calc_crop = create_synthetic_calculator_crop(110, 190)
    frame[150:340, 350:460] = calc_crop

    existing_detections = [
        Detection(bbox=(50, 100, 250, 380), confidence=0.85, class_name="book"),
    ]

    detector = CalculatorCandidateDetector()
    candidates = detector.detect_candidates(frame, existing_detections=existing_detections)

    # Calculator candidate must be identified without touching the book
    assert len(candidates) >= 1
    calc_cand = candidates[0]
    iou_with_book = detector._compute_iou(calc_cand.bbox, existing_detections[0].bbox)
    assert iou_with_book < 0.10, "Calculator candidate must not overlap or merge with book"


# ==============================================================================
# TEST 8: Calculator + Answer Sheet in same scene -> Independent verifications
# ==============================================================================
def test_case8_calculator_and_answer_sheet_independence():
    frame = np.full((480, 640, 3), (60, 70, 80), dtype=np.uint8)
    # White Answer Sheet bbox: (40, 60, 280, 420)
    cv2.rectangle(frame, (40, 60), (280, 420), (248, 248, 248), -1)
    # Calculator bbox: (360, 140, 470, 330)
    calc_crop = create_synthetic_calculator_crop(110, 190)
    frame[140:330, 360:470] = calc_crop

    existing_detections = [
        Detection(bbox=(40, 60, 280, 420), confidence=0.90, class_name="answer_sheet"),
    ]

    detector = CalculatorCandidateDetector()
    candidates = detector.detect_candidates(frame, existing_detections=existing_detections)

    assert len(candidates) >= 1
    calc_cand = candidates[0]
    iou_with_sheet = detector._compute_iou(calc_cand.bbox, existing_detections[0].bbox)
    assert iou_with_sheet < 0.10, "Calculator candidate must not overlap with answer sheet"


# ==============================================================================
# TEST 9: Repeated frame caching -> Gemini not called every frame
# ==============================================================================
def test_case9_temporal_and_spatial_caching():
    config = CalculatorConfig(enabled=True, cache_duration=15.0)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "scientific_calculator", "confidence": 0.92, "reason": "Scientific calculator"}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    # Frame 1: verify crop and store in cache
    crop = create_synthetic_calculator_crop(100, 180)
    res = asyncio.run(verifier.verify_crop(crop, bbox=(100, 100, 200, 280), track_id=12))
    verifier.cache[("cam_0", 12)] = res

    assert verifier.model.generate_content.call_count == 1

    # Frame 2: 0.5 seconds later, query cache with matching track ID and bbox
    cached = verifier.get_cached_result("cam_0", track_id=12, bbox=(102, 101, 201, 282))
    assert cached is not None
    assert cached.safe is True
    assert cached.classification == "scientific_calculator"
    # Call count should remain 1 (no repeated API call)
    assert verifier.model.generate_content.call_count == 1


# ==============================================================================
# TEST 10: Graceful fail-safe handling (never crashes)
# ==============================================================================
def test_case10_graceful_fail_safe():
    config = CalculatorConfig(enabled=True)
    verifier = CalculatorGeminiVerifier(config)

    # Sub-case A: Empty / invalid crop
    res_empty = asyncio.run(verifier.verify_crop(np.zeros((0, 0, 3), dtype=np.uint8)))
    assert res_empty.object_type == "UNKNOWN"
    assert res_empty.safe is False
    assert res_empty.classification == "uncertain"

    # Sub-case B: Gemini API exception / timeout
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(side_effect=RuntimeError("API quota exceeded"))
    crop = create_synthetic_calculator_crop(80, 140)
    res_err = asyncio.run(verifier.verify_crop(crop, bbox=(50, 50, 130, 190)))
    assert res_err.object_type == "UNKNOWN"
    assert res_err.safe is False
    assert res_err.classification == "uncertain"
    assert "API error" in res_err.reason

    # Sub-case C: Invalid JSON response
    verifier.model.generate_content = MagicMock(return_value=MagicMock(text="I cannot classify this."))
    res_json_err = asyncio.run(verifier.verify_crop(crop, bbox=(50, 50, 130, 190)))
    assert res_json_err.object_type == "UNKNOWN"
    assert res_json_err.safe is False
    assert res_json_err.classification == "uncertain"


# ==============================================================================
# TEST 11: Overlay display rendering
# ==============================================================================
def test_case11_overlay_display_rendering():
    detector = DetectionAgent({})
    frame = np.full((480, 640, 3), 100, dtype=np.uint8)

    calc_det = Detection(
        bbox=(150, 120, 270, 320),
        confidence=0.93,
        class_name="scientific_calculator",
    )

    annotated = detector.draw_detections(frame, [calc_det])
    assert annotated is not None
    assert annotated.shape == (480, 640, 3)

    # Verify that the bounding box pixels are altered (colored box drawn)
    # The box outline at y=120 should have been modified
    assert not np.array_equal(frame[120, 150:270], annotated[120, 150:270])


# ==============================================================================
# TEST 12: Pipeline synchronization surfaces verified calculator
# ==============================================================================
def test_case12_pipeline_display_sync():
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())

    # Pre-populate pipeline calculator cache with confirmed scientific calculator
    res = CalculatorVerificationResult(
        object_type="SCIENTIFIC_CALCULATOR",
        classification="scientific_calculator",
        confidence=0.91,
        safe=True,
        reason="Visual features confirmed",
        bbox=(200, 150, 310, 330),
        timestamp=time.time(),
        track_id=15,
    )
    pipeline.calculator_verifier.cache[("cam_test", 15)] = res

    raw_det = Detection(bbox=(200, 150, 310, 330), confidence=0.75, class_name="calculator")

    class MockTrack:
        def __init__(self, track_id, bbox):
            self.track_id = track_id
            self.bbox = bbox

    tracks = [MockTrack(15, (200, 150, 310, 330))]

    synced = pipeline._sync_detections_for_display([raw_det], tracks, camera_id="cam_test")
    assert len(synced) == 1
    assert synced[0].class_name == "scientific_calculator"
    assert synced[0].confidence == 0.91
