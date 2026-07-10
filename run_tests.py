#!/usr/bin/env python
"""
Quick Testing Script - Run all tests in sequence
Usage: python run_tests.py
"""

import sys
import os
import time
import subprocess
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️ {text}{RESET}")

def test_environment():
    """Test 1: Check environment"""
    print_header("PHASE 1: Environment Check")
    
    tests_passed = 0
    tests_failed = 0
    
    # Check Python version
    print(f"Python version: {sys.version}")
    if sys.version_info >= (3, 9):
        print_success("Python 3.9+ found")
        tests_passed += 1
    else:
        print_error(f"Python 3.9+ required (found {sys.version_info.major}.{sys.version_info.minor})")
        tests_failed += 1
    
    # Check required files
    required_files = [
        "config/config.yaml",
        "requirements-enterprise.txt",
        "api_server.py",
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print_success(f"File found: {file}")
            tests_passed += 1
        else:
            print_error(f"File missing: {file}")
            tests_failed += 1
    
    # Check required directories
    required_dirs = [
        "server",
        "analysis",
        "database",
        "pipeline",
    ]
    
    for dir in required_dirs:
        if os.path.isdir(dir):
            print_success(f"Directory found: {dir}")
            tests_passed += 1
        else:
            print_error(f"Directory missing: {dir}")
            tests_failed += 1
    
    return tests_passed, tests_failed

def test_imports():
    """Test 2: Check Python imports"""
    print_header("PHASE 2: Python Imports Check")
    
    tests_passed = 0
    tests_failed = 0
    
    required_packages = [
        ("cv2", "opencv-python"),
        ("flask", "Flask"),
        ("flask_socketio", "Flask-SocketIO"),
        ("numpy", "NumPy"),
        ("torch", "PyTorch"),
        ("ultralytics", "Ultralytics"),
        ("sqlalchemy", "SQLAlchemy"),
        ("fastapi", "FastAPI"),
        ("google.generativeai", "Google Generative AI"),
    ]
    
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print_success(f"{package_name} imported")
            tests_passed += 1
        except ImportError:
            print_error(f"{package_name} not installed")
            tests_failed += 1
    
    return tests_passed, tests_failed

def test_skeleton_analyzer():
    """Test 3: Skeleton analyzer"""
    print_header("PHASE 3: Skeleton Analyzer Test")
    
    try:
        sys.path.insert(0, '.')
        from analysis.skeleton_analyzer import SkeletonAnalyzer
        import numpy as np
        
        print_info("Initializing Skeleton Analyzer...")
        analyzer = SkeletonAnalyzer()
        print_success("Skeleton analyzer initialized")
        
        # Create dummy landmarks
        dummy_landmarks = np.random.rand(33, 3).tolist()
        
        print_info("Analyzing dummy pose...")
        result = analyzer.analyze(landmarks=dummy_landmarks)
        print_success(f"Analysis complete - Anomaly score: {result.anomaly_score}")
        
        return 1, 0
    except Exception as e:
        print_error(f"Skeleton analyzer test failed: {str(e)}")
        return 0, 1

def test_fusion_engine():
    """Test 4: Fusion engine"""
    print_header("PHASE 4: Multi-Modal Fusion Test")
    
    try:
        sys.path.insert(0, '.')
        from analysis.multimodal_fusion import MultiModalFusionEngine, FusionInput
        
        print_info("Initializing Fusion Engine...")
        engine = MultiModalFusionEngine()
        print_success("Fusion engine initialized")
        
        # Create dummy input
        fusion_input = FusionInput(
            gaze_score=0.8,
            pose_score=0.6,
            phone_score=0.9,
            leaning_score=0.4,
            movement_score=0.3,
            timestamp=1234567890
        )
        
        print_info("Running fusion...")
        result = engine.fuse(fusion_input)
        print_success(f"Fusion complete - Risk Score: {result.risk_score}, Level: {result.risk_level}")
        
        return 1, 0
    except Exception as e:
        print_error(f"Fusion engine test failed: {str(e)}")
        return 0, 1

def test_fastapi():
    """Test 5: FastAPI server"""
    print_header("PHASE 5: FastAPI Server Test")
    
    try:
        sys.path.insert(0, '.')
        from server.api_fastapi import app
        from fastapi.testclient import TestClient
        
        print_info("Creating test client...")
        client = TestClient(app)
        
        print_info("Testing /health endpoint...")
        response = client.get("/health")
        if response.status_code == 200:
            print_success("Health endpoint: OK")
        else:
            print_error(f"Health endpoint: Failed ({response.status_code})")
            return 0, 1
        
        return 1, 0
    except Exception as e:
        print_error(f"FastAPI test failed: {str(e)}")
        return 0, 1

def test_database():
    """Test 6: Database models"""
    print_header("PHASE 6: Database Models Test")
    
    try:
        sys.path.insert(0, '.')
        from database.models import Student, Alert, RiskScore
        from datetime import datetime
        
        print_info("Creating Student model...")
        student = Student(
            student_id="STU_001",
            name="Test Student",
            roll_number="001",
            camera_id="camera_1",
            seat_x=100,
            seat_y=200
        )
        print_success("Student model created")
        
        print_info("Creating Alert model...")
        alert = Alert(
            student_id="STU_001",
            severity="HIGH",
            behaviors="phone_usage",
            risk_score=85.5,
            timestamp=datetime.now()
        )
        print_success("Alert model created")
        
        print_info("Creating RiskScore model...")
        risk = RiskScore(
            student_id="STU_001",
            score=85,
            risk_level="HIGH",
            timestamp=datetime.now()
        )
        print_success("RiskScore model created")
        
        return 1, 0
    except Exception as e:
        print_error(f"Database models test failed: {str(e)}")
        return 0, 1

def test_webrtc():
    """Test 7: WebRTC server"""
    print_header("PHASE 7: WebRTC Server Test")
    
    try:
        sys.path.insert(0, '.')
        from server.webrtc_server import WebRTCServer
        import cv2
        import numpy as np
        
        print_info("Initializing WebRTC server...")
        server = WebRTCServer(width=640, height=480, fps=30)
        print_success("WebRTC server initialized")
        
        print_info("Pushing dummy frame...")
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        server.push_frame(frame)
        print_success("Frame pushed to buffer")
        
        print_info("Getting camera status...")
        status = server.get_camera_status()
        print_success("Camera status retrieved")
        
        return 1, 0
    except Exception as e:
        print_error(f"WebRTC test failed: {str(e)}")
        return 0, 1

def print_summary(total_passed, total_failed):
    """Print test summary"""
    print_header("TEST SUMMARY")
    
    total = total_passed + total_failed
    percentage = (total_passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print_success(f"Passed: {total_passed}")
    print_error(f"Failed: {total_failed}")
    print(f"Success Rate: {percentage:.1f}%\n")
    
    if total_failed == 0:
        print(f"{GREEN}{BOLD}🎉 ALL TESTS PASSED! System is ready for deployment.{RESET}")
        return True
    elif total_failed <= 2:
        print(f"{YELLOW}{BOLD}⚠️  Some tests failed. Review errors above and retry.{RESET}")
        return False
    else:
        print(f"{RED}{BOLD}❌ Multiple tests failed. Check installation and configuration.{RESET}")
        return False

def main():
    print(f"\n{BOLD}{BLUE}🧪 Enterprise Surveillance System - Quick Test Suite{RESET}")
    print(f"{BLUE}Testing all components...\n{RESET}")
    
    total_passed = 0
    total_failed = 0
    
    # Run all tests
    tests = [
        ("Environment", test_environment),
        ("Imports", test_imports),
        ("Skeleton Analyzer", test_skeleton_analyzer),
        ("Fusion Engine", test_fusion_engine),
        ("FastAPI Server", test_fastapi),
        ("Database Models", test_database),
        ("WebRTC Server", test_webrtc),
    ]
    
    for test_name, test_func in tests:
        try:
            passed, failed = test_func()
            total_passed += passed
            total_failed += failed
        except Exception as e:
            print_error(f"Unexpected error in {test_name}: {str(e)}")
            total_failed += 1
    
    # Print summary
    success = print_summary(total_passed, total_failed)
    
    print("\n" + "="*70)
    print("📚 Next Steps:")
    print("="*70)
    print("1. Review TESTING_GUIDE.md for comprehensive testing instructions")
    print("2. Start API server: python api_server.py")
    print("3. Test endpoints in browser: http://localhost:5000/api/health")
    print("4. Connect cameras via config/config.yaml")
    print("5. Monitor system: python -m flask --app api_server run")
    print("\n" + "="*70 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
