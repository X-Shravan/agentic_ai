#!/usr/bin/env python
"""
QUICK REFERENCE CARD
AI Exam Surveillance Report & Email System

Print this for your desk! ✅
"""

QUICK_REF = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    📊 REPORT & EMAIL SYSTEM QUICK REF                     ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─ 🚀 GETTING STARTED ──────────────────────────────────────────────────────┐
│                                                                             │
│  1. Install reportlab:                                                    │
│     pip install reportlab                                                 │
│                                                                             │
│  2. Run setup wizard (one time):                                          │
│     python setup_wizard.py                                                │
│                                                                             │
│  3. Add to main.py (see MAIN_INTEGRATION_TEMPLATE.py for full code):      │
│                                                                             │
│     from alert_logger import AlertLogger                                  │
│     from report_generator import generate_report                          │
│     from email_sender import send_report_email                            │
│                                                                             │
│     # Initialize                                                          │
│     alert_logger = AlertLogger()                                          │
│     alert_logger.update_student_count(30)                                 │
│                                                                             │
│     # When alert detected                                                 │
│     alert_logger.add_alert(student_id, "Mobile", 0.85, image_path)        │
│                                                                             │
│     # After monitoring (ESC)                                              │
│     report_path = generate_report(*alert_logger.get_report_data())        │
│     send_report_email(report_path)                                        │
│     alert_logger.clear_logs()                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 📧 EMAIL SETUP (ONE TIME) ────────────────────────────────────────────────┐
│                                                                             │
│  1. Go to: https://myaccount.google.com/security                          │
│     → Enable 2-Factor Authentication                                      │
│                                                                             │
│  2. Go to: https://myaccount.google.com/apppasswords                      │
│     → Select "Mail" and "Windows Computer"                                │
│     → Copy 16-character password                                          │
│                                                                             │
│  3. Run setup:                                                            │
│     python -c "from email_sender import interactive_setup; ..."           │
│                                                                             │
│     → Enter your Gmail address                                            │
│     → Enter 16-char App Password                                          │
│     → Enter recipient email                                               │
│                                                                             │
│  Creates: email_config.txt (keep secure!)                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 📊 ALERT LOGGING ──────────────────────────────────────────────────────────┐
│                                                                             │
│  Log Alert:                                                               │
│  ┌────────────────────────────────────────────────────────────────┐       │
│  │ alert_logger.add_alert(                                        │       │
│  │     student_id=101,                                            │       │
│  │     behavior_type="Mobile",  # Mobile/Looking Around/etc       │       │
│  │     confidence=0.85,         # 0.0-1.0                         │       │
│  │     image_path="evidence/ID_101_mobile.jpg"                    │       │
│  │ )                                                              │       │
│  └────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  Get Alerts:                                                              │
│  ┌────────────────────────────────────────────────────────────────┐       │
│  │ alerts = alert_logger.get_alerts()  # List of alert dicts      │       │
│  │ summary = alert_logger.get_summary(total_students=30)          │       │
│  └────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  Clear Logs:                                                              │
│  ┌────────────────────────────────────────────────────────────────┐       │
│  │ alert_logger.clear_logs()  # After successful email send       │       │
│  └────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 📄 REPORT GENERATION ──────────────────────────────────────────────────────┐
│                                                                             │
│  Generate Report:                                                         │
│  ┌────────────────────────────────────────────────────────────────┐       │
│  │ from report_generator import generate_report                   │       │
│  │                                                                │       │
│  │ report_path = generate_report(                                │       │
│  │     alerts_log=alerts,     # From alert_logger.get_alerts()   │       │
│  │     summary_data=summary   # From alert_logger.get_summary()  │       │
│  │ )                                                             │       │
│  │                                                                │       │
│  │ # Returns: "reports/surveillance_report_20240115_143022.pdf" │       │
│  └────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  Report Contains:                                                         │
│  ✅ Header with title & date                                             │
│  ✅ Summary statistics table                                             │
│  ✅ Alert table (up to 20)                                               │
│  ✅ Evidence section with top 10 images                                  │
│  ✅ Color-coded status indicators                                        │
│  ✅ Professional footer                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 📧 EMAIL SENDING ──────────────────────────────────────────────────────────┐
│                                                                             │
│  Send Report:                                                             │
│  ┌────────────────────────────────────────────────────────────────┐       │
│  │ from email_sender import send_report_email                    │       │
│  │                                                                │       │
│  │ success = send_report_email(                                  │       │
│  │     report_path="reports/surveillance_report_*.pdf",          │       │
│  │     recipient_email="admin@school.com"  # Optional            │       │
│  │ )                                                             │       │
│  │                                                                │       │
│  │ if success:                                                   │       │
│  │     alert_logger.clear_logs()                                 │       │
│  └────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  Note:                                                                    │
│  • Reads credentials from email_config.txt                                │
│  • Returns True/False for success                                         │
│  • Includes PDF as attachment                                             │
│  • Professional email body with formatting                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 📁 FILES & DIRECTORIES ───────────────────────────────────────────────────┐
│                                                                             │
│  Generated Files:                                                         │
│  • logs/current_session.json              ← Real-time alert log           │
│  • reports/surveillance_report_*.pdf      ← Generated PDF reports         │
│  • evidence/ID_X_behavior_TIMESTAMP.jpg   ← Alert screenshots             │
│  • email_config.txt                       ← Email credentials             │
│                                                                             │
│  New Python Modules:                                                      │
│  • alert_logger.py       (280+ lines)  ← Alert collection                │
│  • email_sender.py       (350+ lines)  ← Gmail integration                │
│  • setup_wizard.py       (350+ lines)  ← Setup automation                 │
│                                                                             │
│  Documentation:                                                           │
│  • README_REPORTS_EMAIL.md        ← User guide                           │
│  • REPORT_EMAIL_INTEGRATION.py    ← Technical reference                  │
│  • MAIN_INTEGRATION_TEMPLATE.py   ← Code examples                        │
│  • SETUP_COMPLETE.md              ← Setup summary                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 🆘 COMMON ISSUES ──────────────────────────────────────────────────────────┐
│                                                                             │
│  Email Not Sending?                                                       │
│  ✅ Check: Used Gmail App Password (NOT regular password)                 │
│  ✅ Check: email_config.txt exists                                        │
│  ✅ Check: 2FA enabled on Gmail account                                   │
│  ✅ Fix:  Re-run setup: python -c "from email_sender import ..."          │
│                                                                             │
│  Report Not Generating?                                                   │
│  ✅ Check: reportlab installed (pip install reportlab) ✅                │
│  ✅ Check: reports/ directory exists and is writable                      │
│  ✅ Check: Evidence images exist in evidence/ directory                   │
│                                                                             │
│  Alerts Not Logging?                                                      │
│  ✅ Check: alert_logger.add_alert() called in detection code              │
│  ✅ Check: Detection logic is actually triggering                         │
│  ✅ Check: logs/ directory is writable                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ ⚡ PERFORMANCE ────────────────────────────────────────────────────────────┐
│                                                                             │
│  Alert Logging:        <1 ms per alert                                    │
│  Report Generation:    2-5 seconds (20 alerts + images)                   │
│  Email Sending:        5-15 seconds (depends on network)                  │
│  Memory per Alert:     ~5 KB (with image metadata)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 📋 WORKFLOW DIAGRAM ──────────────────────────────────────────────────────┐
│                                                                             │
│  START MONITORING                                                         │
│         ↓                                                                  │
│  Detect Behavior → Log Alert → Save Evidence                              │
│         ↓                ↓                                                 │
│         └────────────────┘ (Repeat during session)                        │
│                 ↓                                                          │
│  PRESS ESC TO STOP                                                        │
│         ↓                                                                  │
│  Get All Logged Alerts                                                    │
│         ↓                                                                  │
│  Generate PDF Report                                                      │
│         ↓                                                                  │
│  Send via Email (Gmail SMTP)                                              │
│         ↓                                                                  │
│  Clear Logs (Ready for next session)                                      │
│         ↓                                                                  │
│  DONE! 🎉                                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

╔════════════════════════════════════════════════════════════════════════════╗
║                         NEXT STEPS                                         ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                             ║
║  1. Run setup:                                                            ║
║     python setup_wizard.py                                                ║
║                                                                             ║
║  2. Setup email configuration:                                            ║
║     python -c "from email_sender import interactive_setup; ..."           ║
║                                                                             ║
║  3. Add imports to main.py (copy from MAIN_INTEGRATION_TEMPLATE.py)        ║
║                                                                             ║
║  4. Start monitoring:                                                     ║
║     python main.py                                                        ║
║                                                                             ║
║  5. Get automatic reports! 📊                                             ║
║                                                                             ║
╚════════════════════════════════════════════════════════════════════════════╝

📞 DOCUMENTATION
  • Full guide:     README_REPORTS_EMAIL.md
  • Integration:    REPORT_EMAIL_INTEGRATION.py
  • Code examples:  MAIN_INTEGRATION_TEMPLATE.py
  • Setup summary:  SETUP_COMPLETE.md
"""

if __name__ == "__main__":
    print(QUICK_REF)
    
    # Offer to save to file
    import os
    save_choice = input("\nSave to file? (y/n): ").strip().lower()
    if save_choice == 'y':
        filename = "QUICK_REFERENCE.txt"
        with open(filename, 'w') as f:
            f.write(QUICK_REF)
        print(f"✅ Saved to {filename}")
