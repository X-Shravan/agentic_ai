from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import cv2
from ultralytics import YOLO


# --------------------------------------------------
# Detection Output
# --------------------------------------------------
@dataclass
class Detection:
    bbox: Tuple[int, int, int, int]
    confidence: float
    class_name: str

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)


# --------------------------------------------------
# Detection Agent (FIXED VERSION)
# --------------------------------------------------
class DetectionAgent:

    def __init__(self, config):

        print("🚀 YOLO model starting...")

        # ✅ USE OFFICIAL MODEL
        self.model = YOLO("yolov8n.pt")

        print("✅ YOLO model loaded successfully")

        # 🎯 COCO Classes (only detect these)
        self.valid_classes = {
            0: "person",           # Class 0 - person
            67: "cell phone",      # Class 67 - mobile phone
            73: "book"             # Class 73 - book (NOT cheating)
        }
        
        # 🔥 MOBILE VALIDATION THRESHOLDS (to avoid false positives from books/papers)
        self.MOBILE_CONF_MIN = 0.60          # Confidence threshold
        self.MOBILE_AREA_MIN = 7000          # Minimum bounding box area (pixels²)
        self.MOBILE_ASPECT_RATIO_MIN = 1.4  # Phones are taller (height/width ratio)
        self.MOBILE_ASPECT_RATIO_MAX = 2.5  # Max aspect ratio for phones
        
        # Debug counter
        self.detection_count = 0

    # --------------------------------------------------
    # 🔥 MOBILE PHONE VALIDATION (Geometry-based)
    # --------------------------------------------------
    def is_valid_mobile(self, bbox, confidence) -> Tuple[bool, str]:
        """
        Validate if detected object is actually a mobile phone.
        Uses geometry + confidence to avoid false positives from books/papers.
        
        Returns: (is_valid_phone, debug_info)
        """
        x1, y1, x2, y2 = bbox
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        aspect_ratio = height / width
        
        # Check all validation criteria
        conf_valid = confidence >= self.MOBILE_CONF_MIN
        area_valid = area >= self.MOBILE_AREA_MIN
        ratio_valid = self.MOBILE_ASPECT_RATIO_MIN <= aspect_ratio <= self.MOBILE_ASPECT_RATIO_MAX
        
        # Decision
        is_valid = conf_valid and area_valid and ratio_valid
        
        # Debug info
        debug = (f"Conf:{confidence:.2f}({conf_valid}) "
                f"Area:{area}({area_valid}) "
                f"Ratio:{aspect_ratio:.2f}({ratio_valid})")
        
        return is_valid, debug

    # --------------------------------------------------
    def detect(self, frame) -> List[Detection]:

        detections = []

        # 🔥 Lower confidence for better detection
        results = self.model(frame, conf=0.3, verbose=False)

        for r in results:

            if r.boxes is None:
                continue

            for box in r.boxes:

                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                # ❌ Ignore unwanted classes (anything not in valid_classes)
                if cls_id not in self.valid_classes:
                    continue

                class_name = self.valid_classes[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                bbox = (x1, y1, x2, y2)
                
                # 🔥 SPECIAL HANDLING FOR MOBILE PHONES
                if class_name == "cell phone":
                    # Validate using geometry (aspect ratio + area)
                    is_valid_phone, debug_info = self.is_valid_mobile(bbox, conf)
                    
                    if is_valid_phone:
                        # Valid phone - add to detections
                        det = Detection(
                            bbox=bbox,
                            confidence=conf,
                            class_name="cell phone"
                        )
                        detections.append(det)
                        print(f"✅ MOBILE PHONE: {debug_info}")
                    else:
                        # Likely book/paper - ignore
                        print(f"❌ REJECTED (book/paper): Class={cls_id} {debug_info}")
                        continue
                
                # ✅ BOOK HANDLING - Add to detections but marked as book (NOT cheating)
                elif class_name == "book":
                    det = Detection(
                        bbox=bbox,
                        confidence=conf,
                        class_name="book"
                    )
                    detections.append(det)
                    print(f"📚 BOOK DETECTED (normal): Conf={conf:.2f}")
                
                # ✅ PERSON - Always add
                else:  # person
                    det = Detection(
                        bbox=bbox,
                        confidence=conf,
                        class_name="person"
                    )
                    detections.append(det)

        self.detection_count += 1
        return detections

    def draw_detections(self, frame, detections: List[Detection]):

        out = frame.copy()

        for det in detections:

            x1, y1, x2, y2 = det.bbox

            # 🎨 Color coding for different object types
            if det.class_name == "person":
                color = (0, 255, 0)      # Green - person
                label = f"👤 {det.confidence:.2f}"
            elif det.class_name == "cell phone":
                color = (0, 0, 255)      # Red - mobile (cheating)
                label = f"📱 MOBILE {det.confidence:.2f}"
            elif det.class_name == "book":
                color = (0, 165, 255)    # Orange - book (normal)
                label = f"📚 BOOK {det.confidence:.2f}"
            else:
                color = (255, 255, 255) # White - unknown
                label = f"{det.class_name} {det.confidence:.2f}"

            # Draw bounding box
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

            # Draw label background
            text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(out, (x1, y1-25), (x1 + text_size[0] + 5, y1), color, -1)
            
            # Draw label text
            cv2.putText(
                out,
                label,
                (x1 + 2, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

        return out