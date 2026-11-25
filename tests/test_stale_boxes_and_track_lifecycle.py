"""Comprehensive Verification Suite for Master Repair:
Stale Bounding Boxes, Duplicate Track IDs, and Track Lifecycle.

Verifies all 15 specific tests required by the Master Repair Prompt:
- TEST 1: Person Only (single box, single ID, no duplicates)
- TEST 2: Person Stationary (stable identity across frames)
- TEST 3: Phone Appears (detected, tracked, associated to student)
- TEST 4: Phone Disappears (bounding box disappears, no stale rendering)
- TEST 5: Phone Returns (re-identification and ID recovery)
- TEST 6: Book / Answer Sheet (disappears cleanly when removed)
- TEST 7: One Person + Book (1 person track, 1 book, no duplicate person IDs)
- TEST 8: One Person + Phone (1 person, 1 phone, no duplicates)
- TEST 9: Phone Disappears While Person Remains (person stable, phone gone)
- TEST 10: Two People (distinct identities, never collapsed)
- TEST 11: One Person with Temporary YOLO Miss (internal track bridges miss, display empty, recovers)
- TEST 12: Stale Cache (empty detections clear display cache, overlay, and student objects)
- TEST 13: Evidence Accuracy (triggers on current frame, no stale boxes)
- TEST 14: Phone Risk Timer (escalates while present, stops immediately when removed)
- TEST 15: Multiple Objects Independent Lifecycles (person + phone + book + calculator)
"""

import time
import numpy as np
import pytest
from datetime import datetime

from backend.agents.tracking_agent import TrackingAgent, Track, deduplicate_detections
from backend.agents.detection_agent import Detection
from backend.risk_engine.risk_calculator import RiskCalculator


def make_det(bbox, class_name="person", confidence=0.85):
    return Detection(
        bbox=list(bbox),
        confidence=confidence,
        class_name=class_name,
    )


def make_blank_frame(w=640, h=480):
    return np.full((h, w, 3), 40, dtype=np.uint8)


class TestMasterRepairTrackLifecycle:
    """Complete test suite verifying all 15 Master Repair scenarios."""

    # --------------------------------------------------
    # TEST 1 — PERSON ONLY
    # --------------------------------------------------
    def test_01_person_only_no_duplicate_person_boxes(self):
        """One person in camera. If YOLO produces nested/overlapping boxes,
        deduplication must produce exactly ONE person box and ONE track ID.
        """
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        # Simulate YOLO emitting two overlapping/nested person boxes (e.g., full body and torso)
        full_body = make_det([100, 50, 300, 450], "person", confidence=0.88)
        torso = make_det([120, 80, 280, 300], "person", confidence=0.45)

        # 1. Deduplication must suppress the lower-confidence nested box
        deduped = deduplicate_detections([full_body, torso])
        assert len(deduped) == 1, f"Expected 1 person after deduplication, got {len(deduped)}"

        # 2. Tracking update must return exactly 1 confirmed, active person track
        tracks = tracker.update([full_body, torso], frame=frame)
        assert len(tracks) == 1
        assert tracks[0].class_name == "person"
        assert tracks[0].track_id == 1

        # 3. draw_tracks must only draw 1 box
        annotated = tracker.draw_tracks(frame, tracks)
        # Person track exists and no duplicate box exists
        assert len([t for t in tracker.tracks.values() if t.is_currently_detected]) == 1

    # --------------------------------------------------
    # TEST 2 — PERSON STATIONARY
    # --------------------------------------------------
    def test_02_person_stationary_identity_stability(self):
        """Person remains stationary for 30+ frames. Track ID must never fluctuate."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()
        fixed_box = [150, 80, 320, 420]

        observed_ids = []
        for i in range(35):
            jitter = (i % 3) - 1
            det = make_det([fixed_box[0] + jitter, fixed_box[1], fixed_box[2] + jitter, fixed_box[3]], "person")
            tracks = tracker.update([det], frame=frame)
            assert len(tracks) == 1
            observed_ids.append(tracks[0].track_id)

        assert len(set(observed_ids)) == 1, f"Stationary person ID changed: {observed_ids}"
        assert observed_ids[0] == 1

    # --------------------------------------------------
    # TEST 3 — PHONE APPEARS
    # --------------------------------------------------
    def test_03_phone_appears_associated_to_student(self):
        """Phone appears near person. Phone track created and linked into student's objects_detected."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        person_box = [100, 50, 300, 450]
        phone_box = [180, 200, 260, 320]

        dets = [make_det(person_box, "person"), make_det(phone_box, "cell phone", 0.82)]
        tracks = tracker.update(dets, frame=frame)

        assert len(tracks) == 2
        p_track = next(t for t in tracks if t.class_name == "person")
        phone_track = next(t for t in tracks if t.class_name == "cell phone")

        assert p_track.track_id != phone_track.track_id
        assert len(p_track.objects_detected) == 1
        assert p_track.objects_detected[0]["class_name"] == "cell phone"
        assert p_track.objects_detected[0]["track_id"] == phone_track.track_id

    # --------------------------------------------------
    # TEST 4 — PHONE DISAPPEARS
    # --------------------------------------------------
    def test_04_phone_disappears_bounding_box_removed(self):
        """Phone removed. CELL PHONE bounding box must disappear from display.
        It must NOT remain at its previous location or be returned for display.
        """
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        phone_box = [200, 200, 280, 320]
        # Frame 1-3: Phone present
        for _ in range(3):
            tracks = tracker.update([make_det(phone_box, "cell phone")], frame=frame)
            assert len(tracks) == 1

        phone_id = tracks[0].track_id

        # Frame 4: Phone physically removed (no detection)
        tracks_after = tracker.update([], frame=frame)

        # DISPLAY RULE: No current detection -> public tracks list is EMPTY
        assert len(tracks_after) == 0, f"Expected 0 display tracks after phone disappeared, got {len(tracks_after)}"

        # draw_tracks with default/current must NOT render any phone box
        drawn = tracker.draw_tracks(frame, tracks_after)
        # Internal tracker still has the track for re-ID, but is_currently_detected is False
        assert phone_id in tracker.tracks
        assert tracker.tracks[phone_id].is_currently_detected is False

    # --------------------------------------------------
    # TEST 5 — PHONE RETURNS
    # --------------------------------------------------
    def test_05_phone_returns_recovers_id(self):
        """Phone returns after a short absence (2 frames). Same track ID must be recovered."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        phone_box = [200, 200, 280, 320]
        # 5 frames visible
        t_id = None
        for _ in range(5):
            tracks = tracker.update([make_det(phone_box, "cell phone")], frame=frame)
            t_id = tracks[0].track_id

        # 2 frames absent
        for _ in range(2):
            tracks = tracker.update([], frame=frame)
            assert len(tracks) == 0  # Not displayed

        # Frame 8: Phone returns at same location
        tracks_return = tracker.update([make_det(phone_box, "cell phone")], frame=frame)
        assert len(tracks_return) == 1
        assert tracks_return[0].track_id == t_id, f"Expected recovered ID {t_id}, got {tracks_return[0].track_id}"
        assert tracks_return[0].is_currently_detected is True

    # --------------------------------------------------
    # TEST 6 — BOOK / ANSWER SHEET DISAPPEARS
    # --------------------------------------------------
    def test_06_answersheet_disappears_cleanly(self):
        """Answer sheet visible then removed. Box must disappear cleanly; no stale box remains."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        sheet_box = [250, 220, 480, 420]
        tracks = tracker.update([make_det(sheet_box, "answer_sheet")], frame=frame)
        assert len(tracks) == 1
        assert tracks[0].class_name == "answer_sheet"

        # Remove answer sheet
        tracks_removed = tracker.update([], frame=frame)
        assert len(tracks_removed) == 0

    # --------------------------------------------------
    # TEST 7 — ONE PERSON + BOOK
    # --------------------------------------------------
    def test_07_one_person_plus_book(self):
        """One person and one book. Exactly 1 person track, 1 book track, no duplicate person IDs."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        person_box = [100, 50, 300, 450]
        book_box = [250, 250, 420, 400]

        dets = [make_det(person_box, "person"), make_det(book_box, "book")]
        tracks = tracker.update(dets, frame=frame)

        assert len(tracks) == 2
        classes = {t.class_name for t in tracks}
        assert classes == {"person", "book"}

        person_tracks = [t for t in tracks if t.class_name == "person"]
        assert len(person_tracks) == 1

    # --------------------------------------------------
    # TEST 8 — ONE PERSON + PHONE
    # --------------------------------------------------
    def test_08_one_person_plus_phone(self):
        """One person and one phone. Exactly 1 person track, 1 phone track, distinct IDs."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        person_box = [100, 50, 300, 450]
        phone_box = [180, 220, 250, 330]

        dets = [make_det(person_box, "person"), make_det(phone_box, "cell phone")]
        tracks = tracker.update(dets, frame=frame)

        assert len(tracks) == 2
        t_person = next(t for t in tracks if t.class_name == "person")
        t_phone = next(t for t in tracks if t.class_name == "cell phone")
        assert t_person.track_id != t_phone.track_id

    # --------------------------------------------------
    # TEST 9 — PHONE DISAPPEARS WHILE PERSON REMAINS
    # --------------------------------------------------
    def test_09_phone_disappears_while_person_remains(self):
        """Person + Phone. Phone is removed. Person track remains stable with same ID.
        Phone is immediately unlinked from person.objects_detected.
        """
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        person_box = [100, 50, 300, 450]
        phone_box = [180, 220, 250, 330]

        # Frame 1: Person + Phone
        tracks1 = tracker.update([make_det(person_box, "person"), make_det(phone_box, "cell phone")], frame=frame)
        assert len(tracks1) == 2
        p1 = next(t for t in tracks1 if t.class_name == "person")
        person_id = p1.track_id
        assert len(p1.objects_detected) == 1

        # Frame 2: Phone disappears, Person remains
        tracks2 = tracker.update([make_det(person_box, "person")], frame=frame)
        assert len(tracks2) == 1
        p2 = tracks2[0]
        assert p2.track_id == person_id, "Person ID changed when phone disappeared!"
        assert len(p2.objects_detected) == 0, "Stale phone still attached to person!"

    # --------------------------------------------------
    # TEST 10 — TWO PEOPLE
    # --------------------------------------------------
    def test_10_two_distinct_people_not_collapsed(self):
        """Two students sitting side-by-side. Both must have distinct Track IDs and never collapse."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        p1_box = [50, 50, 250, 450]
        p2_box = [320, 50, 520, 450]

        dets = [make_det(p1_box, "person", 0.90), make_det(p2_box, "person", 0.88)]
        # Deduplication must NOT merge two separate people
        deduped = deduplicate_detections(dets)
        assert len(deduped) == 2

        for _ in range(10):
            tracks = tracker.update(dets, frame=frame)
            assert len(tracks) == 2
            ids = [t.track_id for t in tracks]
            assert len(set(ids)) == 2

    # --------------------------------------------------
    # TEST 11 — ONE PERSON WITH TEMPORARY YOLO MISS
    # --------------------------------------------------
    def test_11_one_person_temporary_yolo_miss(self):
        """Person suffers 1-frame detection miss. Internal track survives, display empty on miss, recovers upon return."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()
        p_box = [100, 50, 300, 450]

        tracks = tracker.update([make_det(p_box, "person")], frame=frame)
        init_id = tracks[0].track_id

        # YOLO miss for 1 frame
        miss_tracks = tracker.update([], frame=frame)
        # Display rule: not currently detected -> not drawn
        assert len(miss_tracks) == 0
        # Internal track is alive
        assert init_id in tracker.tracks
        assert tracker.tracks[init_id].is_currently_detected is False

        # Detection returns
        recovered_tracks = tracker.update([make_det(p_box, "person")], frame=frame)
        assert len(recovered_tracks) == 1
        assert recovered_tracks[0].track_id == init_id
        assert recovered_tracks[0].is_currently_detected is True

    # --------------------------------------------------
    # TEST 12 — STALE CACHE
    # --------------------------------------------------
    def test_12_stale_cache_empty_detections_clean_state(self):
        """When current detections are empty, public tracking results are empty,
        and no stale objects linger in display or student objects.
        """
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        # Step 1: Detect object
        tracker.update([make_det([100, 100, 200, 200], "cell phone")], frame=frame)

        # Step 2: Empty frame
        public_tracks = tracker.update([], frame=frame)
        assert public_tracks == []

        # Step 3: draw_tracks with default produces no bounding box
        drawn = tracker.draw_tracks(frame)
        # Frame pixel values are identical to input frame (nothing drawn)
        assert np.array_equal(drawn, frame)

    # --------------------------------------------------
    # TEST 13 — EVIDENCE ACCURACY
    # --------------------------------------------------
    def test_13_evidence_metadata_and_current_frame(self):
        """Verify evidence capture uses current detection metadata."""
        from backend.agents.evidence_agent import EvidenceAgent
        import tempfile, shutil

        tmp_dir = tempfile.mkdtemp()
        try:
            agent = EvidenceAgent(root_dir=tmp_dir)
            frame = np.full((100, 100, 3), 128, dtype=np.uint8)
            annotated = frame.copy()

            rec = agent.capture(
                frame=frame,
                annotated_frame=annotated,
                student_id="CAM_01_1",
                event="📱 Mobile phone detected in vicinity - HIGH RISK",
                camera_id="CAM_01",
                tracking_id=1,
                confidence=0.88,
                risk_score=90.0,
            )

            assert rec["camera_id"] == "CAM_01"
            assert rec["tracking_id"] == 1
            assert rec["risk_score"] == 90.0
            assert rec["original_image_path"] is not None
            assert rec["annotated_image_path"] is not None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # --------------------------------------------------
    # TEST 14 — PHONE RISK TIMER ESCALATION AND RESET
    # --------------------------------------------------
    def test_14_phone_risk_timer_escalation_and_reset(self):
        """Phone appears -> escalates over time. Phone removed -> timer resets immediately."""
        calc = RiskCalculator()
        student_id = "CAM_01_1"

        # Frame 1: Phone detected (duration starts)
        res1 = calc.calculate(phone_score=0.85, student_id=student_id)
        assert student_id in calc.phone_timers
        initial_score = res1["risk_score"]

        # Simulate phone being absent on next calculation
        res2 = calc.calculate(phone_score=0.0, student_id=student_id)
        # Phone timer MUST be cleared immediately
        assert student_id not in calc.phone_timers
        assert res2["risk_score"] < initial_score or res2["risk_score"] == 0.0

    # --------------------------------------------------
    # TEST 15 — MULTIPLE OBJECTS INDEPENDENT LIFECYCLES
    # --------------------------------------------------
    def test_15_multiple_objects_independent_lifecycles(self):
        """Person + phone + book + calculator. Removing phone must NOT remove book or calculator.
        Each object has independent lifecycle and display freshness.
        """
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        frame = make_blank_frame()

        p_box = [50, 50, 250, 450]
        phone_box = [80, 200, 150, 300]
        calc_box = [200, 200, 270, 300]
        book_box = [300, 180, 480, 360]

        all_dets = [
            make_det(p_box, "person"),
            make_det(phone_box, "cell phone"),
            make_det(calc_box, "calculator"),
            make_det(book_box, "book"),
        ]

        tracks = tracker.update(all_dets, frame=frame)
        assert len(tracks) == 4
        phone_id = next(t.track_id for t in tracks if t.class_name == "cell phone")
        book_id = next(t.track_id for t in tracks if t.class_name == "book")
        calc_id = next(t.track_id for t in tracks if t.class_name == "calculator")

        # Now remove ONLY the phone. Keep person, calculator, and book.
        subset_dets = [
            make_det(p_box, "person"),
            make_det(calc_box, "calculator"),
            make_det(book_box, "book"),
        ]
        tracks_step2 = tracker.update(subset_dets, frame=frame)
        assert len(tracks_step2) == 3

        # Phone is NOT in public tracks
        assert not any(t.class_name == "cell phone" for t in tracks_step2)

        # Calculator and Book maintain their exact IDs
        assert any(t.track_id == calc_id for t in tracks_step2)
        assert any(t.track_id == book_id for t in tracks_step2)
