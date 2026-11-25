"""Unit and integration test suite for DeepSORT Track ID Stability.

Verifies that physical objects retain strictly consistent Track IDs across:
- Continuous frames
- Movement and translation
- Proximity and clustering
- Partial and brief occlusions
- Multi-object scenes (Person + Phone + Calculator + Book)
- Gemini semantic class updates (cell phone -> scientific_calculator)
"""

import math
import numpy as np
import pytest
from backend.agents.tracking_agent import TrackingAgent, Track, are_classes_compatible
from backend.agents.detection_agent import Detection


def make_det(bbox, class_name="cell phone", confidence=0.85):
    return Detection(
        bbox=list(bbox),
        confidence=confidence,
        class_name=class_name,
    )


def make_dummy_frame(width=640, height=480, objects=None):
    """Generate a realistic test image with colored patches for appearance testing."""
    frame = np.full((height, width, 3), 40, dtype=np.uint8)  # dark desk background
    if objects:
        for bbox, color in objects:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            frame[y1:y2, x1:x2] = color
    return frame


class TestTrackIdStability:
    """Comprehensive test suite verifying zero ID fluctuation."""

    def test_scenario_1_stationary_phone_stability(self):
        """Scenario 1: Stationary phone maintains constant Track ID over 30 frames."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        fixed_bbox = [100, 100, 200, 200]
        frame = make_dummy_frame(objects=[(fixed_bbox, (0, 0, 200))])

        track_ids_observed = []
        for i in range(30):
            # Add minor bounding box jitter (+-1 px) typical of YOLO
            jitter = (i % 3) - 1
            det = make_det([fixed_bbox[0] + jitter, fixed_bbox[1], fixed_bbox[2] + jitter, fixed_bbox[3]], "cell phone")
            tracks = tracker.update([det], frame=frame)
            assert len(tracks) == 1
            track_ids_observed.append(tracks[0].track_id)

        # Must maintain the initial track ID throughout all 30 frames
        initial_id = track_ids_observed[0]
        assert all(tid == initial_id for tid in track_ids_observed), (
            f"Track ID fluctuated for stationary phone: {track_ids_observed}"
        )
        assert len(set(track_ids_observed)) == 1

    def test_scenario_2_moving_phone_stability(self):
        """Scenario 2: Moving phone moving 3px per frame keeps constant Track ID."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        track_ids_observed = []

        for i in range(30):
            # Move by 3px horizontally each frame
            x1 = 100 + i * 3
            y1 = 120
            bbox = [x1, y1, x1 + 80, y1 + 140]
            frame = make_dummy_frame(objects=[(bbox, (20, 20, 220))])
            det = make_det(bbox, "cell phone")
            tracks = tracker.update([det], frame=frame)

            assert len(tracks) == 1
            track_ids_observed.append(tracks[0].track_id)

        initial_id = track_ids_observed[0]
        assert all(tid == initial_id for tid in track_ids_observed), (
            f"Moving phone ID changed: {track_ids_observed}"
        )

    def test_scenario_3_moving_calculator_stability(self):
        """Scenario 3: Moving calculator keeps constant Track ID."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        track_ids_observed = []

        for i in range(30):
            x1 = 200 + i * 2
            y1 = 200 + i * 1
            bbox = [x1, y1, x1 + 100, y1 + 150]
            frame = make_dummy_frame(objects=[(bbox, (50, 180, 50))])
            det = make_det(bbox, "calculator")
            tracks = tracker.update([det], frame=frame)

            assert len(tracks) == 1
            track_ids_observed.append(tracks[0].track_id)

        initial_id = track_ids_observed[0]
        assert all(tid == initial_id for tid in track_ids_observed), (
            f"Moving calculator ID changed: {track_ids_observed}"
        )

    def test_scenario_4_simultaneous_phone_and_calculator_no_swap(self):
        """Scenario 4: Phone and Calculator simultaneously visible maintain distinct unchanging IDs."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})

        phone_ids = []
        calc_ids = []

        for i in range(30):
            phone_bbox = [100 + i, 150, 180 + i, 280]
            calc_bbox = [350 - i, 150, 460 - i, 290]

            frame = make_dummy_frame(objects=[
                (phone_bbox, (0, 0, 255)),    # Phone: Red
                (calc_bbox, (0, 255, 128)),   # Calculator: Green
            ])

            dets = [
                make_det(phone_bbox, "cell phone"),
                make_det(calc_bbox, "calculator"),
            ]
            tracks = tracker.update(dets, frame=frame)
            assert len(tracks) == 2

            t_by_class = {t.class_name: t for t in tracks}
            phone_track = t_by_class["cell phone"]
            calc_track = t_by_class["calculator"]

            phone_ids.append(phone_track.track_id)
            calc_ids.append(calc_track.track_id)

        # Phone ID must never change
        assert len(set(phone_ids)) == 1, f"Phone IDs fluctuated: {phone_ids}"
        # Calculator ID must never change
        assert len(set(calc_ids)) == 1, f"Calculator IDs fluctuated: {calc_ids}"
        # Phone and Calculator must have completely different IDs
        assert phone_ids[0] != calc_ids[0]

    def test_scenario_5_proximity_close_objects_no_id_swap(self):
        """Scenario 5: Objects in close proximity (centers 70px apart) do not swap identities."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})

        phone_bbox = [200, 200, 260, 320]
        calc_bbox = [270, 200, 340, 320]  # Very close to phone

        frame = make_dummy_frame(objects=[
            (phone_bbox, (10, 10, 240)),  # Phone appearance
            (calc_bbox, (240, 10, 10)),   # Calculator appearance
        ])

        phone_id_init = None
        calc_id_init = None

        for i in range(25):
            # Slight jitter simulating video noise
            j = (i % 2)
            d1 = make_det([phone_bbox[0] + j, phone_bbox[1], phone_bbox[2] + j, phone_bbox[3]], "cell phone")
            d2 = make_det([calc_bbox[0] - j, calc_bbox[1], calc_bbox[2] - j, calc_bbox[3]], "calculator")

            tracks = tracker.update([d1, d2], frame=frame)
            assert len(tracks) == 2

            t_phone = next(t for t in tracks if t.class_name == "cell phone")
            t_calc = next(t for t in tracks if t.class_name == "calculator")

            if phone_id_init is None:
                phone_id_init = t_phone.track_id
                calc_id_init = t_calc.track_id

            assert t_phone.track_id == phone_id_init, f"Phone swapped ID to {t_phone.track_id}"
            assert t_calc.track_id == calc_id_init, f"Calculator swapped ID to {t_calc.track_id}"

    def test_scenario_6_partial_hand_occlusion(self):
        """Scenario 6: Partial hand occlusion preserves Track ID."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        full_bbox = [150, 150, 250, 300]
        occluded_bbox = [150, 180, 250, 300]  # Top 30px covered by hand

        frame_full = make_dummy_frame(objects=[(full_bbox, (0, 0, 200))])
        frame_occ = make_dummy_frame(objects=[(occluded_bbox, (0, 0, 180))])

        # 10 frames fully visible
        t_init = None
        for _ in range(10):
            tracks = tracker.update([make_det(full_bbox, "cell phone")], frame=frame_full)
            assert len(tracks) == 1
            if t_init is None:
                t_init = tracks[0].track_id
            assert tracks[0].track_id == t_init

        # 5 frames partially occluded
        for _ in range(5):
            tracks = tracker.update([make_det(occluded_bbox, "cell phone")], frame=frame_occ)
            assert len(tracks) == 1
            assert tracks[0].track_id == t_init, "Track ID changed during partial occlusion"

        # 10 frames fully visible again
        for _ in range(10):
            tracks = tracker.update([make_det(full_bbox, "cell phone")], frame=frame_full)
            assert len(tracks) == 1
            assert tracks[0].track_id == t_init, "Track ID failed to recover after occlusion"

    def test_scenario_7_full_short_occlusion_kalman_recovery(self):
        """Scenario 7: Full brief occlusion (missing for 2 frames) recovers identical Track ID."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        bbox = [100, 100, 200, 200]
        frame = make_dummy_frame(objects=[(bbox, (10, 10, 200))])

        # 5 frames visible
        t_id = None
        for _ in range(5):
            tracks = tracker.update([make_det(bbox, "cell phone")], frame=frame)
            t_id = tracks[0].track_id

        # 2 frames missing (complete occlusion)
        for _ in range(2):
            tracks = tracker.update([], frame=frame)
            # Display Rule: no current-frame detection -> must NOT be returned for display
            assert len(tracks) == 0
            # But internal track is preserved for re-identification
            assert t_id in tracker.tracks
            assert tracker.tracks[t_id].is_currently_detected is False

        # Reappears at same location
        tracks = tracker.update([make_det(bbox, "cell phone")], frame=frame)
        assert len(tracks) == 1
        assert tracks[0].track_id == t_id, f"Track ID reset to {tracks[0].track_id} after brief occlusion!"

    def test_scenario_8_multi_object_person_phone_calculator_book(self):
        """Scenario 8: Multi-object scene with Person + Phone + Calculator + Book."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})

        person_box = [50, 50, 300, 450]
        phone_box = [80, 250, 150, 350]
        calc_box = [200, 250, 280, 350]
        book_box = [350, 200, 550, 400]

        dets = [
            make_det(person_box, "person"),
            make_det(phone_box, "cell phone"),
            make_det(calc_box, "calculator"),
            make_det(book_box, "book"),
        ]

        # Over 20 frames, all 4 objects keep invariant IDs
        observed_ids = { "person": [], "cell phone": [], "calculator": [], "book": [] }

        for _ in range(20):
            tracks = tracker.update(dets)
            assert len(tracks) == 4
            for t in tracks:
                observed_ids[t.class_name].append(t.track_id)

        for cname, ids in observed_ids.items():
            assert len(set(ids)) == 1, f"Fluctuation in {cname}: {ids}"

        # Confirm person track has linked objects
        person_track = next(t for t in tracker.tracks.values() if t.class_name == "person")
        linked_classes = {o["class_name"] for o in person_track.objects_detected}
        assert "cell phone" in linked_classes
        assert "calculator" in linked_classes

    def test_scenario_9_gemini_class_change_persistence(self):
        """Scenario 9: Track 8 corrected by Gemini from cell phone -> scientific_calculator preserves Track 8."""
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})
        calc_bbox = [200, 200, 320, 340]
        frame = make_dummy_frame(objects=[(calc_bbox, (0, 255, 128))])

        # Frame 1: YOLO detects "cell phone" -> tracker assigns initial ID (e.g. 1)
        det1 = make_det(calc_bbox, "cell phone")
        tracks1 = tracker.update([det1], frame=frame)
        initial_id = tracks1[0].track_id
        assert initial_id == 1
        assert tracks1[0].class_name == "cell phone"

        # Frame 2: Gemini verifies this track as "scientific_calculator"
        tracker.update_track_class(initial_id, "scientific_calculator", safe=True)
        assert tracker.tracks[initial_id].class_name == "scientific_calculator"
        assert tracker.tracks[initial_id].safe is True

        # Frame 3-30: YOLO continues outputting "cell phone"
        # Due to class compatibility and DeepSORT IoU/appearance matching:
        # 1. It MUST match existing Track initial_id
        # 2. It MUST NOT re-initialize a new Track ID
        # 3. It MUST preserve "scientific_calculator" and safe=True
        for frame_idx in range(3, 31):
            det = make_det(calc_bbox, "cell phone")
            tracks = tracker.update([det], frame=frame)
            assert len(tracks) == 1
            t = tracks[0]
            assert t.track_id == initial_id, f"Frame {frame_idx}: Track ID changed to {t.track_id}!"
            assert t.class_name == "scientific_calculator", (
                f"Frame {frame_idx}: Class reverted to {t.class_name}!"
            )
            assert t.safe is True

    def test_scenario_10_simultaneous_phone_critical_and_calculator_safe_stability(self):
        """Scenario 10: Phone (Track 7) and Calculator (Track 8) simultaneously visible.

        Gemini confirms calculator as scientific_calculator (Safe), while phone remains Critical.
        Both IDs remain strictly stable across 30 frames with zero swapping.
        """
        tracker = TrackingAgent({"tracking": {"min_hits": 1, "max_age": 40}})

        phone_bbox = [100, 150, 180, 280]
        calc_bbox = [350, 150, 460, 280]

        frame = make_dummy_frame(objects=[
            (phone_bbox, (0, 0, 255)),    # Phone
            (calc_bbox, (0, 255, 128)),   # Calculator
        ])

        # Step 1: Initialize both tracks
        # YOLO initially sees both as "cell phone" (typical real-world model behavior)
        dets_init = [
            make_det(calc_bbox, "cell phone"),   # Initial track 1
            make_det(phone_bbox, "cell phone"),  # Initial track 2
        ]
        tracks_init = tracker.update(dets_init, frame=frame)
        assert len(tracks_init) == 2

        # Identify which track is which by position
        calc_track = next(t for t in tracks_init if t.bbox[0] > 300)
        phone_track = next(t for t in tracks_init if t.bbox[0] < 200)
        calc_id = calc_track.track_id
        phone_id = phone_track.track_id

        # Step 2: Gemini confirms calculator as scientific_calculator (Safe)
        tracker.update_track_class(calc_id, "scientific_calculator", safe=True)

        # Step 3: Run for 30 frames where YOLO detects "cell phone" at both bboxes
        for f_idx in range(30):
            dets = [
                make_det(phone_bbox, "cell phone"),
                make_det(calc_bbox, "cell phone"),
            ]
            tracks = tracker.update(dets, frame=frame)
            assert len(tracks) == 2

            t_calc = next(t for t in tracks if t.track_id == calc_id)
            t_phone = next(t for t in tracks if t.track_id == phone_id)

            # Assert Calculator is strictly stable, safe, and classified as scientific_calculator
            assert t_calc.track_id == calc_id
            assert t_calc.class_name == "scientific_calculator"
            assert t_calc.safe is True

            # Assert Phone is strictly stable, unsafe, and classified as cell phone
            assert t_phone.track_id == phone_id
            assert t_phone.class_name == "cell phone"
            assert t_phone.safe is False
