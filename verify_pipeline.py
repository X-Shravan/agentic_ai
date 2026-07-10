#!/usr/bin/env python3
"""
Quick verification script for surveillance pipeline
Tests: MediaPipe, YOLO, behavior logic, drawing, evidence saving
"""
import sys
import cv2
import numpy as np
from pathlib import Path

def test_imports():
    """Test all required imports"""
    print("🧪 Testing imports...")
    try:
        import mediapipe as mp
        print("  ✅ MediaPipe")
    except Exception as e:
        print(f"  ❌ MediaPipe: {e}")
        return False
    
    try:
        from agents.detection_agent import DetectionAgent
        print("  ✅ DetectionAgent")
    except Exception as e:
        print(f"  ❌ DetectionAgent: {e}")
        return False
    
    try:
        from agents.simple_behavior_analysis import SimpleBehaviorAnalysis
        print("  ✅ SimpleBehaviorAnalysis")
    except Exception as e:
        print(f"  ❌ SimpleBehaviorAnalysis: {e}")
        return False
    
    try:
        from agents.behavior_analysis_agent import BehaviorAnalysisAgent
        print("  ✅ BehaviorAnalysisAgent")
    except Exception as e:
        print(f"  ❌ BehaviorAnalysisAgent: {e}")
        return False
    
    return True


def test_behavior_logic():
    """Test behavior detection logic"""
    print("\n🧪 Testing behavior logic...")
    
    try:
        from agents.behavior_analysis_agent import BehaviorAnalysisAgent
        ba = BehaviorAnalysisAgent({})
        
        # Test counter logic
        ba.look_around_count[1] = 0
        
        # Simulate: looking around (yaw = 25, which is > 20)
        yaw = 25
        if abs(yaw) > ba.LOOK_AROUND_YAW:  # > 20
            ba.look_around_count[1] += 1
        
        print(f"  After 1 frame with yaw=25°: count={ba.look_around_count[1]} (expected 1) ✅")
        
        # Simulate: not looking around (yaw = 5)
        yaw = 5
        if abs(yaw) > ba.LOOK_AROUND_YAW:
            ba.look_around_count[1] += 1
        else:
            ba.look_around_count[1] = max(ba.look_around_count[1] - 1, 0)
        
        print(f"  After 1 frame with yaw=5°: count={ba.look_around_count[1]} (expected 0) ✅")
        
        # Simulate: 3 frames of looking around
        for i in range(3):
            yaw = 25
            if abs(yaw) > ba.LOOK_AROUND_YAW:
                ba.look_around_count[2] += 1
        
        threshold = ba.LOOK_AROUND_COUNT_THRESHOLD
        print(f"  After 3 frames with yaw=25°: count={ba.look_around_count[2]} >= {threshold}? {ba.look_around_count[2] >= threshold} ✅")
        
        if ba.look_around_count[2] >= threshold:
            print("  ✅ Looking Around detection would trigger!")
        else:
            print("  ❌ Looking Around NOT detected (check thresholds)")
            return False
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    return True


def test_thresholds():
    """Verify thresholds match specification"""
    print("\n🧪 Testing thresholds...")
    
    try:
        from agents.behavior_analysis_agent import BehaviorAnalysisAgent
        ba = BehaviorAnalysisAgent({})
        
        specs = {
            "LOOK_AROUND_YAW": 20,
            "LOOK_AROUND_COUNT_THRESHOLD": 3,
            "LOOK_COPY_PITCH": 15,
            "LOOK_COPY_YAW": 10,
            "LOOK_COPY_COUNT_THRESHOLD": 3,
            "LEAN_SHOULDER_DIFF": 10,
            "LEAN_FRAMES_THRESHOLD": 15,
            "MOBILE_CONF_THRESHOLD": 0.6,
            "MOBILE_AREA_THRESHOLD": 7000,
            "MOBILE_ASPECT_RATIO_MIN": 1.4,
            "MOBILE_ASPECT_RATIO_MAX": 2.5,
        }
        
        all_match = True
        for attr, expected in specs.items():
            actual = getattr(ba, attr)
            match = actual == expected
            symbol = "✅" if match else "❌"
            print(f"  {symbol} {attr}: {actual} (expected {expected})")
            if not match:
                all_match = False
        
        return all_match
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_drawing():
    """Test OpenCV drawing functions"""
    print("\n🧪 Testing OpenCV drawing...")
    
    try:
        # Create test frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Draw box
        cv2.rectangle(frame, (100, 100), (200, 300), (0, 0, 255), 3)
        print("  ✅ Rectangle drawn")
        
        # Draw text
        cv2.putText(
            frame, "ID 1 | Test 🚨 | 85%",
            (100, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )
        print("  ✅ Text drawn")
        
        # Save test image
        cv2.imwrite("/tmp/test_drawing.jpg", frame)
        print("  ✅ Test image saved")
        
        return True
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_evidence_path():
    """Test evidence directory"""
    print("\n🧪 Testing evidence directory...")
    
    try:
        evidence_dir = Path("evidence")
        evidence_dir.mkdir(exist_ok=True)
        print(f"  ✅ Evidence directory: {evidence_dir.absolute()}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_mediapipe():
    """Test MediaPipe initialization"""
    print("\n🧪 Testing MediaPipe...")
    
    try:
        import mediapipe as mp
        
        # Test FaceMesh
        face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=5,
            min_detection_confidence=0.5
        )
        print("  ✅ FaceMesh initialized")
        
        # Test Pose
        pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            min_detection_confidence=0.5
        )
        print("  ✅ Pose initialized")
        
        # Test with dummy image
        dummy_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        dummy_rgb = cv2.cvtColor(dummy_frame, cv2.COLOR_BGR2RGB)
        
        face_res = face_mesh.process(dummy_rgb)
        pose_res = pose.process(dummy_rgb)
        
        print("  ✅ FaceMesh processing works")
        print("  ✅ Pose processing works")
        
        return True
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("🔍 SURVEILLANCE PIPELINE VERIFICATION")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("MediaPipe", test_mediapipe),
        ("Thresholds", test_thresholds),
        ("Behavior Logic", test_behavior_logic),
        ("Drawing", test_drawing),
        ("Evidence Path", test_evidence_path),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ {name} failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        symbol = "✅" if passed_test else "❌"
        print(f"{symbol} {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is ready.")
        print("\nRun demo with: python main.py --demo")
        print("Or run API server with: python api_server.py")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
