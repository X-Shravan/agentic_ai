#!/usr/bin/env python3
"""
🧪 Test PDF Generation System
Quick test to verify PDF reports are being generated correctly
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from generate_pdf_report import generate_report
from datetime import datetime

print("\n" + "="*70)
print("🧪 TESTING PDF REPORT GENERATION SYSTEM")
print("="*70 + "\n")

# Test 1: Check if reportlab is installed
print("1️⃣  Checking dependencies...")
try:
    import reportlab
    print("   ✅ reportlab is installed")
except ImportError:
    print("   ❌ reportlab not installed - install with: pip install reportlab")
    sys.exit(1)

# Test 2: Check if reports folder exists
print("\n2️⃣  Checking reports folder...")
if not os.path.exists("reports"):
    print("   ⚠️  Reports folder doesn't exist, creating...")
    os.makedirs("reports", exist_ok=True)
    print("   ✅ Folder created")
else:
    print("   ✅ Folder exists")

# Test 3: Generate test PDF with sample data
print("\n3️⃣  Generating test PDF...")
test_alerts = [
    {"id": 1, "type": "Using Mobile", "time": "10:05:12", "image_path": None},
    {"id": 2, "type": "Looking Around", "time": "10:10:30", "image_path": None},
    {"id": 3, "type": "Looking to Copy", "time": "10:15:45", "image_path": None},
]

test_summary = {
    "total_students": 30,
    "active_ids": 28,
    "total_alerts": 3,
    "normal_students": 25,
}

try:
    pdf_path = generate_report(test_alerts, test_summary)
    
    if pdf_path and os.path.exists(pdf_path):
        file_size = os.path.getsize(pdf_path)
        print(f"   ✅ PDF generated successfully!")
        print(f"      📁 Location: {os.path.abspath(pdf_path)}")
        print(f"      💾 Size: {file_size:,} bytes")
        
        # Test 4: List all reports
        print("\n4️⃣  Listing all reports in folder...")
        reports = sorted([f for f in os.listdir("reports") if f.endswith('.pdf')])
        print(f"   📊 Total PDFs: {len(reports)}")
        for i, report in enumerate(reports[-5:], 1):  # Show last 5
            path = os.path.join("reports", report)
            size = os.path.getsize(path)
            print(f"      {i}. {report} ({size:,} bytes)")
        
        print("\n" + "="*70)
        print("✅ PDF GENERATION TEST PASSED!")
        print("="*70 + "\n")
        print("📌 Summary:")
        print(f"   • PDF generation: ✅ Working")
        print(f"   • Reports folder: ✅ Accessible")
        print(f"   • File creation: ✅ Success")
        print("\n💡 Your system should automatically generate PDFs when you:")
        print("   1. Run: python api_server.py")
        print("   2. Run: npm start (in dashboard folder)")
        print("   3. Let the system collect alerts")
        print("   4. Press Ctrl+C to stop the server")
        print("   5. PDF will be saved to reports/ folder")
        
    else:
        print(f"   ❌ PDF not created. Path: {pdf_path}")
        sys.exit(1)

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
