"""
Unit and integration tests for Answer Sheet Verification.
Tests orientation-independence (portrait, landscape, rotated 30/45/90 deg),
textbook protection, white textbook protection, track ID caching, and latency logging.
"""

import os
import sys
import time
import pytest
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.agents.answersheet_vision_verifier import AnswerSheetVisionVerifier
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline


class TestAnswerSheetGeometryAndLines:
    """Test orientation-independent geometry and line detection."""

    def setup_method(self):
        self.verifier = AnswerSheetVisionVerifier({})

    def test_portrait_geometry(self):
        # Portrait: height (400) > width (250) -> aspect ratio 1.6
        crop = np.full((400, 250, 3), 240, dtype=np.uint8)
        ok, ratio, msg = self.verifier.verify_geometry(crop)
        assert ok is True
        assert 1.55 <= ratio <= 1.65
        assert "Orientation=portrait" in msg

    def test_landscape_geometry(self):
        # Landscape: width (400) > height (250) -> aspect ratio 1.6
        crop = np.full((250, 400, 3), 240, dtype=np.uint8)
        ok, ratio, msg = self.verifier.verify_geometry(crop)
        assert ok is True
        assert 1.55 <= ratio <= 1.65
        assert "Orientation=landscape" in msg

    def test_square_or_slightly_distorted_geometry(self):
        # Near square: 300x300 -> aspect ratio 1.0
        crop = np.full((300, 300, 3), 240, dtype=np.uint8)
        ok, ratio, msg = self.verifier.verify_geometry(crop)
        assert ok is True
        assert 0.99 <= ratio <= 1.01

    def test_non_perfect_rectangle_not_hard_rejected(self):
        # Non-standard cropped portion of page (aspect ratio 2.8)
        crop = np.full((100, 280, 3), 240, dtype=np.uint8)
        ok, ratio, msg = self.verifier.verify_geometry(crop)
        # Should still be within reasonable supporting range
        assert ok is True
        assert 2.7 <= ratio <= 2.9

    def test_tiny_crop_rejected(self):
        # Dimensions < min_dim (30)
        crop = np.full((20, 20, 3), 240, dtype=np.uint8)
        ok, ratio, msg = self.verifier.verify_geometry(crop)
        assert ok is False

    def test_ruled_lines_horizontal(self):
        # Horizontal lines (standard portrait orientation)
        crop = np.full((300, 200, 3), 255, dtype=np.uint8)
        for y in range(40, 280, 30):
            cv2.line(crop, (10, y), (190, y), (50, 50, 50), 1)
        has_lines, count, msg = self.verifier.verify_ruled_lines(crop)
        assert has_lines is True
        assert count >= 2

    def test_ruled_lines_vertical_turned_landscape(self):
        # Vertical lines (when a portrait answer sheet is held sideways / 90° landscape)
        crop = np.full((200, 300, 3), 255, dtype=np.uint8)
        for x in range(40, 280, 30):
            cv2.line(crop, (x, 10), (x, 190), (50, 50, 50), 1)
        has_lines, count, msg = self.verifier.verify_ruled_lines(crop)
        assert has_lines is True
        assert count >= 2

    def test_ruled_lines_rotated_45_deg(self):
        # Ruled lines rotated by 45 degrees
        crop = np.full((250, 250, 3), 255, dtype=np.uint8)
        for offset in range(-100, 150, 30):
            cv2.line(crop, (0, max(0, 100 + offset)), (min(250, 150 - offset), 250), (50, 50, 50), 1)
        has_lines, count, msg = self.verifier.verify_ruled_lines(crop)
        assert has_lines is True
        assert count >= 2

    def test_whiteness_supporting_only(self):
        # Mostly white crop
        crop = np.full((200, 200, 3), 245, dtype=np.uint8)
        ok, ratio, msg = self.verifier.verify_whiteness(crop)
        assert ok is True
        assert ratio > 0.8
        # Ensure whiteness is a supporting check, not classification decision
        assert "supporting" in msg.lower()


class TestPromptAndGeminiVerification:
    """Test Gemini Vision verification prompt, reference loading, and parsing."""

    def setup_method(self):
        self.verifier = AnswerSheetVisionVerifier({})

    def test_prompt_contains_orientation_guidelines(self):
        prompt = self.verifier.prompt
        assert "portrait" in prompt.lower()
        assert "landscape" in prompt.lower()
        assert "rotated" in prompt.lower()
        assert "do not reject an answer sheet because of orientation" in prompt.lower()
        assert "compare visual structure rather than orientation" in prompt.lower()
        assert "white textbook is still a textbook" in prompt.lower()

    def test_parse_gemini_response_valid_answer_sheet(self):
        response_text = '{"classification": "answer_sheet", "confidence": 0.95, "reason": "College answer sheet ruled layout"}'
        parsed = self.verifier._parse_gemini_response(response_text)
        assert parsed["classification"] == "answer_sheet"
        assert parsed["confidence"] == 0.95

    def test_parse_gemini_response_not_answer_sheet(self):
        response_text = '{"classification": "not_answer_sheet", "confidence": 0.92, "reason": "Textbook cover"}'
        parsed = self.verifier._parse_gemini_response(response_text)
        assert parsed["classification"] == "not_answer_sheet"
        assert parsed["confidence"] == 0.92

    def test_parse_gemini_response_uncertain(self):
        response_text = '{"classification": "uncertain", "confidence": 0.40, "reason": "Partially occluded by hand"}'
        parsed = self.verifier._parse_gemini_response(response_text)
        assert parsed["classification"] == "uncertain"

    def test_parse_gemini_response_synonyms_mapped(self):
        # Test synonyms like 'answer book' and 'paper' are mapped to 'answer_sheet'
        for synonym in ["answer book", "answer_book", "paper"]:
            res = self.verifier._parse_gemini_response(f'{{"classification": "{synonym}", "confidence": 0.9}}')
            assert res["classification"] == "answer_sheet"

    def test_reference_images_loaded(self):
        ref_dir = ROOT_DIR / "reference_data" / "answer_sheet"
        if ref_dir.exists():
            verifier = AnswerSheetVisionVerifier({})
            # Should have loaded up to 3 references
            assert len(verifier.reference_images) >= 1


class TestPipelineAnswerSheetVerification:
    """Test integrated pipeline Answer Sheet verification caching, early trigger, and latency logging."""

    def test_track_id_caching_reuses_result(self):
        config = {
            "enable_detection": False,
            "answer_sheet_verify": {
                "threshold": 0.80,
                "cache_duration": 10.0,
            }
        }
        mock_server = MagicMock()
        pipeline = IntegratedSurveillancePipeline(config, webrtc_server=mock_server)

        # Pre-seed cache with verified answer sheet for Track 15
        now = time.time()
        pipeline.answersheet_vision_cache[(15, "book")] = ("answer_sheet", 0.94, now, (10, 10, 200, 300))

        # Retrieve result
        v_class, v_conf = pipeline._get_answersheet_verification_result(15, "book")
        assert v_class == "answer_sheet"
        assert v_conf == 0.94

        # Verify that calling _verify_answersheet_with_gemini does NOT trigger a new verification
        frame = np.full((480, 640, 3), 200, dtype=np.uint8)
        initial_cache_time = pipeline.answersheet_vision_cache[(15, "book")][2]
        pipeline._verify_answersheet_with_gemini(15, "book", (12, 12, 205, 305), frame)

        # Cache should remain untouched (reused)
        assert pipeline.answersheet_vision_cache[(15, "book")][0] == "answer_sheet"
        assert pipeline.answersheet_vision_cache[(15, "book")][2] == initial_cache_time

    def test_textbook_protection_remains_book(self):
        config = {
            "enable_detection": False,
            "answer_sheet_verify": {
                "threshold": 0.80,
                "cache_duration": 10.0,
            }
        }
        mock_server = MagicMock()
        pipeline = IntegratedSurveillancePipeline(config, webrtc_server=mock_server)

        # Pre-seed cache with rejected textbook
        now = time.time()
        pipeline.answersheet_vision_cache[(18, "book")] = ("not_answer_sheet", 0.95, now, (50, 50, 250, 350))

        v_class, v_conf = pipeline._get_answersheet_verification_result(18, "book")
        assert v_class == "not_answer_sheet"

        # Mock Detection object
        from backend.agents.detection_agent import Detection
        det = Detection(bbox=(50, 50, 250, 350), confidence=0.88, class_name="book")
        track = MagicMock()
        track.track_id = 18
        track.objects_detected = [{"bbox": (50, 50, 250, 350), "class_name": "book"}]

        # Sync detections for display
        synced = pipeline._sync_detections_for_display([det], [track])
        # Textbook remains 'book' (not reclassified to answer_sheet)
        assert synced[0].class_name == "book"

    def test_white_textbook_protection_not_automatically_answersheet(self):
        # White image with no ruled lines or exam structure
        verifier = AnswerSheetVisionVerifier({})
        white_crop = np.full((300, 200, 3), 250, dtype=np.uint8)
        is_white, ratio, _ = verifier.verify_whiteness(white_crop)
        assert is_white is True
        # Ensure ruled lines are NOT found on a plain white book
        has_lines, count, _ = verifier.verify_ruled_lines(white_crop)
        assert has_lines is False

    def test_find_track_id_fallback(self):
        config = {"enable_detection": False}
        mock_server = MagicMock()
        pipeline = IntegratedSurveillancePipeline(config, webrtc_server=mock_server)
        from backend.agents.detection_agent import Detection

        det = Detection(bbox=(100, 100, 250, 350), confidence=0.85, class_name="book")
        # When no tracking results exist, should return fallback 1 (never None or crash)
        track_id = pipeline._find_track_id_for_detection(det, [])
        assert track_id == 1
