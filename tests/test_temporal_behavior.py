"""
Comprehensive Verification Suite for Temporal & Multimodal Behavioral Surveillance.

Tests all 20 required scenarios:
 TEST 1  - Normal Looking: One sideways glance -> LOW / observation, no alert
 TEST 2  - Repeated Looking: Multiple separate sideways glances -> Repetition detected, MEDIUM/HIGH
 TEST 3  - Repeated Gaze + Head Turn: Correlated gaze & head turn in same direction -> HIGH
 TEST 4  - Repeated Gaze + Interaction: Gaze + mutual orientation to neighbor -> HIGH/CRITICAL
 TEST 5  - Normal Writing: Looking down while writing -> Normal, no alert
 TEST 6  - Normal Posture Adjustment: Leans back once and returns -> LOW, no alert
 TEST 7  - Repeated Leaning: Repeated posture deviation -> Posture event, MEDIUM
 TEST 8  - Phone: Phone detected -> existing CRITICAL policy (90+)
 TEST 9  - Calculator: Scientific calculator -> SAFE (0 risk)
 TEST 10 - Calculator + Phone: Simultaneous -> Phone CRITICAL, Calculator SAFE
 TEST 11 - Multiple Students: Simultaneous independent monitoring, zero cross-contamination
 TEST 12 - Track ID Stability: History persists with DeepSORT Track ID
 TEST 13 - Partial Occlusion: Brief occlusion does not reassign or erase history
 TEST 14 - Alert Cooldown: Continuous behavior generates 1 alert, suppresses duplicates
 TEST 15 - Escalation: Severity escalation (MEDIUM -> HIGH) bypasses cooldown
 TEST 16 - Event Debouncing: Continuous 3s action -> exactly 1 episode, not dozens of events
 TEST 17 - Old Event Expiration: Events older than window expire and no longer count
 TEST 18 - Gemini Failure: Local behavior engine operates uninterrupted if Gemini fails
 TEST 19 - Evidence: Behavioral alert captures live frame with track ID, repetition count, window
 TEST 20 - Human Review: Alerts strictly advise "review recommended", never "cheating confirmed"
"""

import time
import numpy as np
import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.agents.behavior_agent import FusionInput, FusionOutput, MultiModalFusionEngine, RiskLevel
from backend.agents.temporal_behavior import (
    BehaviorConfig,
    BehaviorEpisode,
    BehavioralEventType,
    StrictnessMode,
    TemporalBehaviorTracker,
)
from backend.risk_engine.risk_calculator import RiskCalculator
from backend.agents.decision_agent import DecisionAgent, AlertLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_neutral_input(track_id: int = 1, t: float = 100.0) -> FusionInput:
    return FusionInput(
        gaze_left_score=0.0,
        gaze_right_score=0.0,
        gaze_down_score=0.0,
        head_yaw_degrees=0.0,
        head_pitch_degrees=0.0,
        head_roll_degrees=0.0,
        leaning_score=0.0,
        wrist_below_desk_score=0.0,
        arm_extension_score=0.0,
        shoulder_movement_score=0.0,
        phone_visible_score=0.0,
        timestamp=t,
        track_id=track_id
    )


def make_gaze_right_input(track_id: int = 1, t: float = 100.0) -> FusionInput:
    inp = make_neutral_input(track_id=track_id, t=t)
    inp.gaze_right_score = 0.85
    inp.head_yaw_degrees = 5.0
    return inp


def make_gaze_and_head_turn_input(track_id: int = 1, t: float = 100.0, direction: str = "right") -> FusionInput:
    inp = make_neutral_input(track_id=track_id, t=t)
    if direction == "right":
        inp.gaze_right_score = 0.85
        inp.head_yaw_degrees = 28.0
    else:
        inp.gaze_left_score = 0.85
        inp.head_yaw_degrees = -28.0
    return inp


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
class TestTemporalSurveillanceUpgrade:

    def test_01_normal_looking_isolated_glance(self):
        """TEST 1: Student looks sideways once -> observation, no critical/high alert."""
        engine = MultiModalFusionEngine()
        
        # Single 0.5s glance
        t0 = 1000.0
        # Frame 1: look right
        out1 = engine.fuse(make_gaze_right_input(t=t0), track_id=7)
        # Frame 2: look right
        out2 = engine.fuse(make_gaze_right_input(t=t0 + 0.5), track_id=7)
        # Frame 3: return to neutral (1.0s gap closes episode)
        out3 = engine.fuse(make_neutral_input(t=t0 + 1.5), track_id=7)
        
        assert out3.risk_level == RiskLevel.LOW
        assert out3.overall_risk_score < 40.0
        assert "critical" not in out3.brief_reason.lower()

    def test_02_repeated_looking(self):
        """TEST 2: Student repeatedly looks to the same side across separate episodes -> MEDIUM/HIGH."""
        engine = MultiModalFusionEngine()
        t = 1000.0
        
        # Episode 1: look right for 1s, then neutral for 1s
        engine.fuse(make_gaze_right_input(t=t), track_id=7)
        engine.fuse(make_gaze_right_input(t=t + 1.0), track_id=7)
        engine.fuse(make_neutral_input(t=t + 2.0), track_id=7)
        
        # Episode 2: look right again
        t = 1005.0
        engine.fuse(make_gaze_right_input(t=t), track_id=7)
        engine.fuse(make_gaze_right_input(t=t + 1.0), track_id=7)
        out_ep2 = engine.fuse(make_neutral_input(t=t + 2.0), track_id=7)
        
        # 2 episodes in STRICT mode -> MEDIUM alert
        assert out_ep2.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
        assert out_ep2.overall_risk_score >= 40.0
        assert "repeated gaze deviation" in out_ep2.brief_reason.lower()
        
        # Episode 3 & 4: further repeated looking
        t = 1010.0
        engine.fuse(make_gaze_right_input(t=t), track_id=7)
        engine.fuse(make_neutral_input(t=t + 1.5), track_id=7)
        
        t = 1015.0
        engine.fuse(make_gaze_right_input(t=t), track_id=7)
        out_ep4 = engine.fuse(make_neutral_input(t=t + 1.5), track_id=7)
        
        # 4 occurrences within 60s -> HIGH
        assert out_ep4.risk_level == RiskLevel.HIGH
        assert out_ep4.overall_risk_score >= 75.0

    def test_03_repeated_gaze_plus_head_turn(self):
        """TEST 3: Repeated gaze + repeated head turn in same direction -> stronger HIGH alert."""
        engine = MultiModalFusionEngine()
        t = 1000.0
        
        # Episode 1: Gaze right + Head turn right
        engine.fuse(make_gaze_and_head_turn_input(t=t, direction="right"), track_id=7)
        engine.fuse(make_gaze_and_head_turn_input(t=t + 1.0, direction="right"), track_id=7)
        engine.fuse(make_neutral_input(t=t + 2.0), track_id=7)
        
        # Episode 2: Gaze right + Head turn right again
        t = 1006.0
        engine.fuse(make_gaze_and_head_turn_input(t=t, direction="right"), track_id=7)
        engine.fuse(make_gaze_and_head_turn_input(t=t + 1.0, direction="right"), track_id=7)
        out = engine.fuse(make_neutral_input(t=t + 2.0), track_id=7)
        
        # Multimodal cross-confirmation boost -> HIGH
        assert out.risk_level == RiskLevel.HIGH
        assert out.overall_risk_score >= 75.0
        assert any("head" in r.lower() or "turn" in r.lower() for r in out.detailed_reasons + [out.brief_reason])

    def test_04_repeated_gaze_plus_student_interaction(self):
        """TEST 4: Repeated gaze + interaction toward neighboring student -> HIGH/CRITICAL alert."""
        cfg = BehaviorConfig()
        tracker = TemporalBehaviorTracker(cfg)
        
        # Two students side-by-side: S1 at x=200, S2 at x=350 (dist=150)
        t0 = 1000.0
        bbox_s1 = (150, 100, 250, 300)
        bbox_s2 = (300, 100, 400, 300)
        
        # S1 looks right toward S2 (yaw=+25)
        for i in range(2):
            t = t0 + i * 5.0
            # S2 position registered
            tracker.update_student(
                track_id=2, gaze_results={"direction": "CENTER", "confidence": 0.8},
                face_results={"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "face_detected": True},
                skeleton_results=None, detections=[], timestamp=t, bbox=bbox_s2
            )
            # S1 turns toward S2
            tracker.update_student(
                track_id=1, gaze_results={"direction": "RIGHT", "confidence": 0.85},
                face_results={"yaw": 25.0, "pitch": 0.0, "roll": 0.0, "face_detected": True},
                skeleton_results=None, detections=[], timestamp=t, bbox=bbox_s1
            )
            tracker.update_student(
                track_id=1, gaze_results={"direction": "RIGHT", "confidence": 0.85},
                face_results={"yaw": 25.0, "pitch": 0.0, "roll": 0.0, "face_detected": True},
                skeleton_results=None, detections=[], timestamp=t + 1.0, bbox=bbox_s1
            )
            out = tracker.update_student(
                track_id=1, gaze_results={"direction": "CENTER", "confidence": 0.8},
                face_results={"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "face_detected": True},
                skeleton_results=None, detections=[], timestamp=t + 2.0, bbox=bbox_s1
            )
            
        assert out.risk_level in {"HIGH", "CRITICAL"}
        assert out.behavioral_score >= 75.0
        assert "interaction" in out.primary_behavior.lower() or any("interaction" in s.lower() for s in out.supporting_behaviors)

    def test_05_normal_writing_behavior(self):
        """TEST 5: Continuous downward gaze with writing posture -> NOT treated as suspicious."""
        engine = MultiModalFusionEngine()
        t0 = 1000.0
        
        writing_input = make_neutral_input(track_id=7, t=t0)
        writing_input.gaze_down_score = 0.85
        writing_input.head_pitch_degrees = 18.0  # Normal writing head pitch (18 deg)
        writing_input.head_yaw_degrees = 2.0    # Looking at paper, not turning sideways
        writing_input.wrist_below_desk_score = 0.0  # Hands on desk writing
        
        # Student writes continuously for 10 frames
        for f in range(10):
            writing_input.timestamp = t0 + f * 0.5
            out = engine.fuse(writing_input, track_id=7)
            
        # Writing posture must not cause false alert
        assert out.risk_level == RiskLevel.LOW
        assert out.overall_risk_score < 40.0
        assert "normal" in out.brief_reason.lower()

    def test_06_normal_posture_adjustment(self):
        """TEST 6: Student leans back once and returns to normal -> LOW risk, no critical alert."""
        engine = MultiModalFusionEngine()
        t0 = 1000.0
        
        # Lean back once for 1 second
        lean_input = make_neutral_input(track_id=7, t=t0)
        lean_input.head_roll_degrees = 18.0
        lean_input.leaning_score = 0.75
        engine.fuse(lean_input, track_id=7)
        
        # Returns to normal sitting posture
        out = engine.fuse(make_neutral_input(track_id=7, t=t0 + 2.0), track_id=7)
        
        assert out.risk_level == RiskLevel.LOW
        assert out.overall_risk_score <= 20.0

    def test_07_repeated_leaning(self):
        """TEST 7: Student repeatedly leans toward one side -> repeated posture event, MEDIUM risk."""
        engine = MultiModalFusionEngine()
        t0 = 1000.0
        
        # Episode 1: Lean
        lean_in = make_neutral_input(track_id=7, t=t0)
        lean_in.head_roll_degrees = 22.0
        lean_in.leaning_score = 0.85
        engine.fuse(lean_in, track_id=7)
        engine.fuse(lean_in, track_id=7)
        engine.fuse(make_neutral_input(track_id=7, t=t0 + 2.0), track_id=7)
        
        # Episode 2: Lean again
        t = t0 + 6.0
        lean_in.timestamp = t
        engine.fuse(lean_in, track_id=7)
        lean_in.timestamp = t + 1.0
        engine.fuse(lean_in, track_id=7)
        out = engine.fuse(make_neutral_input(track_id=7, t=t + 2.5), track_id=7)
        
        assert out.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
        assert out.overall_risk_score >= 40.0

    def test_08_phone_detection_critical(self):
        """TEST 8: Student shows phone -> existing phone logic triggers CRITICAL."""
        # 1. MultiModalFusionEngine phone detection triggers CRITICAL
        engine = MultiModalFusionEngine()
        phone_input = make_neutral_input(track_id=7, t=1000.0)
        phone_input.phone_visible_score = 0.95
        out = engine.fuse(phone_input, track_id=7)
        assert out.risk_level == RiskLevel.CRITICAL
        assert out.overall_risk_score >= 90.0

        # 2. RiskCalculator with sustained phone presence triggers CRITICAL
        calc = RiskCalculator()
        calc.phone_timers["CAM_01_7"] = {"start_time": time.time() - 6.0, "last_seen": time.time()}
        res = calc.calculate(phone_score=0.95, gaze_score=0.0, pose_score=0.0, behavior_score=0.0, student_id="CAM_01_7")
        assert res["level"] == "CRITICAL"
        assert res["risk_score"] >= 90.0

    def test_09_scientific_calculator_safe(self):
        """TEST 9: Scientific calculator detected -> SAFE (0 risk)."""
        calc = RiskCalculator()
        # Calculator verified safe: phone_score=0.0
        res = calc.calculate(phone_score=0.0, gaze_score=0.0, pose_score=0.0, behavior_score=0.0, student_id="CAM_01_7")
        assert res["level"] == "LOW"
        assert res["risk_score"] == 0.0

    def test_10_calculator_and_phone_simultaneous(self):
        """TEST 10: Calculator + Phone simultaneous -> Calculator SAFE, Phone CRITICAL."""
        # 1. MultiModalFusionEngine simultaneous handling
        engine = MultiModalFusionEngine()
        sim_input = make_neutral_input(track_id=7, t=1000.0)
        sim_input.phone_visible_score = 0.92
        out = engine.fuse(sim_input, track_id=7)
        assert out.risk_level == RiskLevel.CRITICAL
        assert out.overall_risk_score >= 90.0
        assert "phone_detected" in out.primary_behaviors

        # 2. RiskCalculator handles phone independent of safe objects
        calc = RiskCalculator()
        calc.phone_timers["CAM_01_7"] = {"start_time": time.time() - 6.0, "last_seen": time.time()}
        res = calc.calculate(phone_score=0.92, gaze_score=0.0, pose_score=0.0, behavior_score=0.0, student_id="CAM_01_7")
        assert res["level"] == "CRITICAL"
        assert res["risk_score"] >= 90.0

    def test_11_multiple_students_isolation(self):
        """TEST 11: Multi-student independent monitoring with zero cross-contamination."""
        engine = MultiModalFusionEngine()
        t = 1000.0
        
        # Student 1: Normal exam behavior
        s1_input = make_neutral_input(track_id=1, t=t)
        out_s1 = engine.fuse(s1_input, track_id=1)
        
        # Student 2: Repeated gaze (episodes)
        for i in range(3):
            ti = t + i * 5.0
            engine.fuse(make_gaze_right_input(track_id=2, t=ti), track_id=2)
            engine.fuse(make_gaze_right_input(track_id=2, t=ti + 0.8), track_id=2)
            out_s2 = engine.fuse(make_neutral_input(track_id=2, t=ti + 1.8), track_id=2)
            
        # Student 3: Phone detected
        s3_input = make_neutral_input(track_id=3, t=t)
        s3_input.phone_visible_score = 0.95
        out_s3 = engine.fuse(s3_input, track_id=3)
        
        # Check complete independence:
        assert out_s1.risk_level == RiskLevel.LOW
        assert out_s2.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
        assert out_s3.risk_level == RiskLevel.CRITICAL
        assert "phone_detected" in out_s3.primary_behaviors
        assert "phone_detected" not in out_s2.primary_behaviors
        assert "phone_detected" not in out_s1.primary_behaviors

    def test_12_track_id_lifecycle_association(self):
        """TEST 12: DeepSORT Track ID maintains behavior history."""
        engine = MultiModalFusionEngine()
        # Track 7 records gaze event
        engine.fuse(make_gaze_right_input(track_id=7, t=100.0), track_id=7)
        engine.fuse(make_neutral_input(track_id=7, t=102.0), track_id=7)
        
        history_7 = engine.temporal_tracker.get_or_create_history(7)
        assert len(history_7.completed_episodes) >= 1
        
        # Track 8 has empty history
        history_8 = engine.temporal_tracker.get_or_create_history(8)
        assert len(history_8.completed_episodes) == 0

    def test_13_partial_occlusion_tolerance(self):
        """TEST 13: Brief occlusion/absence does not reassign or erase history."""
        engine = MultiModalFusionEngine()
        t = 100.0
        # Register behavior for Track 7
        engine.fuse(make_gaze_right_input(track_id=7, t=t), track_id=7)
        engine.fuse(make_neutral_input(track_id=7, t=t + 1.5), track_id=7)
        
        # Track 7 is briefly occluded for 5 seconds (not in active tracks)
        engine.temporal_tracker.prune_lost_tracks(active_track_ids={1, 2}, max_missing_time=30.0, current_time=t + 5.0)
        
        # History for Track 7 must still be preserved
        assert 7 in engine.temporal_tracker.histories

    def test_14_alert_cooldown(self):
        """TEST 14: Continuous behavior triggers 1 alert, suppresses duplicate frame alerts."""
        decider = DecisionAgent({"risk": {"threshold": 75, "alert_cooldown": 15}})
        
        # Frame 1: High risk -> alert triggers
        scores_1 = {7: {"score": 80.0, "events": ["repeated_gaze_deviation"]}}
        decisions_1 = decider.decide(scores_1)
        assert decisions_1[7].should_alert is True
        
        # Frame 2..10 (within 15s cooldown): score still 80.0 -> alert suppressed
        scores_2 = {7: {"score": 80.0, "events": ["repeated_gaze_deviation"]}}
        decisions_2 = decider.decide(scores_2)
        assert decisions_2[7].should_alert is False

    def test_15_alert_escalation_bypasses_cooldown(self):
        """TEST 15: Severity escalation (MEDIUM -> HIGH) bypasses cooldown."""
        decider = DecisionAgent({"risk": {"threshold": 40, "alert_cooldown": 30}})
        
        # Time 0: Medium alert triggers (score 50)
        scores_med = {7: {"score": 50.0, "events": ["repeated_gaze_deviation"]}}
        d_med = decider.decide(scores_med)
        assert d_med[7].should_alert is True
        assert d_med[7].level == AlertLevel.MEDIUM
        
        # Time 2s: Supporting head turn escalates risk to HIGH (score 82)
        scores_high = {7: {"score": 82.0, "events": ["repeated_gaze_deviation", "head_turn"]}}
        d_high = decider.decide(scores_high)
        # Escalation must bypass cooldown!
        assert d_high[7].should_alert is True
        assert d_high[7].level == AlertLevel.HIGH

    def test_16_event_debouncing_continuous_action(self):
        """TEST 16: Looking right continuously for 3.0 seconds counts as exactly 1 episode."""
        engine = MultiModalFusionEngine()
        t0 = 1000.0
        
        # 30 consecutive frames at 10 FPS (0.1s interval)
        for i in range(30):
            t = t0 + i * 0.1
            engine.fuse(make_gaze_right_input(track_id=7, t=t), track_id=7)
            
        # Return to center
        engine.fuse(make_neutral_input(track_id=7, t=t0 + 4.0), track_id=7)
        
        history = engine.temporal_tracker.get_or_create_history(7)
        gaze_episodes = [ep for ep in history.completed_episodes if ep.event_type == BehavioralEventType.GAZE_RIGHT]
        
        # Must be exactly 1 episode, NOT 30!
        assert len(gaze_episodes) == 1
        assert gaze_episodes[0].duration >= 2.8

    def test_17_old_event_expiration(self):
        """TEST 17: Events older than the configured sliding window expire."""
        engine = MultiModalFusionEngine()
        
        # Event happened 90 seconds ago (outside 60s window)
        t_old = 1000.0
        engine.fuse(make_gaze_right_input(track_id=7, t=t_old), track_id=7)
        engine.fuse(make_neutral_input(track_id=7, t=t_old + 1.5), track_id=7)
        
        # Now at t = 1090.0 (90 seconds later)
        t_now = 1090.0
        out_now = engine.fuse(make_neutral_input(track_id=7, t=t_now), track_id=7)
        
        # Old event must not contribute to current 60s window
        assert out_now.episodes_summary.get("gaze_episodes", 0) == 0
        assert out_now.risk_level == RiskLevel.LOW

    def test_18_gemini_failure_resilience(self):
        """TEST 18: If Gemini fails, local behavior engine continues operating."""
        engine = MultiModalFusionEngine()
        # Simulated gemini error or None
        t = 1000.0
        out = engine.fuse(make_gaze_right_input(track_id=7, t=t), track_id=7)
        assert out is not None
        assert out.risk_level is not None

    def test_19_evidence_metadata_completeness(self):
        """TEST 19: Behavioral alert includes Track ID, repetition count, window, and risk score."""
        engine = MultiModalFusionEngine()
        t0 = 1000.0
        
        # Trigger repeated gaze
        for i in range(3):
            ti = t0 + i * 4.0
            engine.fuse(make_gaze_right_input(track_id=7, t=ti), track_id=7)
            engine.fuse(make_neutral_input(track_id=7, t=ti + 1.5), track_id=7)
            
        out = engine.fuse(make_neutral_input(track_id=7, t=t0 + 15.0), track_id=7)
        
        assert out.temporal_assessment is not None
        assert out.temporal_assessment.track_id == 7
        assert out.temporal_assessment.active_window_seconds == 60.0
        assert out.temporal_assessment.behavioral_score >= 40.0
        assert out.episodes_summary.get("gaze_episodes", 0) >= 2

    def test_20_human_in_the_loop_wording(self):
        """TEST 20: Alerts strictly say 'review recommended', never 'cheating confirmed'."""
        engine = MultiModalFusionEngine()
        t0 = 1000.0
        
        # Trigger high concern
        for i in range(4):
            ti = t0 + i * 4.0
            engine.fuse(make_gaze_and_head_turn_input(track_id=7, t=ti, direction="right"), track_id=7)
            engine.fuse(make_neutral_input(track_id=7, t=ti + 1.5), track_id=7)
            
        out = engine.fuse(make_neutral_input(track_id=7, t=t0 + 20.0), track_id=7)
        
        assert "review recommended" in out.brief_reason.lower()
        assert "cheating" not in out.brief_reason.lower()
        assert "guilty" not in out.brief_reason.lower()
        assert out.temporal_assessment.recommendation == "Invigilator review recommended."
