#!/usr/bin/env python3
"""
Test script to verify YOLO detection improvements:
- Mobile phone detection with geometric validation
- Book handled as normal object
- False positive reduction
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.detection_agent import DetectionAgent
import yaml

# Load config
config_path = Path("config/config.yaml")
config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}

print("=" * 70)
print("🧪 YOLO DETECTION IMPROVEMENTS TEST")
print("=" * 70)

# Initialize detection agent
print("\n📊 Initializing Detection Agent...")
detector = DetectionAgent(config)

print("\n✅ Valid Classes:")
for cls_id, cls_name in detector.valid_classes.items():
    print(f"   {cls_id}: {cls_name}")

print("\n🔥 Mobile Validation Thresholds:")
print(f"   Confidence: ≥ {detector.MOBILE_CONF_MIN}")
print(f"   Area: ≥ {detector.MOBILE_AREA_MIN} px²")
print(f"   Aspect Ratio: {detector.MOBILE_ASPECT_RATIO_MIN} ≤ ratio ≤ {detector.MOBILE_ASPECT_RATIO_MAX}")

# Test geometric validation
print("\n" + "=" * 70)
print("TEST 1: Geometric Validation")
print("=" * 70)

test_cases = [
    {
        "name": "✅ Valid Phone (typical: 100x200, ratio 2.0)",
        "bbox": (100, 100, 200, 300),  # width=100, height=200, area=20000, ratio=2.0
        "confidence": 0.85
    },
    {
        "name": "✅ Valid Phone (tall: 80x160, ratio 2.0)",
        "bbox": (100, 100, 180, 260),  # width=80, height=160, area=12800, ratio=2.0
        "confidence": 0.85
    },
    {
        "name": "✅ Valid Phone (min: 80x112, ratio 1.4)",
        "bbox": (100, 100, 180, 212),  # width=80, height=112, area=8960, ratio=1.4
        "confidence": 0.85
    },
    {
        "name": "❌ Book (wide, low ratio: 200x100, ratio 0.5)",
        "bbox": (100, 100, 300, 200),  # width=200, height=100, area=20000, ratio=0.5
        "confidence": 0.75
    },
    {
        "name": "❌ Book/Paper (wide: 180x100, ratio 0.56)",
        "bbox": (100, 100, 280, 200),  # width=180, height=100, area=18000, ratio=0.56
        "confidence": 0.72
    },
    {
        "name": "❌ Low confidence (conf 0.45, rejected)",
        "bbox": (100, 100, 180, 260),  # width=80, height=160, area=12800, ratio=2.0 (good geometry, bad conf)
        "confidence": 0.45
    },
    {
        "name": "❌ Too small area (50x100, area 5000)",
        "bbox": (100, 100, 150, 200),  # width=50, height=100, area=5000, ratio=2.0
        "confidence": 0.80
    },
]

for test in test_cases:
    is_valid, debug = detector.is_valid_mobile(test["bbox"], test["confidence"])
    status = "✅ PASS" if is_valid else "❌ FAIL"
    print(f"\n{test['name']}")
    print(f"   Result: {status}")
    print(f"   Details: {debug}")

# Test class filtering
print("\n" + "=" * 70)
print("TEST 2: Class Filtering")
print("=" * 70)

classes_to_test = [
    (0, "person", True),
    (1, "bicycle", False),
    (67, "cell phone", True),
    (73, "book", True),
    (75, "keyboard", False),
]

print("\nCOCO Class Validation:")
for cls_id, cls_name, should_pass in classes_to_test:
    is_valid = cls_id in detector.valid_classes
    status = "✅" if is_valid == should_pass else "❌"
    print(f"   {status} Class {cls_id:2d} ({cls_name:15s}): {'ACCEPT' if is_valid else 'REJECT'}")

# Display configuration summary
print("\n" + "=" * 70)
print("CONFIGURATION SUMMARY")
print("=" * 70)

summary = f"""
Detection Pipeline:
  1. YOLO inference (conf ≥ 0.3)
  2. Filter by valid classes (0, 67, 73)
  3. For mobiles: Apply geometric validation
  4. For books: Always add (normal)
  5. For persons: Always add

Mobile Phone Validation:
  - Confidence ≥ {detector.MOBILE_CONF_MIN}
  - Area ≥ {detector.MOBILE_AREA_MIN} pixels²
  - Aspect Ratio: {detector.MOBILE_ASPECT_RATIO_MIN}-{detector.MOBILE_ASPECT_RATIO_MAX}
  
Aspect Ratio Examples:
  - Phone (height 280, width 140): ratio = 2.0 ✅
  - Book (height 150, width 250): ratio = 0.6 ❌
  - Paper (height 100, width 200): ratio = 0.5 ❌

Expected Results:
  ✅ Mobile → Status: "Using Mobile 🚨"
  ✅ Book → Status: "normal"
  ✅ Paper → Rejected (aspect ratio fail)
  ✅ Person → Status: Normal until behavior detected
"""

print(summary)

print("\n" + "=" * 70)
print("✅ TEST COMPLETE")
print("=" * 70)
print("\nNext Steps:")
print("  1. Run: python main.py --demo")
print("  2. Verify no false alerts on books/papers")
print("  3. Check mobile phones still detected")
print("  4. Monitor debug output for class filtering")
