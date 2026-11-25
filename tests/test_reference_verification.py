import sys
import os
import numpy as np
import cv2
import pytest
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.detection_agent import Detection
from backend.cv.reference_verifier import ReferenceVerifier
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline
from backend.api.websocket import init_webrtc_server

class MockDetection:
    def __init__(self, bbox, confidence, class_name):
        self.bbox = bbox
        self.confidence = confidence
        self.class_name = class_name
        self.objects_detected = []
        self.track_id = 42

def test_reference_verifier_watch_rules():
    config = {
        "reference_verify": {
            "enabled": True,
            "smartwatch_threshold": 0.20,
            "analog_watch_threshold": 0.55,
            "answer_sheet_threshold": 0.35,
            "cache_duration": 10.0
        }
    }
    verifier = ReferenceVerifier(config)
    
    # Check that thresholds are correctly initialized
    assert verifier.sw_threshold == 0.20
    assert verifier.aw_threshold == 0.55
    assert verifier.ans_threshold == 0.35
    assert verifier.cache_duration == 10.0

    # Test watch decision logic (conceptual rules check)
    # smartwatch_score >= sw_threshold and smartwatch_score > analog_watch_score -> smartwatch
    # analog_watch_score >= aw_threshold and analog_watch_score > smartwatch_score -> analog_watch
    # Otherwise -> unknown

    # 1. Strong smartwatch match
    class MockedVerifier(ReferenceVerifier):
        def evaluate_similarity(self, crop, category):
            if category == "smartwatch":
                return self.mock_sw
            elif category == "analog_watch":
                return self.mock_aw
            elif category == "answer_sheet":
                return self.mock_ans
            return 0.0
            
    mock_verifier = MockedVerifier(config)
    dummy_crop = np.zeros((100, 100, 3), dtype=np.uint8)

    # Case A: smartwatch_score >= 0.20 and smartwatch_score > analog_watch_score
    mock_verifier.mock_sw = 0.30
    mock_verifier.mock_aw = 0.25
    res, score = mock_verifier.verify(dummy_crop, "smart watch")
    assert res == "smartwatch"
    assert score == 0.30

    # Case B: analog_watch_score >= 0.55 and analog_watch_score > smartwatch_score
    mock_verifier.mock_sw = 0.50
    mock_verifier.mock_aw = 0.60
    res, score = mock_verifier.verify(dummy_crop, "smart watch")
    assert res == "analog_watch"
    assert score == 0.60

    # Case C: Both below thresholds, or equal, or smartwatch score <= analog watch score but analog below threshold
    # e.g., sw = 0.15, aw = 0.10 -> both below thresholds -> unknown
    mock_verifier.mock_sw = 0.15
    mock_verifier.mock_aw = 0.10
    res, score = mock_verifier.verify(dummy_crop, "smart watch")
    assert res == "unknown"

    # e.g., sw = 0.25, aw = 0.30 -> aw is higher but aw < aw_threshold (0.55). sw is not > aw. -> unknown
    mock_verifier.mock_sw = 0.25
    mock_verifier.mock_aw = 0.30
    res, score = mock_verifier.verify(dummy_crop, "smart watch")
    assert res == "unknown"


def test_mobile_isolation():
    # TEST 1 & 7: Verify that mobile phone detection is NOT passed to the reference verifier and remains unchanged.
    config = {
        "enable_detection": False,
        "reference_verify": {
            "enabled": True,
            "smartwatch_threshold": 0.20,
            "analog_watch_threshold": 0.55,
            "answer_sheet_threshold": 0.35
        }
    }
    
    # Initialize mock WebRTC server and pipeline
    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)
    
    # Create person track with objects_detected containing cell phone
    class MockTrack:
        def __init__(self, track_id, bbox, class_name):
            self.track_id = track_id
            self.bbox = bbox
            self.confidence = 0.90
            self.class_name = class_name
            self.objects_detected = []
            self.history = [((bbox[0]+bbox[2])//2, (bbox[1]+bbox[3])//2)]
            self.time_since_update = 0

    student_track = MockTrack(track_id=12, bbox=(100, 100, 200, 300), class_name="person")
    student_track.objects_detected.append({
        "class_name": "cell phone",
        "confidence": 0.95,
        "bbox": (110, 110, 130, 180),
        "area": 1400
    })

    # Clear pipeline verification cache
    pipeline.verification_cache.clear()

    # Create dummy frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Process frame
    import asyncio
    res = asyncio.run(pipeline.process_frame(
        frame=frame,
        camera_id="cam_test",
        yolo_results=[student_track],
        timestamp=1.0,
        clean_frame=frame
    ))

    # Verify that the cell phone object is NOT verified (no cache entry created for cell phone, class remains cell phone)
    cache_keys = list(pipeline.verification_cache.keys())
    for k in cache_keys:
        assert "cell_phone" not in k[1] and "mobile" not in k[1]
        
    # Check that class name remained "cell phone"
    assert student_track.objects_detected[0]["class_name"] == "cell phone"
