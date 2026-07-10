#!/usr/bin/env python3
"""
🧪 TEST SCRIPT: PDF Report Generation System
Demonstrates the complete workflow
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from generate_pdf_report import generate_report

# ===================================================
# TEST 1: BASIC REPORT
# ===================================================

def test_basic_report():
    """Test basic PDF generation"""
    print("\n" + "🔵 TEST 1: BASIC REPORT GENERATION")
    print("-" * 70)
    
    # Simple alerts
    alerts = [
        {"id": 1, "type": "Using Mobile", "time": "10:05:12"},
        {"id": 2, "type": "Looking Around", "time": "10:10:30"},
    ]
    
    summary = {
        "total_students": 25,
        "active_ids": 23,
        "total_alerts": 2,
        "normal_students": 21
    }
    
    pdf_path = generate_report(alerts, summary)
    
    if pdf_path and os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        print(f"\n✅ TEST 1 PASSED")
        print(f"   File: {pdf_path}")
        print(f"   Size: {size} bytes\n")
        return True
    else:
        print(f"\n❌ TEST 1 FAILED\n")
        return False


# ===================================================
# TEST 2: LARGE REPORT WITH MANY ALERTS
# ===================================================

def test_large_report():
    """Test PDF with many alerts"""
    print("\n" + "🟣 TEST 2: LARGE REPORT (MANY ALERTS)")
    print("-" * 70)
    
    # Generate 15 alerts
    alerts = []
    for i in range(1, 16):
        behavior_types = ["Using Mobile", "Looking Around", "Leaning", "Looking to Copy"]
        alerts.append({
            "id": i,
            "type": behavior_types[i % len(behavior_types)],
            "time": f"{10 + i//60:02d}:{5 + (i*5)%60:02d}:{12 + (i*3)%60:02d}"
        })
    
    summary = {
        "total_students": 50,
        "active_ids": 48,
        "total_alerts": 15,
        "normal_students": 33
    }
    
    pdf_path = generate_report(alerts, summary)
    
    if pdf_path and os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        print(f"\n✅ TEST 2 PASSED")
        print(f"   File: {pdf_path}")
        print(f"   Size: {size} bytes")
        print(f"   Alerts: {len(alerts)}\n")
        return True
    else:
        print(f"\n❌ TEST 2 FAILED\n")
        return False


# ===================================================
# TEST 3: EMPTY REPORT (NO ALERTS)
# ===================================================

def test_empty_report():
    """Test PDF with no alerts"""
    print("\n" + "🟢 TEST 3: CLEAN SESSION (NO ALERTS)")
    print("-" * 70)
    
    alerts = []  # No alerts
    
    summary = {
        "total_students": 30,
        "active_ids": 30,
        "total_alerts": 0,
        "normal_students": 30
    }
    
    pdf_path = generate_report(alerts, summary)
    
    if pdf_path and os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        print(f"\n✅ TEST 3 PASSED")
        print(f"   File: {pdf_path}")
        print(f"   Size: {size} bytes\n")
        return True
    else:
        print(f"\n❌ TEST 3 FAILED\n")
        return False


# ===================================================
# TEST 4: BEHAVIOR TYPES
# ===================================================

def test_all_behavior_types():
    """Test all behavior types"""
    print("\n" + "🟡 TEST 4: ALL BEHAVIOR TYPES")
    print("-" * 70)
    
    behavior_types = [
        "Using Mobile",
        "Looking Around",
        "Leaning",
        "Looking to Copy",
        "Sharing Answers",
        "Suspicious Activity"
    ]
    
    alerts = []
    for idx, behavior in enumerate(behavior_types, 1):
        alerts.append({
            "id": idx,
            "type": behavior,
            "time": f"10:{10+idx:02d}:{idx*10%60:02d}"
        })
    
    summary = {
        "total_students": 100,
        "active_ids": 95,
        "total_alerts": len(behavior_types),
        "normal_students": 89
    }
    
    pdf_path = generate_report(alerts, summary)
    
    if pdf_path and os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        print(f"\n✅ TEST 4 PASSED")
        print(f"   File: {pdf_path}")
        print(f"   Size: {size} bytes")
        print(f"   Behavior Types: {len(behavior_types)}\n")
        return True
    else:
        print(f"\n❌ TEST 4 FAILED\n")
        return False


# ===================================================
# MAIN TEST RUNNER
# ===================================================

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 PDF REPORT GENERATION - TEST SUITE")
    print("="*70)
    
    results = {
        "Test 1: Basic Report": test_basic_report(),
        "Test 2: Large Report": test_large_report(),
        "Test 3: Empty Report": test_empty_report(),
        "Test 4: Behavior Types": test_all_behavior_types(),
    }
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST RESULTS SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}  {test_name}")
    
    print("\n" + "-"*70)
    print(f"Score: {passed}/{total} tests passed ({passed*100//total}%)")
    
    # Check reports folder
    print("\n" + "-"*70)
    print("📁 REPORTS FOLDER CONTENTS:")
    reports_dir = "reports"
    
    if os.path.exists(reports_dir):
        files = os.listdir(reports_dir)
        pdf_files = [f for f in files if f.endswith('.pdf')]
        print(f"   Total PDFs: {len(pdf_files)}")
        
        for pdf_file in sorted(pdf_files)[-5:]:  # Show last 5
            file_path = os.path.join(reports_dir, pdf_file)
            size = os.path.getsize(file_path)
            print(f"   • {pdf_file} ({size} bytes)")
    else:
        print(f"   ⚠️  Folder not found: {reports_dir}")
    
    print("\n" + "="*70)
    
    if passed == total:
        print(f"✅ ALL TESTS PASSED - Report system is working perfectly!")
    else:
        print(f"⚠️  {total - passed} test(s) failed - check errors above")
    
    print("="*70 + "\n")
    
    return passed == total


# ===================================================
# MAIN
# ===================================================

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
