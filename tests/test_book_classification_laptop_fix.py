"""
Unit and integration tests for Book / Answer Sheet classification and complete LAPTOP elimination.
Verifies all 13 required scenarios specified in the Master Antigravity Prompt:
1. Open textbook -> BOOK
2. Open textbook for 30s -> stable BOOK
3. Move textbook -> BOOK
4. Partially cover textbook with hands -> BOOK (never LAPTOP)
5. Actual answer sheet -> ANSWER_SHEET after sufficient verification
6. Gemini unavailable -> no LAPTOP and no classification flicker
7. YOLO produces class 63 laptop for an open book -> IGNORE LAPTOP and retain BOOK candidate
8. BOOK -> false LAPTOP -> BOOK YOLO sequence -> final classification remains BOOK
9. Book disappears -> BOOK box disappears
10. Book returns -> BOOK classification can resume/recover
11. Person + Book -> PERSON + BOOK
12. Person + Answer Sheet -> PERSON + ANSWER_SHEET
13. Person + Book + Phone -> PERSON + BOOK + CELL PHONE independently
"""

import os
import time
import numpy as np
import cv2
import pytest

from backend.agents.detection_agent import Detection, DetectionAgent
from backend.agents.tracking_agent import Track, TrackingAgent, are_classes_compatible, DEVICE_CLASSES, PAPER_CLASSES
from backend.agents.answersheet_vision_verifier import AnswerSheetVisionVerifier
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline
from backend.risk_engine.risk_calculator import RiskCalculator


def create_mock_frame(h=480, w=640, color=(120, 120, 120)):
    """Create a mock BGR frame."""
    return np.full((h, w, 3), color, dtype=np.uint8)


def create_book_crop(h=150, w=200, colorful=True):
    """Create a mock textbook crop with a colorful or darker cover / non-white pages."""
    crop = np.full((h, w, 3), (40, 100, 180) if colorful else (80, 80, 80), dtype=np.uint8)
    for y in range(20, h - 20, 15):
        cv2.line(crop, (15, y), (w - 15, y), (20, 20, 20), 1)
    return crop


def create_answer_sheet_crop(h=200, w=150):
    """Create a mock answer sheet crop: >= 95% near-white with ruled horizontal lines."""
    crop = np.full((h, w, 3), (250, 250, 250), dtype=np.uint8)
    cv2.rectangle(crop, (6, 6), (w - 6, h - 6), (110, 110, 110), 1)
    for y in range(30, h - 20, 25):
        cv2.line(crop, (10, y), (w - 10, y), (120, 120, 120), 1)
    return crop


class TestBookClassificationAndLaptopElimination:
    """Test suite for Master Antigravity Prompt book & answer sheet classification."""

    @classmethod
    def setup_class(cls):
        cls.config = {
            "book_verification": {
                "enabled": True,
                "answer_sheet_white_ratio": 0.95,
                "temporal_confirmation_frames": 3,
                "threshold": 0.80,
                "cache_duration": 10.0,
            },
            "answer_sheet_verify": {
                "threshold": 0.80,
                "temporal_confirmation_frames": 3,
            },
            "mobile_detection": {"conf_min": 0.30},
            "enable_detection": False,  # Pipeline uses shared agents
        }
        cls.verifier = AnswerSheetVisionVerifier(cls.config)
        cls.pipeline = IntegratedSurveillancePipeline(cls.config)

    def setup_method(self):
        self.tracker = TrackingAgent()
        self.pipeline.tracker = self.tracker
        self.pipeline.answersheet_vision_cache.clear()
        self.pipeline._book_temporal_history.clear()
        self.pipeline._book_confirmed_labels.clear()
        self.pipeline._book_last_logged_info.clear()

    # -----------------------------------------------------------------
    # Test 1: Open textbook -> Expected: BOOK
    # -----------------------------------------------------------------
    def test_01_open_textbook_classified_as_book(self):
        crop = create_book_crop(colorful=True)
        res_class, conf, metrics = self.verifier.verify_candidate_semantics(crop, yolo_conf=0.85)
        assert res_class == "book", f"Expected BOOK for normal textbook, got {res_class}"
        assert "laptop" not in res_class.lower()

    # -----------------------------------------------------------------
    # Test 2: Open textbook for 30 seconds (90 frames) -> Expected: stable BOOK
    # -----------------------------------------------------------------
    def test_02_open_textbook_stable_over_time(self):
        frame = create_mock_frame()
        crop = create_book_crop(colorful=True)
        book_box = (100, 150, 260, 320)
        frame[150:320, 100:260] = cv2.resize(crop, (160, 170))

        observed_ids = set()
        observed_classes = set()

        for f_idx in range(90):
            det = Detection(bbox=book_box, confidence=0.88, class_name="book")
            tracks = self.tracker.update([det], frame=frame)
            sync_dets = self.pipeline._sync_detections_for_display([det], tracks, camera_id="cam_0")

            assert len(tracks) == 1
            observed_ids.add(tracks[0].track_id)
            assert len(sync_dets) == 1
            observed_classes.add(sync_dets[0].class_name)

        assert len(observed_ids) == 1, f"Track ID must remain strictly identical, got {observed_ids}"
        assert observed_classes == {"book"}, f"Class must remain strictly BOOK, got {observed_classes}"

    # -----------------------------------------------------------------
    # Test 3: Move textbook -> Expected: BOOK
    # -----------------------------------------------------------------
    def test_03_move_textbook_stability(self):
        frame = create_mock_frame()
        observed_ids = set()

        for i in range(25):
            x1 = 80 + i * 4
            y1 = 120 + i * 2
            x2 = x1 + 150
            y2 = y1 + 120
            det = Detection(bbox=(x1, y1, x2, y2), confidence=0.85, class_name="book")
            tracks = self.tracker.update([det], frame=frame)
            sync_dets = self.pipeline._sync_detections_for_display([det], tracks, camera_id="cam_0")

            assert len(tracks) == 1
            observed_ids.add(tracks[0].track_id)
            assert sync_dets[0].class_name == "book"

        assert len(observed_ids) == 1, "Moving book must maintain single continuous track ID"

    # -----------------------------------------------------------------
    # Test 4: Partially cover textbook with hands -> Expected: BOOK or stable, NOT LAPTOP
    # -----------------------------------------------------------------
    def test_04_partially_covered_textbook_not_laptop(self):
        crop = create_book_crop(colorful=False)
        crop[30:80, 40:100] = (140, 170, 220)
        res_class, conf, metrics = self.verifier.verify_candidate_semantics(crop, yolo_conf=0.75)
        assert res_class in {"book", "answer_sheet"}, f"Must not be an invalid class: {res_class}"
        assert res_class != "laptop"
        assert "laptop" not in res_class

    # -----------------------------------------------------------------
    # Test 5: Actual answer sheet -> Expected: ANSWER_SHEET after verification
    # -----------------------------------------------------------------
    def test_05_actual_answer_sheet_verification(self):
        frame = create_mock_frame()
        as_crop = create_answer_sheet_crop(h=200, w=150)
        as_box = (150, 100, 300, 300)
        frame[100:300, 150:300] = as_crop

        # Feed consecutive frames
        for f in range(5):
            det = Detection(bbox=as_box, confidence=0.85, class_name="book")
            tracks = self.tracker.update([det], frame=frame)
            self.pipeline._trigger_early_answersheet_verification([det], tracks, frame, camera_id="cam_0")
            sync_dets = self.pipeline._sync_detections_for_display([det], tracks, camera_id="cam_0")

        # After >= 3 confirming frames, the answer sheet is confirmed
        assert sync_dets[0].class_name == "answer_sheet"
        assert tracks[0].class_name == "answer_sheet"

    # -----------------------------------------------------------------
    # Test 6: Gemini unavailable -> Expected: no LAPTOP and no classification flicker
    # -----------------------------------------------------------------
    def test_06_gemini_unavailable_no_laptop_no_flicker(self):
        self.pipeline.answersheet_verifier.model = None
        frame = create_mock_frame()
        book_box = (100, 100, 250, 220)
        book_crop = create_book_crop(colorful=True)
        frame[100:220, 100:250] = cv2.resize(book_crop, (150, 120))

        for f in range(10):
            det = Detection(bbox=book_box, confidence=0.82, class_name="book")
            tracks = self.tracker.update([det], frame=frame)
            self.pipeline._trigger_early_answersheet_verification([det], tracks, frame, camera_id="cam_0")
            sync_dets = self.pipeline._sync_detections_for_display([det], tracks, camera_id="cam_0")
            assert sync_dets[0].class_name == "book"
            assert "laptop" not in sync_dets[0].class_name

    # -----------------------------------------------------------------
    # Test 7: YOLO produces class 63 laptop for an open book -> Expected: IGNORE LAPTOP and retain BOOK candidate
    # -----------------------------------------------------------------
    def test_07_yolo_class_63_laptop_ignored_retained_as_book_candidate(self):
        class DummyBox:
            def __init__(self, cls_id, conf, xyxy):
                self.cls = [cls_id]
                self.conf = [conf]
                self.xyxy = [xyxy]

        class DummyResults:
            def __init__(self, boxes):
                self.boxes = boxes

        class DummyModel:
            def __init__(self):
                self.names = {0: "person", 63: "laptop", 73: "book"}
            def __call__(self, frame, **kwargs):
                return [DummyResults([DummyBox(63, 0.78, (120, 100, 320, 260))])]

        det_agent = DetectionAgent(self.config)
        det_agent.model = DummyModel()

        frame = create_mock_frame()
        detections = det_agent.detect(frame)

        # 1. LAPTOP must NOT be in detections
        assert not any(d.class_name == "laptop" for d in detections), "LAPTOP must never be emitted!"
        # 2. Must retain as a BOOK candidate
        book_cands = [d for d in detections if d.class_name == "book"]
        assert len(book_cands) >= 1, "Must retain candidate as a BOOK candidate"
        assert book_cands[0].is_candidate is True

    # -----------------------------------------------------------------
    # Test 8: BOOK -> false LAPTOP -> BOOK YOLO sequence -> Expected: final classification remains BOOK
    # -----------------------------------------------------------------
    def test_08_book_false_laptop_book_sequence_stable(self):
        frame = create_mock_frame()
        book_box = (100, 100, 260, 240)

        # Frame 1: YOLO gives BOOK
        det1 = Detection(bbox=book_box, confidence=0.85, class_name="book")
        tracks1 = self.tracker.update([det1], frame=frame)
        sync1 = self.pipeline._sync_detections_for_display([det1], tracks1, camera_id="cam_0")
        assert sync1[0].class_name == "book"
        track_id = tracks1[0].track_id

        # Frame 2: YOLO produces class 63 (laptop) on the same book
        # DetectionAgent ignores LAPTOP and outputs a BOOK candidate
        det2 = Detection(bbox=book_box, confidence=0.75, class_name="book", is_candidate=True)
        tracks2 = self.tracker.update([det2], frame=frame)
        sync2 = self.pipeline._sync_detections_for_display([det2], tracks2, camera_id="cam_0")
        assert tracks2[0].track_id == track_id, "Track ID must remain identical on frame 2"
        assert sync2[0].class_name == "book", "Classification must remain BOOK on frame 2"

        # Frame 3: YOLO gives BOOK
        det3 = Detection(bbox=book_box, confidence=0.88, class_name="book")
        tracks3 = self.tracker.update([det3], frame=frame)
        sync3 = self.pipeline._sync_detections_for_display([det3], tracks3, camera_id="cam_0")
        assert tracks3[0].track_id == track_id, "Track ID must remain identical on frame 3"
        assert sync3[0].class_name == "book", "Classification must remain BOOK on frame 3"

        # Verify no LAPTOP track was ever created
        assert all(t.class_name != "laptop" for t in self.tracker.tracks.values())

    # -----------------------------------------------------------------
    # Test 9: Book disappears -> Expected: BOOK box disappears
    # -----------------------------------------------------------------
    def test_09_book_disappears_box_disappears(self):
        frame = create_mock_frame()
        book_box = (100, 100, 250, 220)

        for _ in range(3):
            det = Detection(bbox=book_box, confidence=0.85, class_name="book")
            tracks = self.tracker.update([det], frame=frame)
            assert len(tracks) == 1

        empty_tracks = self.tracker.update([], frame=frame)
        assert len(empty_tracks) == 0, "No tracks must be returned for display after disappearance"

        drawn = self.tracker.draw_tracks(frame.copy(), empty_tracks)
        assert np.array_equal(drawn, frame), "No bounding box must be drawn when book is absent"

    # -----------------------------------------------------------------
    # Test 10: Book returns -> Expected: BOOK classification can resume/recover
    # -----------------------------------------------------------------
    def test_10_book_returns_recovers_classification(self):
        frame = create_mock_frame()
        book_box = (100, 100, 250, 220)

        det = Detection(bbox=book_box, confidence=0.85, class_name="book")
        tracks = self.tracker.update([det], frame=frame)
        initial_id = tracks[0].track_id

        for _ in range(3):
            self.tracker.update([], frame=frame)

        tracks_returned = self.tracker.update([det], frame=frame)
        assert len(tracks_returned) == 1
        assert tracks_returned[0].track_id == initial_id, "Track ID should recover upon return"
        assert tracks_returned[0].class_name == "book"

    # -----------------------------------------------------------------
    # Test 11: Person + Book -> Expected: PERSON + BOOK
    # -----------------------------------------------------------------
    def test_11_person_plus_book(self):
        frame = create_mock_frame()
        p_det = Detection(bbox=(50, 50, 250, 400), confidence=0.90, class_name="person")
        b_det = Detection(bbox=(300, 200, 450, 350), confidence=0.85, class_name="book")

        tracks = self.tracker.update([p_det, b_det], frame=frame)
        sync_dets = self.pipeline._sync_detections_for_display([p_det, b_det], tracks, camera_id="cam_0")

        classes = {d.class_name for d in sync_dets}
        assert classes == {"person", "book"}, f"Expected PERSON + BOOK, got {classes}"

    # -----------------------------------------------------------------
    # Test 12: Person + Answer Sheet -> Expected: PERSON + ANSWER_SHEET
    # -----------------------------------------------------------------
    def test_12_person_plus_answer_sheet(self):
        frame = create_mock_frame()
        as_crop = create_answer_sheet_crop(h=200, w=150)
        as_box = (300, 180, 450, 380)
        frame[180:380, 300:450] = as_crop

        p_det = Detection(bbox=(50, 50, 250, 400), confidence=0.90, class_name="person")
        as_det = Detection(bbox=as_box, confidence=0.88, class_name="book")

        for _ in range(4):
            tracks = self.tracker.update([p_det, as_det], frame=frame)
            self.pipeline._trigger_early_answersheet_verification([p_det, as_det], tracks, frame, camera_id="cam_0")
            sync_dets = self.pipeline._sync_detections_for_display([p_det, as_det], tracks, camera_id="cam_0")

        classes = {d.class_name for d in sync_dets}
        assert classes == {"person", "answer_sheet"}, f"Expected PERSON + ANSWER_SHEET, got {classes}"

    # -----------------------------------------------------------------
    # Test 13: Person + Book + Phone -> Expected: PERSON + BOOK + CELL PHONE independently
    # -----------------------------------------------------------------
    def test_13_person_plus_book_plus_phone(self):
        frame = create_mock_frame()
        p_det = Detection(bbox=(50, 50, 250, 400), confidence=0.90, class_name="person")
        b_det = Detection(bbox=(300, 200, 450, 350), confidence=0.85, class_name="book")
        phone_det = Detection(bbox=(180, 220, 220, 300), confidence=0.80, class_name="cell phone")

        tracks = self.tracker.update([p_det, b_det, phone_det], frame=frame)
        sync_dets = self.pipeline._sync_detections_for_display([p_det, b_det, phone_det], tracks, camera_id="cam_0")

        classes = {d.class_name for d in sync_dets}
        assert classes == {"person", "book", "cell phone"}, f"Expected PERSON + BOOK + CELL PHONE, got {classes}"

        rc = RiskCalculator()
        res_phone = rc.calculate(phone_score=0.80, student_id="student_1")
        assert res_phone["risk_score"] > 30.0, "Active phone must score risk"

        res_book_only = rc.calculate(phone_score=0.0, student_id="student_1")
        assert res_book_only["risk_score"] == 0.0, "Book alone must produce 0 phone risk"
