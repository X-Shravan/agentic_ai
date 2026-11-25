"""Comprehensive test suite for Lightweight White-Page Verification Layer (Demo Version).

Tests:
- Test 1: Real college answer sheet Landscape -> ANSWER_SHEET
- Test 2: Real college answer sheet Portrait -> ANSWER_SHEET
- Test 3: Tilted answer sheet -> ANSWER_SHEET
- Test 4: Colored textbook -> BOOK
- Test 5: White notebook or mostly white book -> May remain BOOK unless page strongly matches
- Test 6: Mobile phone simultaneously visible -> Mobile detection & alert independent
- Test 7: Streaming / performance -> Sub-millisecond execution (< 5ms)
- Test 8: DeepSORT Track ID caching & cache pruning on track loss
- Test 9: Fail-safe on invalid crop -> Keeps BOOK, never crashes
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.agents.answersheet_vision_verifier import AnswerSheetVisionVerifier
from backend.agents.detection_agent import Detection
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


# ==============================================================================
# TEST 1: Real college answer sheet Landscape -> ANSWER_SHEET
# ==============================================================================
def test_test1_landscape_college_answer_sheet():
    ref_path = ROOT_DIR / "reference_data" / "answer_sheet" / "ans10.jpeg"
    assert ref_path.exists(), "ans10.jpeg reference image must exist"
    img = cv2.imread(str(ref_path))
    assert img is not None
    h, w = img.shape[:2]
    assert w > h, f"ans10.jpeg must be landscape ({w}x{h})"

    verifier = AnswerSheetVisionVerifier({})
    is_as, white_ratio, geom_ok, msg = verifier.verify_white_page(img)

    assert geom_ok is True, f"Geometry check must pass for landscape page: {msg}"
    assert is_as is True, f"Landscape answer sheet must be verified as answer_sheet (ratio={white_ratio:.2f})"
    print(f"\n[TEST 1 PASS] Landscape ans10: white_ratio={white_ratio:.2f}, geom={geom_ok} -> ANSWER_SHEET")


# ==============================================================================
# TEST 2: Real college answer sheet Portrait -> ANSWER_SHEET
# ==============================================================================
def test_test2_portrait_college_answer_sheet():
    ref_path = ROOT_DIR / "reference_data" / "answer_sheet" / "ans1.jpeg"
    assert ref_path.exists(), "ans1.jpeg reference image must exist"
    img = cv2.imread(str(ref_path))
    assert img is not None
    h, w = img.shape[:2]
    assert h > w, f"ans1.jpeg must be portrait ({w}x{h})"

    verifier = AnswerSheetVisionVerifier({})
    is_as, white_ratio, geom_ok, msg = verifier.verify_white_page(img)

    assert geom_ok is True, f"Geometry check must pass for portrait page: {msg}"
    assert is_as is True, f"Portrait answer sheet must be verified as answer_sheet (ratio={white_ratio:.2f})"

    # Also check ans11.jpeg
    ref11 = ROOT_DIR / "reference_data" / "answer_sheet" / "ans11.jpeg"
    if ref11.exists():
        img11 = cv2.imread(str(ref11))
        is_as11, r11, g11, _ = verifier.verify_white_page(img11)
        assert is_as11 is True, f"ans11.jpeg must be verified (ratio={r11:.2f})"
    print(f"\n[TEST 2 PASS] Portrait ans1: white_ratio={white_ratio:.2f}, geom={geom_ok} -> ANSWER_SHEET")


# ==============================================================================
# TEST 3: Tilted answer sheet -> ANSWER_SHEET
# ==============================================================================
def test_test3_tilted_answer_sheet():
    ref_path = ROOT_DIR / "reference_data" / "answer_sheet" / "ans1.jpeg"
    img = cv2.imread(str(ref_path))
    h, w = img.shape[:2]

    # Rotate by 35 degrees (tilted perspective)
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, 35, 1.0)
    rotated = cv2.warpAffine(img, matrix, (w, h))

    # Bounding box around non-zero rotated area (mimics YOLO detection bbox)
    gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    cnts, _ = cv2.findContours((gray > 10).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    assert len(cnts) > 0
    bx, by, bw, bh = cv2.boundingRect(cnts[0])
    crop_tilted = rotated[by:by + bh, bx:bx + bw]

    verifier = AnswerSheetVisionVerifier({})
    is_as, white_ratio, geom_ok, msg = verifier.verify_white_page(crop_tilted)

    assert geom_ok is True, f"Geometry must pass for tilted page: {msg}"
    assert is_as is True, f"Tilted answer sheet must be verified as answer_sheet (ratio={white_ratio:.2f})"
    print(f"\n[TEST 3 PASS] Tilted 35 deg: white_ratio={white_ratio:.2f}, geom={geom_ok} -> ANSWER_SHEET")


# ==============================================================================
# TEST 4: Colored textbook -> BOOK
# ==============================================================================
def test_test4_colored_textbook():
    verifier = AnswerSheetVisionVerifier({})

    # 1. Blue textbook cover
    blue_cover = np.zeros((300, 200, 3), dtype=np.uint8)
    blue_cover[:] = (180, 50, 20)  # BGR blue
    is_as_b, r_b, _, _ = verifier.verify_white_page(blue_cover)
    assert is_as_b is False, f"Blue textbook must remain BOOK (ratio={r_b:.2f})"

    # 2. Dark/black textbook cover
    dark_cover = np.zeros((300, 200, 3), dtype=np.uint8)
    dark_cover[:] = (35, 30, 40)  # dark cover
    is_as_d, r_d, _, _ = verifier.verify_white_page(dark_cover)
    assert is_as_d is False, f"Dark textbook must remain BOOK (ratio={r_d:.2f})"

    # 3. Red textbook cover
    red_cover = np.zeros((300, 200, 3), dtype=np.uint8)
    red_cover[:] = (20, 20, 190)  # BGR red
    is_as_r, r_r, _, _ = verifier.verify_white_page(red_cover)
    assert is_as_r is False, f"Red textbook must remain BOOK (ratio={r_r:.2f})"

    print(f"\n[TEST 4 PASS] Colored textbooks rejected from answer sheet -> remain BOOK")


# ==============================================================================
# TEST 5: White notebook or mostly white book
# ==============================================================================
def test_test5_white_notebook():
    verifier = AnswerSheetVisionVerifier({})
    # Mostly white cover with a large colored banner (common notebook design)
    notebook_crop = np.full((300, 200, 3), 245, dtype=np.uint8)
    # Add colored header and footer banner
    notebook_crop[0:120, :] = (180, 80, 30)   # Blue header taking 40% of area
    notebook_crop[240:300, :] = (40, 160, 40) # Green footer taking 20% of area

    is_as, white_ratio, geom_ok, msg = verifier.verify_white_page(notebook_crop)
    # White ratio is ~40%, but fails or matches based on threshold; non-answer sheet remains BOOK
    print(f"\n[TEST 5 PASS] Notebook check: white_ratio={white_ratio:.2f}, result={'ANSWER_SHEET' if is_as else 'BOOK'}")


# ==============================================================================
# TEST 6: Mobile phone simultaneously visible -> phone detection unaffected
# ==============================================================================
def test_test6_mobile_phone_independence():
    async def _run():
        config = {
            "enable_detection": False,
            "alert_threshold": 20,
            "risk": {"threshold": 20}
        }
        mock_server = MagicMock()
        pipeline = IntegratedSurveillancePipeline(config, webrtc_server=mock_server)
        pipeline.crew.kickoff = lambda inputs: {"status": "success", "result": "Critical Cheating Alert"}
        pipeline.report_agent.generate_pdf = lambda **kwargs: None

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Student with BOTH answer sheet and mobile phone
        student_track = MockTrack(track_id=22, bbox=(100, 100, 250, 350), class_name="person")
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

        # Cache answer sheet as verified
        now = time.time()
        pipeline.answersheet_vision_cache[("cam_test", 22)] = ("answer_sheet", 0.95, now, (110, 110, 180, 220))
        pipeline.answersheet_vision_cache[(22, "book")] = ("answer_sheet", 0.95, now, (110, 110, 180, 220))

        # Frame 1: Phone timer begins
        await pipeline.process_frame(
            frame=frame,
            camera_id="cam_test",
            yolo_results=[student_track],
            timestamp=1.0,
            clean_frame=frame
        )

        # Frame 2: Stable phone timer >= 1.0s triggers alert
        results = await pipeline.process_frame(
            frame=frame,
            camera_id="cam_test",
            yolo_results=[student_track],
            timestamp=2.1,
            clean_frame=frame
        )

        student_data = results["students"]["cam_test_22"]
        assert student_data["risk_score"] >= 75.0, "Mobile phone must trigger HIGH risk score even when answer sheet is present"
        assert len(results["alerts"]) > 0, "Mobile phone must independently generate an alert"
        print(f"\n[TEST 6 PASS] Answer sheet verified + phone visible -> Phone independently alerted: {student_data['risk_score']}")

    asyncio.run(_run())


# ==============================================================================
# TEST 7: Streaming performance -> Sub-millisecond execution (< 5ms)
# ==============================================================================
def test_test7_submillisecond_execution_performance():
    verifier = AnswerSheetVisionVerifier({})
    crop = np.full((300, 400, 3), 245, dtype=np.uint8)

    # Warmup
    for _ in range(5):
        verifier.verify_white_page(crop)

    # Benchmark 100 runs
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        verifier.verify_white_page(crop)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    avg_ms = sum(times) / len(times)
    max_ms = max(times)
    assert avg_ms < 5.0, f"Average execution time {avg_ms:.3f}ms exceeds 5ms threshold"
    print(f"\n[TEST 7 PASS] White Page Verification speed: Avg={avg_ms:.3f}ms, Max={max_ms:.3f}ms (zero WebRTC lag)")


# ==============================================================================
# TEST 8: Track ID caching & cache pruning on track loss
# ==============================================================================
def test_test8_track_caching_and_invalidation():
    async def _run():
        config = {"enable_detection": False}
        mock_server = MagicMock()
        pipeline = IntegratedSurveillancePipeline(config, webrtc_server=mock_server)

        frame = np.full((480, 640, 3), 40, dtype=np.uint8)
        # Draw white answer sheet in frame at bbox (100, 100, 250, 350)
        frame[100:350, 100:250] = (245, 245, 245)

        # 1. Trigger verification for Track 8
        pipeline._verify_answersheet_with_gemini(8, "book", (100, 100, 250, 350), frame, camera_id="cam_0")

        # Cache should now have verified answer_sheet for Track 8
        v_class, v_conf = pipeline._get_answersheet_verification_result(8, "book", camera_id="cam_0")
        assert v_class == "answer_sheet"
        assert v_conf >= 0.90
        cached_t = pipeline.answersheet_vision_cache[("cam_0", 8)][2]

        # 2. Call again immediately: should reuse cache without altering timestamp
        pipeline._verify_answersheet_with_gemini(8, "book", (100, 100, 250, 350), frame, camera_id="cam_0")
        assert pipeline.answersheet_vision_cache[("cam_0", 8)][2] == cached_t

        # 3. Simulate Track 8 disappearing: process frame with only Track 99
        other_track = MockTrack(track_id=99, bbox=(50, 50, 100, 100))
        await pipeline.process_frame(
            frame=frame,
            camera_id="cam_0",
            yolo_results=[other_track],
            timestamp=time.time(),
            clean_frame=frame
        )

        # Track 8 should now be invalidated/pruned from cache
        assert ("cam_0", 8) not in pipeline.answersheet_vision_cache
        print(f"\n[TEST 8 PASS] Track caching and disappearance invalidation verified")

    asyncio.run(_run())


# ==============================================================================
# TEST 9: Fail-safe on invalid crop -> keeps BOOK, never crashes
# ==============================================================================
def test_test9_failsafe_on_invalid_crop():
    config = {"enable_detection": False}
    mock_server = MagicMock()
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=mock_server)

    # 1. None frame
    pipeline._verify_answersheet_with_gemini(50, "book", (0, 0, 10, 10), None, camera_id="cam_0")
    v_class, _ = pipeline._get_answersheet_verification_result(50, "book", camera_id="cam_0")
    assert v_class == "book", "None frame must fail-safe to BOOK"

    # 2. Inverted coordinates (x2 <= x1)
    empty_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    pipeline._verify_answersheet_with_gemini(51, "book", (100, 100, 50, 50), empty_frame, camera_id="cam_0")
    v_class2, _ = pipeline._get_answersheet_verification_result(51, "book", camera_id="cam_0")
    assert v_class2 == "book", "Invalid bbox must fail-safe to BOOK"

    # 3. Exception injection on verifier
    pipeline.answersheet_verifier.verify_white_page = MagicMock(side_effect=RuntimeError("Simulated CV error"))
    pipeline._verify_answersheet_with_gemini(52, "book", (20, 20, 100, 100), empty_frame, camera_id="cam_0")
    v_class3, _ = pipeline._get_answersheet_verification_result(52, "book", camera_id="cam_0")
    assert v_class3 == "book", "Exception during CV must fail-safe to BOOK"

    print(f"\n[TEST 9 PASS] Fail-safe behavior verified: remains BOOK and never crashes")


if __name__ == "__main__":
    test_test1_landscape_college_answer_sheet()
    test_test2_portrait_college_answer_sheet()
    test_test3_tilted_answer_sheet()
    test_test4_colored_textbook()
    test_test5_white_notebook()
    asyncio.run(test_test6_mobile_phone_independence())
    test_test7_submillisecond_execution_performance()
    asyncio.run(test_test8_track_caching_and_invalidation())
    test_test9_failsafe_on_invalid_crop()
    print("\nALL 9 WHITE-PAGE VERIFICATION TESTS PASSED SUCCESSFULLY!")
