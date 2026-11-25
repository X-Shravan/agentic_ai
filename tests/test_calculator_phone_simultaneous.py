"""Comprehensive Test Suite for Simultaneous Independent Scientific Calculator and Mobile Phone Detection.

Validates all prompt-mandated test scenarios:
TEST 1: Show only scientific calculator -> SCIENTIFIC CALCULATOR SAFE, 0 phone alerts.
TEST 2: Show only mobile phone -> CELL PHONE CRITICAL, phone alert triggered, risk elevated.
TEST 3: Show calculator + mobile phone simultaneously -> BOTH visible, calculator SAFE, phone CRITICAL.
TEST 4: Move calculator closer to phone -> Still maintain two object identities without merging.
TEST 5: Move calculator away from phone -> Both objects remain independently classified.
TEST 6: Show book -> Existing Book behavior unchanged, not classified as calculator.
TEST 7: Show answer sheet -> Existing Answer Sheet behavior unchanged, not classified as calculator.
TEST 8: Gemini Visual Object Detection Option -> normalized box_2d converted to exact frame pixel coordinates.
TEST 9: Gemini Failure Handling -> timeout/error returns uncertain, phone alert continues unsuppressed.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from backend.agents.detection_agent import Detection, DetectionAgent
from backend.agents.tracking_agent import Track
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


def make_test_frame(w: int = 640, h: int = 480) -> np.ndarray:
    """Create a neutral desk test frame."""
    frame = np.full((h, w, 3), (80, 85, 90), dtype=np.uint8)
    for y in range(h):
        shade = int(75 + 20 * (y / h))
        frame[y, :] = (shade, shade + 5, shade + 10)
    return frame


def draw_calc_on_frame(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
    """Draw a synthetic scientific calculator pattern onto frame."""
    w = x2 - x1
    h = y2 - y1
    cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 42, 45), -1)
    # LCD Display
    lcd_h = int(h * 0.25)
    cv2.rectangle(frame, (x1 + 6, y1 + 8), (x2 - 6, y1 + 8 + lcd_h), (130, 160, 130), -1)
    cv2.putText(frame, "fx-991", (x1 + 8, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (20, 30, 20), 1)
    # Function buttons
    for row in range(3):
        by = y1 + int(h * 0.35) + row * 14
        for col in range(4):
            bx = x1 + 8 + col * int((w - 16) / 4)
            cv2.rectangle(frame, (bx, by), (bx + int((w - 16) / 4) - 4, by + 10), (65, 65, 70), -1)
    # Numeric keypad
    for row in range(4):
        by = y1 + int(h * 0.60) + row * 16
        for col in range(3):
            bx = x1 + 10 + col * int((w - 20) / 3)
            cv2.rectangle(frame, (bx, by), (bx + int((w - 20) / 3) - 5, by + 12), (90, 90, 95), -1)


def draw_phone_on_frame(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
    """Draw a synthetic mobile phone pattern onto frame."""
    cv2.rectangle(frame, (x1, y1), (x2, y2), (20, 20, 20), -1)
    cv2.rectangle(frame, (x1 + 4, y1 + 8), (x2 - 4, y2 - 8), (220, 180, 40), -1)  # bright screen
    cv2.circle(frame, ((x1 + x2) // 2, y1 + 5), 2, (10, 10, 10), -1)


# ==============================================================================
# TEST 1: Show only scientific calculator -> SCIENTIFIC CALCULATOR SAFE, 0 alerts
# ==============================================================================
def test_case1_only_scientific_calculator():
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    frame = make_test_frame()
    draw_calc_on_frame(frame, 300, 200, 410, 390)

    # Pre-populate confirmed calculator cache
    calc_res = CalculatorVerificationResult(
        object_type="SCIENTIFIC_CALCULATOR",
        classification="scientific_calculator",
        confidence=0.96,
        safe=True,
        reason="LCD matrix display and function keys",
        bbox=(300, 200, 410, 390),
        timestamp=time.time(),
        track_id=12,
    )
    pipeline.calculator_verifier.cache[("cam_0", 12)] = calc_res

    calc_track = Track(track_id=12, bbox=(300, 200, 410, 390), confidence=0.96)
    setattr(calc_track, "class_name", "scientific_calculator")

    res = asyncio.run(pipeline.process_frame(frame, "cam_0", [calc_track], timestamp=time.time()))

    assert len(res["alerts"]) == 0, "Scientific calculator alone must NOT trigger any alert"
    assert len(res["calculators"]) >= 1, "Calculator must be recorded in frame_results['calculators']"
    calc_item = res["calculators"][0]
    assert calc_item["safe"] is True
    assert calc_item["classification"] == "scientific_calculator"


# ==============================================================================
# TEST 2: Show only mobile phone -> CELL PHONE CRITICAL, 1 alert
# ==============================================================================
def test_case2_only_mobile_phone():
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    frame = make_test_frame()
    draw_phone_on_frame(frame, 150, 150, 240, 330)

    phone_track = Track(track_id=7, bbox=(150, 150, 240, 330), confidence=0.93)
    setattr(phone_track, "class_name", "cell phone")
    setattr(phone_track, "phone_confidence", 0.93)
    phone_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.93, "bbox": (150, 150, 240, 330)}]

    # First frame starts 1s timer
    t0 = time.time()
    res1 = asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track], timestamp=t0))

    # Second frame at t0 + 1.2s triggers stable CRITICAL alert
    res2 = asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track], timestamp=t0 + 1.2))

    assert len(res2["alerts"]) >= 1, "Phone detection must trigger alert after 1s stability"
    alert = res2["alerts"][0]
    assert alert["severity"] == "critical", "Phone alert severity must be critical"
    assert alert["risk_score"] >= 90.0, "Phone risk must be CRITICAL (score >= 90.0)"
    assert len(res2["calculators"]) == 0, "No calculator should be reported"


# ==============================================================================
# TEST 3: Show calculator + mobile phone simultaneously
# Expected: BOTH visible, calculator SAFE, phone CRITICAL, 1 alert
# ==============================================================================
def test_case3_simultaneous_calculator_and_phone():
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    detector = DetectionAgent({})
    frame = make_test_frame()

    # Place Phone at (100, 150, 190, 330) and Calculator at (350, 150, 460, 340)
    draw_phone_on_frame(frame, 100, 150, 190, 330)
    draw_calc_on_frame(frame, 350, 150, 460, 340)

    # 1. Setup Phone track
    phone_track = Track(track_id=7, bbox=(100, 150, 190, 330), confidence=0.94)
    setattr(phone_track, "class_name", "cell phone")
    setattr(phone_track, "phone_confidence", 0.94)
    phone_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.94, "bbox": (100, 150, 190, 330)}]

    # 2. Setup Calculator verification cache
    calc_res = CalculatorVerificationResult(
        object_type="SCIENTIFIC_CALCULATOR",
        classification="scientific_calculator",
        confidence=0.96,
        safe=True,
        reason="Scientific calculator LCD and keyboard",
        bbox=(350, 150, 460, 340),
        timestamp=time.time(),
        track_id=12,
    )
    pipeline.calculator_verifier.cache[("cam_0", 12)] = calc_res

    calc_track = Track(track_id=12, bbox=(350, 150, 460, 340), confidence=0.96)
    setattr(calc_track, "class_name", "scientific_calculator")

    # Run frame 1 at t0
    t0 = time.time()
    asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track, calc_track], timestamp=t0))

    # Run frame 2 at t0 + 1.2s
    res2 = asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track, calc_track], timestamp=t0 + 1.2))

    # 1. Verify Phone is CRITICAL and generated an alert
    assert len(res2["alerts"]) >= 1, "Phone alert must fire even though calculator is present!"
    phone_alert = res2["alerts"][0]
    assert phone_alert["severity"] == "critical"
    assert phone_alert["risk_score"] >= 90.0

    # 2. Verify Calculator is SAFE and recorded in frame_results["calculators"]
    assert len(res2["calculators"]) >= 1, "Calculator must be recorded in frame_results['calculators']"
    calc_rec = res2["calculators"][0]
    assert calc_rec["safe"] is True
    assert calc_rec["classification"] == "scientific_calculator"

    # 3. Verify Display Synchronization has BOTH objects
    raw_dets = [
        Detection(bbox=(100, 150, 190, 330), confidence=0.94, class_name="cell phone"),
        Detection(bbox=(350, 150, 460, 340), confidence=0.96, class_name="scientific_calculator"),
    ]
    synced = pipeline._sync_detections_for_display(raw_dets, [phone_track, calc_track], camera_id="cam_0")
    classes_synced = {d.class_name for d in synced}
    assert "cell phone" in classes_synced, "Cell phone must be in synced detections"
    assert "scientific_calculator" in classes_synced, "Scientific calculator must be in synced detections"

    # 4. Verify Visual Overlay renders BOTH objects with distinct colors & labels
    annotated = detector.draw_detections(frame, synced)
    assert annotated is not None
    # Phone region should have red box pixels (BGR: 0, 0, 255)
    # Calculator region should have spring green box pixels (BGR: 0, 255, 128)
    assert np.any(annotated[150, 100:190] == [0, 0, 255]), "Phone box must be colored Red"
    assert np.any(annotated[150, 350:460] == [0, 255, 128]), "Calculator box must be colored Spring Green"


# ==============================================================================
# TEST 4: Move calculator closer to phone -> Still maintain two object identities
# ==============================================================================
def test_case4_calculator_close_to_phone():
    detector = CalculatorCandidateDetector()
    frame = make_test_frame()

    phone_bbox = (150, 150, 240, 330)
    draw_phone_on_frame(frame, *phone_bbox)

    calc_bbox = (250, 150, 360, 340)
    draw_calc_on_frame(frame, *calc_bbox)

    existing_detections = [
        Detection(bbox=phone_bbox, confidence=0.93, class_name="cell phone"),
    ]

    candidates = detector.detect_candidates(frame, existing_detections=existing_detections)

    assert len(candidates) >= 1
    found_calc_cand = False
    for c in candidates:
        iou_with_phone = detector._compute_iou(c.bbox, phone_bbox)
        if iou_with_phone < 0.20 and detector._compute_iou(c.bbox, calc_bbox) > 0.40:
            found_calc_cand = True
            break
    assert found_calc_cand, "Calculator candidate must be generated distinctly right next to phone"


# ==============================================================================
# TEST 5: Move calculator away from phone -> Both independently maintained
# ==============================================================================
def test_case5_calculator_far_from_phone():
    detector = CalculatorCandidateDetector()
    frame = make_test_frame()

    phone_bbox = (50, 120, 140, 300)
    draw_phone_on_frame(frame, *phone_bbox)

    calc_bbox = (480, 140, 590, 330)
    draw_calc_on_frame(frame, *calc_bbox)

    existing_detections = [
        Detection(bbox=phone_bbox, confidence=0.91, class_name="cell phone"),
    ]

    candidates = detector.detect_candidates(frame, existing_detections=existing_detections)
    assert len(candidates) >= 1
    c_cand = candidates[0]
    iou_phone = detector._compute_iou(c_cand.bbox, phone_bbox)
    iou_calc = detector._compute_iou(c_cand.bbox, calc_bbox)
    assert iou_phone == 0.0, "Candidate must have 0 overlap with distant phone"
    assert iou_calc > 0.40, "Candidate must match calculator location"


# ==============================================================================
# TEST 6: Show book -> Calculator module does not classify it as calculator
# ==============================================================================
def test_case6_book_not_classified_as_calculator():
    config = CalculatorConfig(enabled=True)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "not_scientific_calculator", "confidence": 0.98, "reason": "Printed paper book"}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    book_crop = np.full((260, 200, 3), (30, 40, 180), dtype=np.uint8)
    cv2.putText(book_crop, "CALCULUS", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    res = asyncio.run(verifier.verify_crop(book_crop, bbox=(50, 50, 250, 310)))
    assert res.classification == "not_scientific_calculator"
    assert res.object_type == "NOT_CALCULATOR"
    assert res.safe is False


# ==============================================================================
# TEST 7: Show answer sheet -> Calculator module does not classify as calculator
# ==============================================================================
def test_case7_answer_sheet_not_classified_as_calculator():
    config = CalculatorConfig(enabled=True)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '{"classification": "not_scientific_calculator", "confidence": 0.99, "reason": "Ruled answer paper"}'
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    sheet_crop = np.full((300, 220, 3), (250, 250, 250), dtype=np.uint8)
    for y in range(40, 280, 25):
        cv2.line(sheet_crop, (15, y), (205, y), (210, 210, 210), 1)

    res = asyncio.run(verifier.verify_crop(sheet_crop, bbox=(60, 60, 280, 360)))
    assert res.classification == "not_scientific_calculator"
    assert res.object_type == "NOT_CALCULATOR"
    assert res.safe is False


# ==============================================================================
# TEST 8: Gemini Visual Object Detection Option (detect_calculator_box)
# ==============================================================================
def test_case8_gemini_visual_object_detection():
    config = CalculatorConfig(enabled=True)
    verifier = CalculatorGeminiVerifier(config)

    mock_resp = MagicMock()
    mock_resp.text = '''
    {
      "found": true,
      "label": "scientific_calculator",
      "confidence": 0.95,
      "box_2d": [300, 400, 750, 650],
      "reason": "Scientific calculator with keypad and matrix screen detected on desk."
    }
    '''
    verifier.model = MagicMock()
    verifier.model.generate_content = MagicMock(return_value=mock_resp)

    frame = make_test_frame(640, 480)
    res = asyncio.run(verifier.detect_calculator_box(frame, camera_id="cam_0", track_id=22))

    assert res is not None
    assert res.object_type == "SCIENTIFIC_CALCULATOR"
    assert res.classification == "scientific_calculator"
    assert res.safe is True
    assert res.confidence == 0.95
    assert res.bbox == (256, 144, 416, 360)


# ==============================================================================
# TEST 9: Gemini Failure Handling -> Uncertain, does not suppress phone alert
# ==============================================================================
def test_case9_gemini_failure_handling():
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    frame = make_test_frame()

    pipeline.calculator_verifier.model = MagicMock()
    pipeline.calculator_verifier.model.generate_content = MagicMock(side_effect=RuntimeError("API Network Timeout"))

    phone_track = Track(track_id=8, bbox=(100, 100, 200, 280), confidence=0.95)
    setattr(phone_track, "class_name", "cell phone")
    setattr(phone_track, "phone_confidence", 0.95)
    phone_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.95, "bbox": (100, 100, 200, 280)}]

    t0 = time.time()
    asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track], timestamp=t0))
    res = asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track], timestamp=t0 + 1.2))

    assert len(res["alerts"]) >= 1, "Phone alert must NOT be suppressed when calculator API fails"
    assert res["alerts"][0]["severity"] == "critical"


# ==============================================================================
# TEST 10: YOLO Misclassifies Calculator as Phone -> Gemini corrects to SAFE
# ==============================================================================
def test_case10_yolo_misclassifies_calculator_as_phone():
    """When YOLO outputs 'cell phone' for a calculator (Track 8), Gemini verifies

    it as SCIENTIFIC_CALCULATOR. Arbitration must clear phone_confidence to 0.0,
    set safe=True, prevent any cell phone alert from firing, and keep risk score at 0.0.
    """
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    frame = make_test_frame()
    calc_bbox = (350, 150, 460, 340)
    draw_calc_on_frame(frame, *calc_bbox)

    # Pre-populate Gemini verification cache for Track 8
    calc_res = CalculatorVerificationResult(
        object_type="SCIENTIFIC_CALCULATOR",
        classification="scientific_calculator",
        confidence=0.96,
        safe=True,
        reason="Scientific calculator LCD matrix display and multi-row key grid",
        bbox=calc_bbox,
        timestamp=time.time(),
        track_id=8,
    )
    pipeline.calculator_verifier.cache[("cam_0", 8)] = calc_res

    # YOLO misclassified this object as a cell phone with high confidence
    calc_track = Track(track_id=8, bbox=calc_bbox, confidence=0.91)
    setattr(calc_track, "class_name", "cell phone")
    setattr(calc_track, "phone_confidence", 0.91)
    calc_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.91, "bbox": calc_bbox}]

    t0 = time.time()
    res1 = asyncio.run(pipeline.process_frame(frame, "cam_0", [calc_track], timestamp=t0))
    res2 = asyncio.run(pipeline.process_frame(frame, "cam_0", [calc_track], timestamp=t0 + 1.2))

    # Verification checks
    assert getattr(calc_track, "safe", False) is True, "Track 8 must be marked safe=True"
    assert getattr(calc_track, "phone_confidence", 0.0) == 0.0, "phone_confidence must be cleared to 0.0"
    assert calc_track.class_name == "scientific_calculator", "Track class_name must be updated to scientific_calculator"
    assert len(res2["alerts"]) == 0, "No phone alert should be triggered for verified calculator"
    assert len(res2["calculators"]) >= 1, "Calculator must be recorded in calculators list"
    assert res2["students"]["cam_0_8"]["risk_score"] == 0.0, "Risk score must be 0.0 LOW"


# ==============================================================================
# TEST 11: Real Phone (Track 7) + Misclassified Calculator (Track 8) in Same Frame
# ==============================================================================
def test_case11_simultaneous_phone_and_misclassified_calculator():
    """In the same camera frame:

    - Track 7: Real cell phone (YOLO 'cell phone' 0.94) -> CRITICAL alert, risk elevated
    - Track 8: Physical calculator (YOLO misclassified 'cell phone' 0.91) -> Gemini corrects to SAFE
    Expected: Track 7 fires exactly 1 CRITICAL phone alert. Track 8 is SAFE.
    No duplicate tracks, no suppression of the real phone alert, and both display properly.
    """
    pipeline = IntegratedSurveillancePipeline({"enable_detection": False}, webrtc_server=MagicMock())
    detector = DetectionAgent({})
    frame = make_test_frame()

    phone_bbox = (100, 150, 190, 330)
    calc_bbox = (350, 150, 460, 340)
    draw_phone_on_frame(frame, *phone_bbox)
    draw_calc_on_frame(frame, *calc_bbox)

    # 1. Real phone track
    phone_track = Track(track_id=7, bbox=phone_bbox, confidence=0.94)
    setattr(phone_track, "class_name", "cell phone")
    setattr(phone_track, "phone_confidence", 0.94)
    phone_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.94, "bbox": phone_bbox}]

    # 2. Calculator track initially misclassified by YOLO as cell phone
    calc_track = Track(track_id=8, bbox=calc_bbox, confidence=0.91)
    setattr(calc_track, "class_name", "cell phone")
    setattr(calc_track, "phone_confidence", 0.91)
    calc_track.objects_detected = [{"class_name": "cell phone", "confidence": 0.91, "bbox": calc_bbox}]

    # Gemini verifies Track 8 as SCIENTIFIC_CALCULATOR
    calc_res = CalculatorVerificationResult(
        object_type="SCIENTIFIC_CALCULATOR",
        classification="scientific_calculator",
        confidence=0.96,
        safe=True,
        reason="Scientific calculator LCD matrix display and multi-row key grid",
        bbox=calc_bbox,
        timestamp=time.time(),
        track_id=8,
    )
    pipeline.calculator_verifier.cache[("cam_0", 8)] = calc_res

    # Frame 1 at t0
    t0 = time.time()
    res1 = asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track, calc_track], timestamp=t0))

    # Frame 2 at t0 + 1.2s
    res2 = asyncio.run(pipeline.process_frame(frame, "cam_0", [phone_track, calc_track], timestamp=t0 + 1.2))

    # Assertions
    # 1. Exactly 1 alert fired, and it is for Track 7 (cell phone)
    assert len(res2["alerts"]) == 1, f"Expected exactly 1 alert, got {len(res2['alerts'])}"
    alert = res2["alerts"][0]
    assert alert["severity"] == "critical"
    assert alert["risk_score"] >= 90.0
    assert alert["student_id"] == "cam_0_7"
    assert "phone" in alert["reason"].lower() or "mobile" in alert["reason"].lower()

    # 2. Track 8 was corrected and cleared
    assert getattr(calc_track, "safe", False) is True
    assert getattr(calc_track, "phone_confidence", 0.0) == 0.0
    assert calc_track.class_name == "scientific_calculator"
    assert res2["students"]["cam_0_8"]["risk_score"] == 0.0

    # 3. Track 7 remains cell phone and elevated risk
    assert phone_track.class_name == "cell phone"
    assert getattr(phone_track, "phone_confidence", 0.0) == 0.94
    assert res2["students"]["cam_0_7"]["risk_score"] >= 90.0

    # 4. Display sync keeps both distinct
    raw_dets = [
        Detection(bbox=phone_bbox, confidence=0.94, class_name="cell phone"),
        Detection(bbox=calc_bbox, confidence=0.91, class_name="cell phone"),
    ]
    synced = pipeline._sync_detections_for_display(raw_dets, [phone_track, calc_track], camera_id="cam_0")
    synced_classes = {d.class_name: d for d in synced}
    assert "cell phone" in synced_classes
    assert "scientific_calculator" in synced_classes

    # 5. Visual overlay check
    annotated = detector.draw_detections(frame, synced)
    assert annotated is not None
    # Phone box: Red (BGR: 0, 0, 255)
    assert np.any(annotated[150, 100:190] == [0, 0, 255])
    # Calculator box: Spring Green (BGR: 0, 255, 128)
    assert np.any(annotated[150, 350:460] == [0, 255, 128])

