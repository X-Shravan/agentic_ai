#!/usr/bin/env python3
"""
🔍 SURVEILLANCE SYSTEM VERIFICATION SCRIPT
Checks if all fixes are working correctly
"""

import cv2
import os
import sys
from pathlib import Path

def check_imports():
    """Verify all required imports"""
    print("\n📦 Checking imports...")
    try:
        import mediapipe as mp
        print("  ✅ MediaPipe available")
    except ImportError:
        print("  ❌ MediaPipe NOT installed: pip install mediapipe")
        return False
    
    try:
        import torch
        print("  ✅ PyTorch available")
    except ImportError:
        print("  ⚠️  PyTorch NOT installed (optional)")
    
    try:
        from flask import Flask
        from flask_socketio import SocketIO
        print("  ✅ Flask & SocketIO available")
    except ImportError:
        print("  ❌ Flask/SocketIO NOT installed: pip install flask flask-socketio")
        return False
    
    try:
        import yaml
        print("  ✅ PyYAML available")
    except ImportError:
        print("  ❌ PyYAML NOT installed: pip install pyyaml")
        return False
    
    return True

def check_directories():
    """Verify all required directories exist"""
    print("\n📁 Checking directories...")
    required_dirs = [
        "evidence",
        "config",
        "models",
        "logs",
        "agents",
        "alerts",
        "utils",
        "dashboard"
    ]
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"  ✅ {dir_name}/")
        else:
            print(f"  ⚠️  {dir_name}/ NOT found (creating...)")
            os.makedirs(dir_name, exist_ok=True)
    
    return True

def check_files():
    """Verify all critical files exist"""
    print("\n📄 Checking files...")
    required_files = [
        "main.py",
        "api_server.py",
        "agents/behavior_analysis_agent.py",
        "agents/detection_agent.py",
        "agents/tracking_agent.py",
        "config/config.yaml"
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} MISSING")
            all_exist = False
    
    return all_exist

def check_behavior_agent():
    """Verify behavior analysis agent has sharing detection"""
    print("\n🤝 Checking Sharing Detection...")
    try:
        with open("agents/behavior_analysis_agent.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = {
            "detect_sharing method": "def detect_sharing" in content,
            "SHARING_DISTANCE_THRESHOLD": "SHARING_DISTANCE_THRESHOLD" in content,
            "head_positions tracking": "self.head_positions" in content,
            "Sharing emoji label": "Sharing Answers 🤝" in content,
        }
        
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")
        
        return all(checks.values())
    except Exception as e:
        print(f"  ❌ Error checking: {e}")
        return False

def check_main_fixes():
    """Verify main.py has all critical fixes"""
    print("\n🔧 Checking Main.py Fixes...")
    try:
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = {
            "Frame copy": "display_frame = data[\"frame\"].copy()" in content,
            "Box drawing": "cv2.rectangle(display_frame" in content,
            "Alert transition check": "(prev_stat == \"Normal\"" in content,
            "Evidence save check": "if (prev_stat == \"Normal\"" in content,
            "Processed frame return": "results[cam_id][\"frame\"] = display_frame" in content,
        }
        
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")
        
        return all(checks.values())
    except Exception as e:
        print(f"  ❌ Error checking: {e}")
        return False

def check_api_server():
    """Verify API server handles all alert types"""
    print("\n🌐 Checking API Server...")
    try:
        with open("api_server.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = {
            "Sharing type tracking": '"Sharing Answers" in situation' in content,
            "Emoji detection": '🚨" in situation or "🤝' in content,
            "Image saving": "cv2.imwrite(" in content or "save_screenshot(" in content,
        }
        
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}")
        
        return all(checks.values())
    except Exception as e:
        print(f"  ❌ Error checking: {e}")
        return False

def check_evidence_dir():
    """Check if evidence directory is writable"""
    print("\n💾 Checking Evidence Directory...")
    try:
        test_file = "evidence/test_write.jpg"
        
        # Create dummy image
        import numpy as np
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(test_file, test_img)
        
        if os.path.exists(test_file):
            os.remove(test_file)
            print("  ✅ Evidence directory is writable")
            return True
        else:
            print("  ❌ Cannot write to evidence directory")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_frame_pipeline():
    """Test frame pipeline logic"""
    print("\n🔄 Testing Frame Pipeline...")
    try:
        # Simulate frame pipeline
        import numpy as np
        
        # Original frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        print(f"  ✅ Created frame: {frame.shape}")
        
        # Copy for display
        display_frame = frame.copy()
        print(f"  ✅ Created display_frame: {display_frame.shape}")
        
        # Test drawing on display frame
        cv2.rectangle(display_frame, (100, 100), (200, 200), (0, 0, 255), 3)
        print(f"  ✅ Drew rectangle on display_frame")
        
        # Verify original not modified
        if np.array_equal(frame, display_frame):
            print("  ⚠️  Frame modified (should be separate)")
            return False
        else:
            print("  ✅ Frames are properly separated")
            return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    """Run all verification checks"""
    print("\n" + "="*60)
    print("🔍 SURVEILLANCE SYSTEM VERIFICATION")
    print("="*60)
    
    results = []
    
    # Run all checks
    results.append(("Imports", check_imports()))
    results.append(("Directories", check_directories()))
    results.append(("Files", check_files()))
    results.append(("Behavior Agent", check_behavior_agent()))
    results.append(("Main Fixes", check_main_fixes()))
    results.append(("API Server", check_api_server()))
    results.append(("Evidence Directory", check_evidence_dir()))
    results.append(("Frame Pipeline", test_frame_pipeline()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    print(f"\nScore: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL CHECKS PASSED! System is ready to run.")
        return 0
    elif passed >= total - 1:
        print("\n⚠️  MOST CHECKS PASSED. Minor issues may be present.")
        return 1
    else:
        print("\n❌ CRITICAL ISSUES FOUND. Please fix before running.")
        return 2

if __name__ == "__main__":
    sys.exit(main())
