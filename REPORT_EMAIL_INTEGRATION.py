"""
INTEGRATION GUIDE: Report Generation + Email System
Complete guide for integrating report generation, email sending, and alert logging
into your AI Exam Surveillance System
"""

# ================================================================
# STEP 1: SETUP EMAIL CONFIGURATION
# ================================================================
"""
Before using the email system, you must:

1. Enable 2-Factor Authentication on your Gmail account:
   - Go to https://myaccount.google.com/security
   - Enable "2-Step Verification"

2. Generate Gmail App Password:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Google will generate a 16-character password
   - Copy this password (you'll use it in setup)

3. Run email setup (one time only):
   
   from email_sender import interactive_setup
   interactive_setup()
   
   This will prompt you for:
   - Your Gmail address (e.g., your.email@gmail.com)
   - Your Gmail App Password (the 16-char one from step 2)
   - Recipient email (where reports will be sent)
   
   Configuration will be saved to: email_config.txt
"""


# ================================================================
# STEP 2: INTEGRATE WITH MAIN.PY SURVEILLANCE LOOP
# ================================================================
"""
Add to your main.py at the top (imports section):

    from alert_logger import AlertLogger
    from report_generator import generate_report
    from email_sender import send_report_email
    
    # Initialize logger
    alert_logger = AlertLogger("logs", "current_session.json")

In your main surveillance loop, when an alert is detected:

    # When you detect a behavior, log it
    alert_logger.add_alert(
        student_id=student_id,
        behavior_type="Mobile",  # or "Looking Around", etc.
        confidence=confidence_score,
        image_path=evidence_image_path  # from evidence_capture.py
    )

When monitoring session ends:

    # Generate report from collected logs
    alerts, summary = alert_logger.get_alerts(), alert_logger.get_summary(
        total_students=total_students_in_exam
    )
    
    report_path = generate_report(alerts, summary)
    print(f"✅ Report saved to: {report_path}")
    
    # Send via email
    if send_report_email(report_path, "admin@school.com"):
        # Clear logs after successful send
        alert_logger.clear_logs()
        print("✅ Report emailed and logs cleared")
"""


# ================================================================
# STEP 3: COMPLETE MAIN.PY INTEGRATION EXAMPLE
# ================================================================
"""
Here's what your main.py should look like:

====== MAIN.PY SECTION: IMPORTS ======

from alert_logger import AlertLogger
from report_generator import generate_report
from email_sender import send_report_email
import cv2
import numpy as np
# ... other imports ...

====== MAIN.PY SECTION: INITIALIZATION ======

# Initialize alert logging
alert_logger = AlertLogger("logs", "current_session.json")
TOTAL_STUDENTS = 30  # Set based on your exam

alert_logger.update_student_count(TOTAL_STUDENTS)

====== MAIN.PY SECTION: IN YOUR DETECTION LOOP ======

while cap.isOpened():
    # ... your existing detection code ...
    
    if detection_result.is_alert and confidence > threshold:
        # IMPORTANT: Log the alert
        alert_logger.add_alert(
            student_id=student_id,
            behavior_type=behavior_type,  # "Mobile", "Looking to Copy", etc.
            confidence=confidence,
            image_path=evidence_image_path
        )
        
        # ... rest of your handling code ...

====== MAIN.PY SECTION: AFTER MONITORING ENDS ======

# When user presses ESC to stop monitoring:
if key == 27:  # ESC key
    cap.release()
    cv2.destroyAllWindows()
    
    print("\\n" + "="*60)
    print("📊 GENERATING SESSION REPORT...")
    print("="*60)
    
    # Get all data
    alerts = alert_logger.get_alerts()
    summary = alert_logger.get_summary(
        total_students=TOTAL_STUDENTS,
        active_ids=set(alert['id'] for alert in alerts)
    )
    
    # Generate report
    report_path = generate_report(alerts, summary)
    
    if report_path:
        print(f"✅ Report generated: {report_path}")
        
        # Send email
        print("\\n📧 Sending report via email...")
        if send_report_email(report_path):
            alert_logger.clear_logs()
            print("✅ Report sent and logs cleared!")
        else:
            print("⚠️ Report generated but email failed to send")
    
    break
"""


# ================================================================
# STEP 4: QUICK START REFERENCE
# ================================================================
"""
QUICK START (5 minutes):

1. Setup email (one time):
   python -c "from email_sender import interactive_setup; interactive_setup()"

2. Add to main.py imports:
   from alert_logger import AlertLogger
   from report_generator import generate_report
   from email_sender import send_report_email

3. Initialize in main.py:
   alert_logger = AlertLogger()

4. Log alerts when detected:
   alert_logger.add_alert(student_id, behavior_type, confidence, image_path)

5. Generate and email report:
   report_path = generate_report(alerts, summary)
   send_report_email(report_path, recipient_email)
   alert_logger.clear_logs()
"""


# ================================================================
# STEP 5: API REFERENCE
# ================================================================
"""
ALERT LOGGER API:

    from alert_logger import AlertLogger
    
    # Create logger
    logger = AlertLogger(log_dir="logs", log_file="current_session.json")
    
    # Add alert
    alert = logger.add_alert(
        student_id=101,
        behavior_type="Mobile",
        confidence=0.85,
        image_path="evidence/student_101_mobile_12345.jpg"
    )
    # Returns: {id, type, confidence, time, timestamp, image_path}
    
    # Get all alerts
    alerts = logger.get_alerts()  # List of alert dicts
    
    # Get summary
    summary = logger.get_summary(
        total_students=30,
        active_ids={101, 102, 105}
    )
    # Returns: {total_students, active_ids, total_alerts, normal_students, 
    #           alert_breakdown, session_duration, average_confidence}
    
    # Clear logs
    logger.clear_logs()
    
    # Export alerts
    logger.export_alerts("archived_session.json")

REPORT GENERATOR API:

    from report_generator import generate_report
    
    # Generate report
    report_path = generate_report(
        alerts_log=[...],  # List of alert dicts from logger
        summary_data={...}  # Summary dict from logger
    )
    # Returns: Path to generated PDF (e.g., "reports/surveillance_report_20240115_143022.pdf")

EMAIL SENDER API:

    from email_sender import send_report_email, setup_email_config
    
    # Setup (one time)
    setup_email_config(
        sender_email="your.email@gmail.com",
        app_password="xxxx xxxx xxxx xxxx",  # 16-char app password
        recipient_email="admin@school.com"
    )
    
    # Send report
    success = send_report_email(
        report_path="reports/surveillance_report_20240115_143022.pdf",
        recipient_email="admin@school.com"
    )
    # Returns: True if successful, False otherwise
"""


# ================================================================
# STEP 6: ALERT LOG STRUCTURE
# ================================================================
"""
Each alert has this structure:

    {
        'id': 101,                                    # Student ID
        'type': 'Mobile',                             # Behavior type
        'confidence': 0.85,                           # 0.0 to 1.0
        'time': '14:30:22.123',                       # HH:MM:SS.mmm
        'timestamp': '2024-01-15T14:30:22.123456',    # ISO format
        'image_path': 'evidence/student_101_...jpg'   # Path to evidence
    }

Behavior types (set by your detection system):
  - "Mobile"
  - "Looking Around"
  - "Looking to Copy"
  - "Leaning"
  - Or any custom behavior string
"""


# ================================================================
# STEP 7: REPORT STRUCTURE
# ================================================================
"""
Generated PDF reports contain:

1. HEADER
   - Title: "AI EXAM SURVEILLANCE REPORT"
   - Date/Time: When generated
   - Separator line

2. SUMMARY TABLE
   - Total Students: Number of students in exam
   - Active IDs: Number with at least one alert
   - Total Alerts: Total detections
   - Normal Students: No alerts during exam
   - Average Confidence: Mean detection confidence

3. ALERTS TABLE
   - Student ID | Behavior Type | Time | Status (color-coded emoji)
   - Up to 20 alerts shown (truncated if more)
   - Color coding:
     * 🔴 RED: Mobile/Copy (high priority)
     * 🟠 ORANGE: Looking/Leaning (medium priority)
     * ⚪ INFO: Other alerts

4. EVIDENCE SECTION
   - Top 10 most recent alerts with images
   - Image resized to 6" × 4.5"
   - Format: "ID X → Type → HH:MM:SS"
   - Graceful handling of missing images
   - Page breaks every 3 alerts

5. FOOTER
   - Report generation timestamp
   - System identifier

If no alerts:
   - Shows success message with green checkmark ✅
   - Summary shows 0 alerts
"""


# ================================================================
# STEP 8: TROUBLESHOOTING
# ================================================================
"""
EMAIL NOT SENDING?

1. ❌ "Authentication failed"
   Fix: Check that you're using Gmail App Password, not regular password
   - Go to https://myaccount.google.com/apppasswords
   - Generate new App Password if needed
   - Make sure 2FA is enabled

2. ❌ "Connection refused"
   Fix: Gmail SMTP might be blocked
   - Check firewall settings
   - Ensure SMTP port 587 is open
   - Try running on different network if at school/work

3. ❌ "SMTPException: 535 5.7.8 Username and Password not accepted"
   Fix: Your credentials are wrong
   - Re-run setup: python -c "from email_sender import interactive_setup; interactive_setup()"
   - Verify email address case-sensitivity
   - Make sure app password is copied correctly (spaces matter!)

4. ❌ "Report file not found"
   Fix: PDF generation failed
   - Check that reportlab is installed: pip install reportlab
   - Check that log directory exists
   - Check file permissions

REPORT NOT GENERATING?

1. ❌ "No module named 'reportlab'"
   Fix: Install reportlab library
   pip install reportlab

2. ❌ "Invalid image path"
   Fix: Evidence images not saved properly
   - Check evidence_capture.py is being called
   - Verify "evidence/" directory exists and is writable
   - Check image paths passed to logger are correct

3. ❌ "PDF file corrupted"
   Fix: Rare issue, usually permissions
   - Check "reports/" directory is writable
   - Ensure enough disk space
   - Try deleting and recreating reports/ folder

LOG NOT COLLECTING?

1. ❌ "Alerts list always empty"
   Fix: You're not calling alert_logger.add_alert()
   - Verify add_alert() is in your detection code
   - Check detection logic is triggering
   - Add debug print statements before logger.add_alert()

2. ❌ "Logs not persisting"
   Fix: Check "logs/" directory
   - Verify directory is writable
   - Check current_session.json file is created
   - Ensure JSON format is valid
"""


# ================================================================
# STEP 9: RUNNING THE COMPLETE WORKFLOW
# ================================================================
"""
MANUAL WORKFLOW (for testing):

1. Terminal 1: Start camera feed
   python main.py

2. In main.py, pressing ESC will:
   - Stop camera
   - Generate report from collected logs
   - Send report via email
   - Clear logs for next session

3. Check results:
   - PDF report in: reports/surveillance_report_YYYYMMDD_HHMMSS.pdf
   - Email received at configured recipient
   - Logs cleared in: logs/current_session.json


AUTOMATED WORKFLOW (after hours):

1. Save this script as schedule_reports.py:

    from alert_logger import AlertLogger
    from report_generator import generate_report
    from email_sender import send_report_email
    
    def generate_daily_report():
        # Load today's logs
        logger = AlertLogger()
        alerts = logger.get_alerts()
        summary = logger.get_summary(total_students=30)
        
        # Generate report
        report_path = generate_report(alerts, summary)
        
        # Send email
        if report_path:
            send_report_email(report_path, "principal@school.com")
            logger.clear_logs()
            print("✅ Daily report generated and sent!")
    
    if __name__ == "__main__":
        generate_daily_report()

2. Schedule with Windows Task Scheduler:
   - Create task to run: python schedule_reports.py
   - Set to run at desired time (e.g., 5 PM daily)
"""


# ================================================================
# STEP 10: CONFIGURATION FILE
# ================================================================
"""
Your email_config.txt (auto-created by setup) should contain:

    SENDER_EMAIL=your.email@gmail.com
    APP_PASSWORD=xxxx xxxx xxxx xxxx
    RECIPIENT_EMAIL=admin@school.com

NEVER:
  - Share this file
  - Commit to version control
  - Expose the app password
  - Use your regular Gmail password

SECURITY:
  - App passwords are specific to this application
  - If compromised, regenerate at myaccount.google.com/apppasswords
  - The password only works for Gmail SMTP (not other services)
"""

print(__doc__)
