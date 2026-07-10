#!/usr/bin/env python3
"""
🚀 QUICK START: PDF Report Generation

Use this file as a reference for how to generate PDFs in your project.
"""

# ===================================================
# EXAMPLE 1: SIMPLE USAGE
# ===================================================

from generate_pdf_report import generate_report

def example_1_basic():
    """Simplest possible usage"""
    
    # Your data
    alerts = [
        {"id": 1, "type": "Using Mobile", "time": "10:05:12"},
        {"id": 2, "type": "Looking Around", "time": "10:10:30"},
    ]
    
    summary = {
        "total_students": 30,
        "active_ids": 28,
        "total_alerts": 2,
        "normal_students": 26
    }
    
    # Generate PDF
    pdf_path = generate_report(alerts, summary)
    
    # Check result
    if pdf_path:
        print(f"✅ PDF created: {pdf_path}")
    else:
        print("❌ PDF creation failed")


# ===================================================
# EXAMPLE 2: WITH ERROR HANDLING
# ===================================================

def example_2_safe_usage():
    """Safe usage with error handling"""
    
    try:
        alerts = [
            {"id": 1, "type": "Using Mobile", "time": "10:05:12", "image_path": "evidence/1.jpg"},
            {"id": 2, "type": "Looking Around", "time": "10:10:30"},
        ]
        
        summary = {
            "total_students": 50,
            "active_ids": 48,
            "total_alerts": 2,
            "normal_students": 46
        }
        
        # Generate PDF
        pdf_path = generate_report(alerts, summary)
        
        if pdf_path:
            print(f"✅ Success: {pdf_path}")
            # Do something with the PDF
            # e.g., send email, upload, etc.
        else:
            print("⚠️ Warning: PDF generation returned None")
    
    except Exception as e:
        print(f"❌ Error: {e}")


# ===================================================
# EXAMPLE 3: WITH REAL SURVEILLANCE DATA
# ===================================================

def example_3_from_surveillance():
    """Convert surveillance data to PDF"""
    
    # Your surveillance system's alert data
    raw_alerts = [
        {'id': 1, 'type': 'Using Mobile', 'timestamp': '2026-04-19T10:05:12', 'image_path': 'evidence/ID1_100512.jpg'},
        {'id': 2, 'type': 'Looking Around', 'timestamp': '2026-04-19T10:10:30', 'image_path': None},
        {'id': 3, 'type': 'Leaning', 'timestamp': '2026-04-19T10:15:45', 'image_path': 'evidence/ID3_101545.jpg'},
    ]
    
    # Convert to PDF format
    alerts = [
        {
            "id": alert['id'],
            "type": alert['type'],
            "time": alert['timestamp'].split('T')[1][:8],  # HH:MM:SS
            "image_path": alert.get('image_path')
        }
        for alert in raw_alerts
    ]
    
    summary = {
        "total_students": 100,
        "active_ids": 95,
        "total_alerts": len(alerts),
        "normal_students": 92
    }
    
    # Generate
    pdf_path = generate_report(alerts, summary)
    print(f"📄 Report: {pdf_path}")


# ===================================================
# EXAMPLE 4: BATCH GENERATION
# ===================================================

def example_4_batch():
    """Generate multiple PDFs"""
    
    test_cases = [
        {
            "name": "Morning Session",
            "alerts": [{"id": i, "type": "Using Mobile", "time": f"{10}:{i:02d}:00"} for i in range(1, 6)],
            "students": 50
        },
        {
            "name": "Afternoon Session",
            "alerts": [{"id": i, "type": "Looking Around", "time": f"{14}:{i:02d}:00"} for i in range(1, 4)],
            "students": 45
        },
    ]
    
    for case in test_cases:
        summary = {
            "total_students": case["students"],
            "active_ids": case["students"] - 2,
            "total_alerts": len(case["alerts"]),
            "normal_students": case["students"] - len(case["alerts"])
        }
        
        pdf_path = generate_report(case["alerts"], summary)
        print(f"✅ {case['name']}: {pdf_path}")


# ===================================================
# EXAMPLE 5: USING IN API
# ===================================================

def example_5_api_usage():
    """How the API endpoint uses it"""
    
    from flask import Flask, jsonify
    import os
    
    app = Flask(__name__)
    
    @app.route('/api/reports/generate', methods=['POST'])
    def generate_report_endpoint():
        """Generate PDF via API"""
        
        # Your data collection logic
        alerts = [...]  # From surveillance system
        summary = {...}  # From dashboard
        
        # Generate PDF
        pdf_path = generate_report(alerts, summary)
        
        if pdf_path and os.path.exists(pdf_path):
            return jsonify({
                'success': True,
                'report_path': pdf_path,
                'file_size': os.path.getsize(pdf_path)
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate report'
            }), 500


# ===================================================
# EXAMPLE 6: SCHEDULED GENERATION
# ===================================================

def example_6_scheduled():
    """Generate reports on a schedule"""
    
    from datetime import datetime
    import time
    
    def generate_hourly_reports(surveillance_system):
        """Generate report every hour"""
        
        while True:
            # Wait until next hour
            now = datetime.now()
            wait_seconds = (60 - now.minute) * 60
            print(f"⏰ Next report in {wait_seconds//60} minutes...")
            time.sleep(wait_seconds)
            
            # Get current data
            alerts = surveillance_system.get_alerts()
            summary = surveillance_system.get_summary()
            
            # Generate PDF
            pdf_path = generate_report(alerts, summary)
            print(f"📄 Scheduled report: {pdf_path}")


# ===================================================
# MAIN
# ===================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 PDF REPORT GENERATION - QUICK START EXAMPLES")
    print("="*70 + "\n")
    
    print("Example 1: Basic Usage")
    print("-" * 70)
    example_1_basic()
    
    print("\n\nExample 2: With Error Handling")
    print("-" * 70)
    example_2_safe_usage()
    
    print("\n\nExample 3: From Surveillance Data")
    print("-" * 70)
    example_3_from_surveillance()
    
    print("\n\nExample 4: Batch Generation")
    print("-" * 70)
    example_4_batch()
    
    print("\n\n" + "="*70)
    print("✅ Check reports/ folder for generated PDFs")
    print("="*70 + "\n")
