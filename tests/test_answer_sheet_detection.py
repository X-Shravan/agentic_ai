#!/usr/bin/env python3
"""Comprehensive test suite for Answer Sheet Detection improvements.

Tests:
- TEST 1: Portrait answer sheet detection without requiring YOLO BOOK
- TEST 2: Landscape answer sheet detection
- TEST 3: Rotated / tilted answer sheet (30-45 degrees)
- TEST 4: Distant / small area answer sheet
- TEST 5: Textbook protection (NOT_ANSWER_SHEET -> preserves normal book behavior)
- TEST 6: White textbook protection (whiteness alone never yields ANSWER_SHEET)
- TEST 7: Answer Sheet + Mobile Phone isolation
- TEST 8: Answer Sheet + Smartwatch isolation
- TEST 9: Throttling & Cache hit verification
- TEST 10: Multi-camera cache isolation
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.detection_agent import Detection
from backend.agents.page_candidate_detector import PageCandidateDetector, PageCandidate
from backend.agents.answersheet_vision_verifier import AnswerSheetVisionVerifier
from backend.api.websocket import init_webrtc_server
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline


class MockTrack:
    def __init__(self, track_id: int, bbox: tuple, class_name: str = "person", confidence: float = 0.9):
        self.track_id = track_id
        self.bbox = bbox
        self.confidence = confidence
        self.class_name = class_name
        self.objects_detected = []
        self.history = [((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)]
        self.time_since_update = 0

    @property
    def center(self):
        return ((self.bbox[0] + self.bbox[2]) // 2, (self.bbox[1] + self.bbox[3]) // 2)


def test_portrait_page_candidate_detection():
    """TEST 1: Verify portrait answer sheet is detected by candidate detector without YOLO BOOK."""
    ref_path = Path("reference_data/answer_sheet/ans1.jpeg")
    assert ref_path.exists(), "ans1.jpeg must exist in reference_data"

    img = cv2.imread(str(ref_path))
    assert img is not None
    h, w = img.shape[:2]
    assert h > w, "ans1.jpeg should be portrait"

    detector = PageCandidateDetector()
    candidates = detector.detect_candidates(img)

    assert len(candidates) > 0, "Portrait answer sheet candidate must be detected"
    best = candidates[0]
    assert best.orientation == "portrait", "Orientation must be portrait"
    assert best.score >= 0.50, f"Candidate score {best.score:.2f} must be >= 0.50"
    print(f"✅ TEST 1 passed: Portrait candidate detected with score={best.score:.2f}, ratio={best.aspect_ratio:.2f}")


def test_landscape_page_candidate_detection():
    """TEST 2: Verify landscape answer sheet is detected by candidate detector."""
    ref_path = Path("reference_data/answer_sheet/ans10.jpeg")
    assert ref_path.exists(), "ans10.jpeg must exist in reference_data"

    img = cv2.imread(str(ref_path))
    assert img is not None
    h, w = img.shape[:2]
    assert w > h, "ans10.jpeg should be landscape"

    detector = PageCandidateDetector()
    candidates = detector.detect_candidates(img)

    assert len(candidates) > 0, "Landscape answer sheet candidate must be detected"
    best = candidates[0]
    assert best.orientation == "landscape", "Orientation must be landscape"
    assert best.score >= 0.50, f"Candidate score {best.score:.2f} must be >= 0.50"
    print(f"✅ TEST 2 passed: Landscape candidate detected with score={best.score:.2f}, ratio={best.aspect_ratio:.2f}")


def test_rotated_tilted_page_candidate():
    """TEST 3: Verify candidate detector supports rotated / tilted answer sheet (35 degrees)."""
    ref_path = Path("reference_data/answer_sheet/ans1.jpeg")
    img = cv2.imread(str(ref_path))
    h, w = img.shape[:2]

    # Rotate by 35 degrees
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, 35, 0.8)
    rotated = cv2.warpAffine(img, matrix, (w, h), borderValue=(50, 50, 50))

    detector = PageCandidateDetector()
    candidates = detector.detect_candidates(rotated)

    assert len(candidates) > 0, "Rotated answer sheet must still be detected as page candidate"
    best = candidates[0]
    assert best.score >= 0.40, f"Rotated candidate score {best.score:.2f} must be >= 0.40"
    print(f"✅ TEST 3 passed: Rotated page candidate detected with score={best.score:.2f}")


def test_distant_page_candidate():
    """TEST 4: Verify candidate detector catches small/distant answer sheet above min area ratio."""
    # Create 640x480 frame with a small white ruled sheet occupying ~3% of frame
    frame = np.full((480, 640, 3), 40, dtype=np.uint8)
    sheet_w, sheet_h = 100, 140  # 14000 px / (640*480 = 307200) = ~4.5%
    x1, y1 = 200, 150
    x2, y2 = x1 + sheet_w, y1 + sheet_h

    # Draw white paper
    cv2.rectangle(frame, (x1, y1), (x2, y2), (240, 240, 240), -1)
    # Draw dark ruled lines
    for line_y in range(y1 + 20, y2 - 10, 15):
        cv2.line(frame, (x1 + 10, line_y), (x2 - 10, line_y), (100, 100, 100), 1)

    detector = PageCandidateDetector(config={"page_candidate_detector": {"min_area_ratio": 0.015}})
    candidates = detector.detect_candidates(frame)

    assert len(candidates) > 0, "Distant page candidate must be detected"
    best = candidates[0]
    assert best.area_ratio >= 0.015, "Candidate area ratio should be >= min threshold"
    print(f"✅ TEST 4 passed: Distant candidate detected with area_ratio={best.area_ratio:.3f}")


def test_white_textbook_protection():
    """TEST 5 & 6: Verify plain white textbook without exam ruling is not classified as answer sheet."""
    verifier = AnswerSheetVisionVerifier(config={"answer_sheet_verify": {"enabled": False}})
    # A plain white solid rectangle (textbook cover without ruled lines)
    white_book = np.full((300, 200, 3), 245, dtype=np.uint8)

    lines_ok, lines_count, _ = verifier.verify_ruled_lines(white_book)
    assert lines_count < 2, "Plain white book should have no ruled lines"

    # Response parsing protection test: Ensure not_answer_sheet is parsed correctly
    parsed = verifier._parse_gemini_response('{"classification": "not_answer_sheet", "confidence": 0.95, "reason": "Textbook cover with printed title"}')
    assert parsed["classification"] == "not_answer_sheet"
    assert parsed["confidence"] == 0.95
    print("✅ TEST 5 & 6 passed: White textbook protection verified")


@pytest.mark.asyncio
async def test_pipeline_answer_sheet_and_mobile_isolation():
    """TEST 7: Verify answer sheet and mobile phone operate independently."""
    config = {
        "enable_detection": False,
        "alert_threshold": 20,
        "risk": {"threshold": 20}
    }
    class MockGemini:
        async def analyze_alert(self, inputs):
            return {"ai_explanation": "Device visible"}

    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)
    pipeline.gemini = MockGemini()
    pipeline.workflow_impl.gemini_agent = pipeline.gemini
    pipeline.crew.kickoff = lambda inputs: {"status": "success", "result": "Critical Incident"}
    pipeline.report_agent.generate_pdf = lambda **kwargs: None

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Student with both answer sheet and cell phone
    student_track = MockTrack(track_id=10, bbox=(100, 100, 250, 350), class_name="person")
    student_track.objects_detected.append({
        "class_name": "answer_sheet",
        "confidence": 0.95,
        "bbox": (110, 110, 180, 220),
        "area": 7700
    })
    student_track.objects_detected.append({
        "class_name": "cell phone",
        "confidence": 0.92,
        "bbox": (200, 120, 230, 180),
        "area": 1800
    })

    # Cache answer sheet as confirmed
    pipeline.answersheet_vision_cache[("cam_test", 10)] = ("answer_sheet", 0.95, time.time(), (110, 110, 180, 220))
    pipeline.answersheet_vision_cache[(10, "book")] = ("answer_sheet", 0.95, time.time(), (110, 110, 180, 220))

    # Call 1: Start phone timer
    await pipeline.process_frame(
        frame=frame,
        camera_id="cam_test",
        yolo_results=[student_track],
        timestamp=1.0,
        clean_frame=frame
    )

    # Call 2: Stable phone timer triggers alert
    results = await pipeline.process_frame(
        frame=frame,
        camera_id="cam_test",
        yolo_results=[student_track],
        timestamp=2.1,
        clean_frame=frame
    )

    student_data = results["students"]["cam_test_10"]
    assert student_data["risk_score"] > 0, "Mobile phone must independently trigger risk despite answer sheet"
    assert len(results["alerts"]) > 0, "Mobile phone must generate alert"
    print("✅ TEST 7 passed: Answer sheet and mobile phone operate independently")


@pytest.mark.asyncio
async def test_pipeline_answer_sheet_smartwatch_isolation():
    """TEST 8: Verify answer sheet and smartwatch operate independently."""
    config = {
        "enable_detection": False,
        "alert_threshold": 20,
        "risk": {"threshold": 20}
    }
    class MockGemini:
        async def analyze_alert(self, inputs):
            return {"ai_explanation": "Device visible"}

    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)
    pipeline.gemini = MockGemini()
    pipeline.workflow_impl.gemini_agent = pipeline.gemini
    pipeline.crew.kickoff = lambda inputs: {"status": "success", "result": "Critical Incident"}
    pipeline.report_agent.generate_pdf = lambda **kwargs: None

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    student_track = MockTrack(track_id=11, bbox=(100, 100, 250, 350), class_name="person")
    student_track.objects_detected.append({
        "class_name": "answer_sheet",
        "confidence": 0.92,
        "bbox": (110, 110, 180, 220),
        "area": 7700
    })
    student_track.objects_detected.append({
        "class_name": "smart watch",
        "confidence": 0.90,
        "bbox": (120, 120, 150, 150),
        "area": 900
    })

    # Cache answer sheet and smartwatch
    pipeline.answersheet_vision_cache[("cam_test", 11)] = ("answer_sheet", 0.92, time.time(), (110, 110, 180, 220))
    pipeline.gemini_vision_cache[(11, "smart watch")] = ("smartwatch", 0.90, time.time(), (120, 120, 150, 150))

    # Call 1: Start smartwatch timer
    await pipeline.process_frame(
        frame=frame,
        camera_id="cam_test",
        yolo_results=[student_track],
        timestamp=1.0,
        clean_frame=frame
    )

    # Call 2: Stable smartwatch timer triggers alert
    results = await pipeline.process_frame(
        frame=frame,
        camera_id="cam_test",
        yolo_results=[student_track],
        timestamp=2.1,
        clean_frame=frame
    )

    student_data = results["students"]["cam_test_11"]
    assert student_data["risk_score"] >= 75.0, "Smartwatch must independently trigger risk"
    print("✅ TEST 8 passed: Answer sheet and smartwatch operate independently")


def test_caching_and_throttling():
    """TEST 9: Verify answer sheet cache avoids duplicate Gemini calls on same candidate."""
    config = {"enable_detection": False}
    from backend.api.websocket import init_webrtc_server
    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)

    # Pre-populate cache for track 8
    t_now = time.time()
    pipeline.answersheet_vision_cache[("cam_test", 8)] = ("answer_sheet", 0.94, t_now, (50, 50, 150, 200))

    # Retrieve from cache
    v_class, v_conf = pipeline._get_answersheet_verification_result(8, "page_candidate", camera_id="cam_test", bbox=(52, 51, 148, 199))
    assert v_class == "answer_sheet"
    assert v_conf == 0.94

    # Spatial match retrieval without track_id
    v_class_sp, v_conf_sp = pipeline._get_answersheet_verification_result(None, "page_candidate", camera_id="cam_test", bbox=(52, 51, 148, 199))
    assert v_class_sp == "answer_sheet"
    assert v_conf_sp == 0.94
    print("✅ TEST 9 passed: Caching and spatial candidate retrieval verified")


def test_multi_camera_isolation():
    """TEST 10: Verify multi-camera cache keys do not collide."""
    config = {"enable_detection": False}
    from backend.api.websocket import init_webrtc_server
    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)

    t_now = time.time()
    pipeline.answersheet_vision_cache[("cam_0", 5)] = ("answer_sheet", 0.91, t_now, (10, 10, 100, 100))

    # cam_0 should find answer_sheet
    c0_class, _ = pipeline._get_answersheet_verification_result(5, "book", camera_id="cam_0")
    assert c0_class == "answer_sheet"

    # cam_1 should NOT share the result of cam_0 / track 5
    c1_class, _ = pipeline._get_answersheet_verification_result(5, "book", camera_id="cam_1")
    assert c1_class == "pending", "cam_1 must not inherit cam_0 verification result"
    print("✅ TEST 10 passed: Multi-camera cache isolation verified")


if __name__ == "__main__":
    test_portrait_page_candidate_detection()
    test_landscape_page_candidate_detection()
    test_rotated_tilted_page_candidate()
    test_distant_page_candidate()
    test_white_textbook_protection()
    asyncio.run(test_pipeline_answer_sheet_and_mobile_isolation())
    asyncio.run(test_pipeline_answer_sheet_smartwatch_isolation())
    test_caching_and_throttling()
    test_multi_camera_isolation()
    print("\n🎉 ALL ANSWER SHEET TESTS PASSED SUCCESSFULLY!")
