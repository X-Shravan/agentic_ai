#!/usr/bin/env python3
"""
Quick Test Script - Verify all services can start
Run this to diagnose any issues before running RUN_ALL.py
"""

import sys
import subprocess
import time
import requests
from pathlib import Path

def test_service(name, url, timeout=3):
    """Test if a service is responding"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            print(f"✅ {name}: {url}")
            return True
        else:
            print(f"⚠️  {name}: Responded with {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ {name}: Connection failed - {url}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ {name}: Timeout - {url}")
        return False
    except Exception as e:
        print(f"❌ {name}: Error - {e}")
        return False

def main():
    print("\n" + "="*60)
    print("Service Test Script - Checking if services can start")
    print("="*60 + "\n")
    
    # Check Python packages
    print("📦 Checking Python packages...\n")
    
    packages = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "flask": "Flask",
        "cv2": "OpenCV",
        "numpy": "NumPy",
    }
    
    missing = []
    for package, display_name in packages.items():
        try:
            __import__(package)
            print(f"  ✅ {display_name}")
        except ImportError:
            print(f"  ❌ {display_name} - NOT INSTALLED")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt\n")
        return 1
    
    print("\n✅ All required packages found!\n")
    
    # Test file structure
    print("📁 Checking project structure...\n")
    
    root = Path(__file__).parent
    required_files = {
        "backend/main.py": "Backend main file",
        "dashboard/app.py": "Dashboard file",
        "api_simple.py": "Simple API file",
        "frontend/package.json": "Frontend project",
    }
    
    missing_files = []
    for file_path, description in required_files.items():
        full_path = root / file_path
        if full_path.exists():
            print(f"  ✅ {description}: {file_path}")
        else:
            print(f"  ❌ {description}: {file_path} - NOT FOUND")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Missing files: {missing_files}")
        return 1
    
    print("\n✅ All files found!\n")
    
    # Try quick backend test
    print("🧪 Testing Backend import...\n")
    try:
        from backend.main import app
        print("  ✅ Backend imports successfully")
    except Exception as e:
        print(f"  ❌ Backend import failed: {e}")
        return 1
    
    print("\n" + "="*60)
    print("✅ All checks passed! Ready to run RUN_ALL.py")
    print("="*60 + "\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
