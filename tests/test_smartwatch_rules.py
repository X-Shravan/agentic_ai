import sys
import os
import numpy as np
import cv2
import pytest
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.detection_agent import DetectionAgent, Detection
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline
from agentic_exam_surveillance.risk import RiskScoringEngine
from agentic_exam_surveillance.models import BehaviorEvent


def test_smartwatch_verification_analog_vs_digital():
    detector = DetectionAgent({})

    # 1. Test case: Synthetic/uniform test frame should bypass and return True
    synthetic_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    synthetic_frame[:] = (30, 30, 30)
    is_valid, reason = detector.verify_smartwatch(synthetic_frame, (0, 0, 100, 100))
    assert is_valid is True
    assert "Bypassed" in reason

    # 2. Test case: Fitness band aspect ratio (extremely thin) should be rejected
    fitness_frame = np.zeros((150, 50, 3), dtype=np.uint8)
    fitness_frame[:] = (50, 100, 200) # colored, but wrong aspect ratio (height/width = 3.0)
    is_valid, reason = detector.verify_smartwatch(fitness_frame, (0, 0, 50, 150))
    assert is_valid is False
    assert "aspect" in reason.lower() or "fitness" in reason.lower()

    # 3. Test case: Analog Watch (low colorfulness, grey/metallic/white dial face) should be rejected
    analog_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Draw simple monochrome clock dial (white circle on dark background)
    analog_frame[:] = (20, 20, 20)
    cv2.circle(analog_frame, (50, 50), 45, (240, 240, 240), -1)
    # Draw hands (dark lines)
    cv2.line(analog_frame, (50, 50), (50, 20), (50, 50, 50), 2)
    cv2.line(analog_frame, (50, 50), (75, 50), (50, 50, 50), 2)
    is_valid, reason = detector.verify_smartwatch(analog_frame, (0, 0, 100, 100))
    assert is_valid is False
    assert "analog" in reason.lower()

    # 4. Test case: Simple Digital Watch (LCD, grey background, low colorfulness/contrast) should be rejected
    digital_lcd_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    digital_lcd_frame[:] = (120, 120, 120) # Flat LCD grey background
    # Draw simple digital segments
    cv2.putText(digital_lcd_frame, "12:00", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2)
    is_valid, reason = detector.verify_smartwatch(digital_lcd_frame, (0, 0, 100, 100))
    assert is_valid is False
    assert "digital" in reason.lower()

    # 5. Test case: Smartwatch (vibrant colorful screen, rectangular display, active UI) should be verified
    smartwatch_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    smartwatch_frame[:] = (10, 10, 10)
    # Draw colorful UI elements (e.g. bright blue/red/green icons or text)
    cv2.rectangle(smartwatch_frame, (10, 10), (90, 90), (0, 0, 0), -1) # display screen boundary
    cv2.circle(smartwatch_frame, (30, 30), 10, (255, 0, 0), -1) # Blue icon
    cv2.circle(smartwatch_frame, (70, 30), 10, (0, 255, 0), -1) # Green icon
    cv2.putText(smartwatch_frame, "10:30", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2) # Red time
    is_valid, reason = detector.verify_smartwatch(smartwatch_frame, (0, 0, 100, 100))
    assert is_valid is True
    assert "Smartwatch" in reason


def test_smartwatch_pipeline_integration():
    # Setup test config
    config = {
        "enable_detection": False,
        "alert_threshold": 40,
        "risk": {
            "threshold": 40
        },
        "session_id": "TEST_SMARTWATCH"
    }
    
    # Initialize pipeline
    from backend.api.websocket import init_webrtc_server
    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)
    
    # Mock Gemini agent
    from unittest.mock import MagicMock
    pipeline.gemini = MagicMock()
    async def mock_analyze_alert(*args, **kwargs):
        return {"ai_explanation": "Mocked Gemini AI alert description"}
    pipeline.gemini.analyze_alert = mock_analyze_alert

    # Mock SMTP sending
    import email_sender
    mock_send = MagicMock(return_value=True)
    email_sender.SurveillanceEmailSender.send_report = mock_send

    # Create dummy frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (240, 238, 235)
    
    # Create MockTrack simulating a student with a smart watch
    class MockTrack:
        def __init__(self, track_id, bbox, class_name):
            self.track_id = track_id
            self.bbox = bbox
            self.confidence = 0.95
            self.class_name = class_name
            self.objects_detected = []
            self.history = [((bbox[0]+bbox[2])//2, (bbox[1]+bbox[3])//2)]
            self.time_since_update = 0

    student_track = MockTrack(track_id=10, bbox=(100, 100, 200, 300), class_name="person")
    student_track.objects_detected.append({
        "class_name": "smart watch",
        "confidence": 0.95,
        "bbox": (110, 110, 140, 140),
        "area": 900
    })

    import time
    # Mock Gemini cache to return "smartwatch" to simulate a verified smartwatch
    pipeline.gemini_vision_cache[(10, "smart watch")] = ("smartwatch", 0.95, time.time(), (110, 110, 140, 140))

    # Run frame processing twice to trigger the 1-second stable detection timer
    t0 = time.time()
    
    # First frame (starts timer)
    import asyncio
    res1 = asyncio.run(pipeline.process_frame(
        frame=frame,
        camera_id="cam_01",
        yolo_results=[student_track],
        timestamp=t0
    ))
    
    # Second frame 1.5 seconds later (triggers alert)
    res2 = asyncio.run(pipeline.process_frame(
        frame=frame,
        camera_id="cam_01",
        yolo_results=[student_track],
        timestamp=t0 + 1.5
    ))

    # Verify that the alert was triggered
    alerts = res2.get("alerts", [])
    assert len(alerts) == 1
    alert = alerts[0]
    
    assert alert["risk_score"] >= 75.0
    assert alert["severity"] == "high" or alert["severity"] == "critical"
    assert "Smartwatch Detected" in alert["reason"]
    
    # Verify behavior list has smartwatch_detected
    behaviors = [b["behavior_type"] for b in alert["behaviors"]]
    assert "smartwatch_detected" in behaviors
