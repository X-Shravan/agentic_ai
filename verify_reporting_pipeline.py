#!/usr/bin/env python3
import sys
import os
import shutil
import numpy as np
import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to python path
sys.path.insert(0, str(Path(__file__).parent))

# Mock SMTP sending in email_sender to prevent real network calls during verification
import email_sender
mock_send = MagicMock(side_effect=lambda *args, **kwargs: (print("MOCK SMTP: send_report called successfully!"), True)[1])
email_sender.SurveillanceEmailSender.send_report = mock_send

from pipeline.integrated_pipeline import IntegratedSurveillancePipeline
from backend.database.store import store

class MockTrack:
    def __init__(self, track_id, bbox, class_name, confidence=0.9):
        self.track_id = track_id
        self.bbox = bbox
        self.confidence = confidence
        self.class_name = class_name
        self.objects_detected = []
        self.history = [((bbox[0]+bbox[2])//2, (bbox[1]+bbox[3])//2)]
        self.time_since_update = 0

async def main():
    print("=" * 80)
    print("INTEGRATED EVIDENCE, REPORTING AND EMAIL PIPELINE VERIFICATION")
    print("=" * 80)

    # Ensure storage folder exists without deleting it
    storage_path = Path("storage")
    storage_path.mkdir(parents=True, exist_ok=True)

    # 2. Config setup
    config = {
        "enable_detection": False,
        "alert_threshold": 20,
        "risk": {
            "threshold": 20
        },
        "session_id": "TEST_SESSION"
    }

    # Initialize WebRTC server mock context
    from backend.api.websocket import init_webrtc_server
    server = init_webrtc_server(config)
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)

    # Mock Gemini agent inside pipeline for fast testing
    pipeline.gemini = MagicMock()
    async def mock_analyze_alert(*args, **kwargs):
        return {"ai_explanation": "Mocked Gemini AI alert description"}
    pipeline.gemini.analyze_alert = mock_analyze_alert

    # 3. Create simulated live camera frame programmatically (no dataset image file dependencies)
    print("\nCreating mock frame history...")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Draw soft gray background representing exam room wall
    frame[:] = (240, 238, 235)
    # Draw classroom board
    cv2.rectangle(frame, (40, 20), (600, 120), (45, 60, 40), -1)
    cv2.rectangle(frame, (40, 20), (600, 120), (110, 140, 110), 3)
    cv2.putText(frame, "Simulated Exam Room - Live Feed", (60, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "Subject: AI Surveillance Test Session", (60, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (190, 210, 190), 1)
    
    # Draw simulated desk
    cv2.rectangle(frame, (100, 280), (540, 420), (170, 200, 220), -1)
    cv2.rectangle(frame, (100, 280), (540, 420), (100, 120, 140), 2)
    # Draw simulated student
    cv2.circle(frame, (320, 220), 40, (140, 90, 70), -1)
    cv2.rectangle(frame, (260, 260), (380, 380), (110, 75, 55), -1)
    
    pipeline.frame_history = {
        "cam_01": [frame.copy() for _ in range(30)]
    }

    # 4. Trigger alert scenario
    print("\nTriggering suspicious alert (student + cell phone)...")
    student_track = MockTrack(track_id=42, bbox=(100, 100, 200, 300), class_name="person")
    student_track.objects_detected.append({
        "class_name": "cell phone",
        "confidence": 0.95,
        "bbox": (110, 110, 130, 160),
        "area": 1000
    })

    # First call to start timer
    t0 = time.time()
    print("Sending first frame to start phone detection timer...")
    await pipeline.process_frame(
        frame=frame,
        camera_id="cam_01",
        yolo_results=[student_track],
        timestamp=t0,
        clean_frame=frame
    )

    # Second call 1.1s later to trigger the alert
    t1 = t0 + 1.1
    print("Sending second frame 1.1s later to trigger immediate stable alert...")
    results = await pipeline.process_frame(
        frame=frame,
        camera_id="cam_01",
        yolo_results=[student_track],
        timestamp=t1,
        clean_frame=frame
    )

    print("\nVerifying local storage directories...")
    # Wait briefly for disk writes and background threads
    await asyncio.sleep(2)

    # Verify directory YYYY-MM-DD/camera/student/
    date_str = datetime.now().strftime("%Y-%m-%d")
    evidence_dir = Path(f"storage/evidence/{date_str}/cam_01/cam_01_42")
    
    print(f"Checking path: {evidence_dir.absolute()}")
    assert evidence_dir.exists(), "Error: Evidence directory was not created!"
    print("Evidence directory exists.")

    # List files
    files = list(evidence_dir.iterdir())
    print(f"Files saved: {[f.name for f in files]}")
    
    original_exists = any("original.jpg" in f.name or ("EV_" in f.name and "original" in f.name) for f in files)
    annotated_exists = any("annotated.jpg" in f.name or ("EV_" in f.name and "original" not in f.name and "clip" not in f.name and "metadata" not in f.name and f.name.endswith(".jpg")) for f in files)
    video_exists = any("clip.mp4" in f.name or ("EV_" in f.name and "clip" in f.name) for f in files)
    metadata_exists = any("metadata.json" in f.name or ("EV_" in f.name and "metadata" in f.name) for f in files)

    assert original_exists, "Error: Original frame was not saved!"
    assert annotated_exists, "Error: Evidence frame was not saved!"
    assert video_exists, "Error: Video clip was not saved!"
    assert metadata_exists, "Error: Metadata JSON was not saved!"
    print("All expected files (original, annotated, mp4 clip, metadata json) exist inside student directory.")

    # 5. Verify database store metadata
    print("\nChecking database store metadata...")
    evidence_records = store.list("evidence")
    print(f"Evidence records in store: {len(evidence_records)}")
    assert len(evidence_records) > 0, "Error: No evidence record stored in database!"
    
    rec = evidence_records[0]
    required_keys = ["evidence_id", "incident_id", "alert_id", "student_id", "student", "tracking_id", "camera_id", "timestamp", "behaviour", "event", "confidence", "risk_score", "evidence_image_path", "image_path", "evidence_video_path", "gemini_summary", "reviewer_status", "session_id", "annotated_image_path", "original_image_path"]
    for k in required_keys:
        assert k in rec, f"Error: Required key '{k}' is missing from database record!"
    
    # Assert alert_id links correctly
    alerts = store.list("alerts")
    assert len(alerts) > 0, "Error: No alert stored in database!"
    assert rec["alert_id"] == alerts[0]["alert_id"], f"Error: Evidence alert_id '{rec['alert_id']}' does not match Alert ID '{alerts[0]['alert_id']}'!"
    print("Database store contains all required metadata fields successfully, with valid alert_id mapping.")

    # 6. Verify PDF report generation
    print("\nChecking PDF report generation...")
    reports = store.list("reports")
    print(f"Reports generated: {len(reports)}")
    assert len(reports) > 0, "Error: PDF report record was not added to the store!"
    
    report_path = Path(reports[0]["pdf_path"])
    print(f"PDF Path: {report_path}")
    assert report_path.exists(), f"Error: PDF file does not exist at {report_path}"
    print("PDF report file generated successfully.")

    # 7. Verify background email trigger
    print("\nChecking background email delivery task...")
    assert mock_send.call_count > 0, "Error: SurveillanceEmailSender.send_report was not called!"
    print("Background email delivery was triggered successfully.")

    # Check database report status updated
    assert reports[0]["email_status"] in ["sent", "sending"], f"Error: Report email_status is not updated (current: {reports[0]['email_status']})"
    print("Database report email status updated successfully.")

    print("\n" + "=" * 80)
    print("ALL SCENARIOS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    import cv2
    from datetime import datetime
    asyncio.run(main())
