import os
import cv2
import time


class EvidenceCapture:

    def __init__(self, save_dir="evidence"):

        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

        print("[INFO] Evidence capture system initialized")

    # ------------------------------------------------
    # ✅ IMPROVED EVIDENCE CAPTURE
    # ------------------------------------------------
    def save_screenshot(self, frame, track_id, score, events):
        """
        Save screenshot with proper naming and metadata.
        
        Naming format: evidence/ID_1_mobile_20260417_101530.jpg
        """

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Extract situation from events
        situation = "normal"
        if events and len(events) > 0:
            event_text = str(events[0]).lower()
            if "mobile" in event_text or "🚨" in event_text:
                situation = "mobile"
            elif "copy" in event_text:
                situation = "copy"
            elif "looking" in event_text or "👀" in event_text:
                situation = "looking"
            elif "leaning" in event_text or "↘️" in event_text:
                situation = "leaning"

        # Format: ID_1_mobile_20260417_101530.jpg
        filename = f"{self.save_dir}/ID_{track_id}_{situation}_{timestamp}.jpg"

        # 🔥 Draw metadata on image
        img = frame.copy()
        h, w = img.shape[:2]

        # Background overlay
        cv2.rectangle(img, (10, 10), (w - 10, 110), (0, 0, 0), -1)
        cv2.rectangle(img, (10, 10), (w - 10, 110), (0, 255, 0), 2)

        # Text info
        cv2.putText(
            img,
            f"ALERT: Student ID {track_id}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

        event_text = events[0] if events else "Unknown"
        cv2.putText(
            img,
            f"Behavior: {event_text}",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        cv2.putText(
            img,
            f"Score: {int(score * 100)}% | Time: {timestamp}",
            (20, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )

        cv2.imwrite(filename, img)

        print(f"📸 EVIDENCE SAVED: {filename}")