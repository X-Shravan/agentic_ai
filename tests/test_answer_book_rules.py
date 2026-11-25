import sys
import os
import numpy as np
import cv2
import pytest
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.detection_agent import DetectionAgent, Detection

def test_ruled_paper_detection_and_suppression():
    detector = DetectionAgent({})

    # 1. Test Case: Synthetic frame with horizontal lines representing ruled paper
    frame = np.zeros((400, 400, 3), dtype=np.uint8)
    frame[:] = (245, 245, 245) # white paper background
    # Draw horizontal ruled lines
    for y in range(40, 380, 30):
        cv2.line(frame, (20, y), (380, y), (180, 180, 180), 1)
    # Draw written text
    cv2.putText(frame, "Answer to Question 1", (30, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1)
    cv2.putText(frame, "The solution is calculated as follows...", (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1)

    # Verify that it is recognized as a book/paper
    is_valid, debug = detector.verify_answer_book(frame, (10, 10, 390, 390))
    assert is_valid is True
    assert "RuledLines" in debug

    # 2. Test Case: False mobile phone detection on horizontal lines
    # If a cell phone bbox is detected, but contains only the horizontal lines crop:
    false_phone_bbox = (50, 110, 150, 260) # width = 100, height = 150
    false_phone_crop = frame[110:260, 50:150]
    
    # Assert that is_just_paper_lines identifies it as just lines
    assert detector.is_just_paper_lines(false_phone_crop) is True

    # 3. Test Case: Real mobile phone crop (has vertical border and dark body)
    real_phone_crop = np.zeros((150, 100, 3), dtype=np.uint8)
    # Draw black cell phone body
    cv2.rectangle(real_phone_crop, (5, 5), (95, 145), (20, 20, 20), -1)
    # Draw screen
    cv2.rectangle(real_phone_crop, (10, 10), (90, 120), (50, 50, 50), -1)
    # Assert that is_just_paper_lines identifies it as NOT just paper lines
    assert detector.is_just_paper_lines(real_phone_crop) is False

    # 4. Test Case: post_process_detections verification
    # Setup list of mock detections:
    # A book, a false phone (on horizontal lines), a real phone (which does not match just lines), and an overlapping duplicate book.
    detections = [
        # Book 1
        Detection(bbox=(10, 10, 390, 390), confidence=0.85, class_name="book"),
        # Overlapping Duplicate Book 2 (should be suppressed by NMS)
        Detection(bbox=(15, 15, 385, 385), confidence=0.70, class_name="book"),
        # False phone (its bbox corresponds to horizontal lines crop in the frame)
        Detection(bbox=(50, 110, 150, 260), confidence=0.75, class_name="cell phone"),
        # Real phone (needs to be kept since its crop will be real_phone_crop)
        # To simulate this, we'll draw the real phone on the frame at its bbox coordinates
        Detection(bbox=(250, 200, 350, 350), confidence=0.80, class_name="cell phone"),
    ]

    # Draw the real phone on the frame at (250, 200, 350, 350)
    frame[200:350, 250:350] = real_phone_crop

    processed = detector.post_process_detections(frame, detections)

    # We expect:
    # - Book 1 (kept)
    # - Overlapping Book 2 (suppressed)
    # - False phone (suppressed)
    # - Real phone (kept)
    classes = [d.class_name for d in processed]
    assert "book" in classes
    assert len([c for c in classes if c == "book"]) == 1 # only 1 book kept (NMS succeeded)
    assert len([c for c in classes if c == "cell phone"]) == 1 # only the real phone kept (false phone suppressed)
    
    # Check that the kept phone is the real one at (250, 200)
    kept_phone = [d for d in processed if d.class_name == "cell phone"][0]
    assert kept_phone.bbox == (250, 200, 350, 350)
