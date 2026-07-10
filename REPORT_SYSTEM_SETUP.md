# AI Exam Surveillance - Report System Configuration

## 🔧 Setup Instructions

### 1. Install Required Dependencies

```bash
pip install reportlab pillow
```

Or if using requirements.txt:
```bash
pip install -r requirements.txt
```

### 2. Gmail App Password Setup (CRITICAL)

**Why not use regular password?**
- Gmail blocks less secure app login
- App passwords are more secure
- Only for your app, not your main Gmail

**Steps to get App Password:**

1. Go to Google Account: https://myaccount.google.com
2. Left sidebar → Security
3. Enable 2-Step Verification (if not already done)
4. Search for "App passwords"
5. Select "Mail" and "Windows Computer" (or your device)
6. Google generates 16-character password
7. Copy it (you'll use this in config)

**Example App Password:** `abcd efgh ijkl mnop` (with spaces, remove them when using)

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
SURVEILLANCE_EMAIL=your-email@gmail.com
SURVEILLANCE_APP_PASSWORD=abcdefghijklmnop
SURVEILLANCE_RECIPIENT=recipient@gmail.com
```

**Or set as system environment variables:**

**Windows CMD:**
```batch
setx SURVEILLANCE_EMAIL "your-email@gmail.com"
setx SURVEILLANCE_APP_PASSWORD "abcdefghijklmnop"
setx SURVEILLANCE_RECIPIENT "recipient@gmail.com"
```

**Windows PowerShell:**
```powershell
[Environment]::SetEnvironmentVariable("SURVEILLANCE_EMAIL", "your-email@gmail.com")
[Environment]::SetEnvironmentVariable("SURVEILLANCE_APP_PASSWORD", "abcdefghijklmnop")
[Environment]::SetEnvironmentVariable("SURVEILLANCE_RECIPIENT", "recipient@gmail.com")
```

### 4. Verify Setup

```bash
python -c "from report_system import ReportGenerator; print('✅ Report system ready')"
```

---

## 📚 Usage Guide

### Basic Usage (3 Steps)

**Step 1: Initialize Report System**
```python
from report_integration import initialize_report_system

initialize_report_system(
    sender_email="your-email@gmail.com",
    app_password="your-app-password",
    recipient_email="recipient@gmail.com"
)
```

**Step 2: Log Alerts During Monitoring**
```python
from report_integration import log_alert_to_report

# When an alert is detected:
log_alert_to_report(
    student_id=3,
    behavior_type="Using Mobile",
    timestamp="10:05:12",
    image_path="evidence/ID3_100512.jpg"
)
```

**Step 3: Generate Report When Done**
```python
from report_integration import generate_session_report

result = generate_session_report(
    total_students=30,
    active_ids=28,
    total_alerts=5,
    normal_students=23,
    monitoring_time="00:45:30",
    send_email=True,  # Send to email
    clear_logs=True   # Clear logs after
)

print(f"✅ Report: {result['report_path']}")
print(f"📧 Email sent: {result['email_sent']}")
```

---

## 🔌 Integration with Existing System

### In api_server.py

**At startup:**
```python
from report_integration import initialize_report_system

if __name__ == '__main__':
    # Initialize report system
    initialize_report_system()
    
    # Start surveillance system...
```

**In surveillance_loop() when alert detected:**
```python
from report_integration import log_alert_to_report
from datetime import datetime

# When decision agent triggers alert:
if dec.should_alert:
    log_alert_to_report(
        student_id=tid,
        behavior_type=dec.situation,  # e.g., "Using Mobile"
        timestamp=datetime.now().strftime("%H:%M:%S"),
        image_path=f"evidence/ID{tid}_{datetime.now().strftime('%H%M%S')}.jpg"
    )
```

**When monitoring stops:**
```python
from report_integration import generate_session_report

# Calculate final statistics
result = generate_session_report(
    total_students=dashboard_data.total_students,
    active_ids=len(dashboard_data.active_ids),
    total_alerts=len(dashboard_data.alerts),
    normal_students=dashboard_data.total_students - len(dashboard_data.alerts),
    monitoring_time=elapsed_time_str,
    send_email=True,
    clear_logs=True
)

print(f"📊 Report generated: {result['report_path']}")
if result['email_sent']:
    print(f"📧 Email sent to recipient")
```

---

## 📁 Directory Structure

```
mini project/
├─ report_system.py          ← Main report generation module
├─ report_integration.py     ← Integration layer
├─ api_server.py             ← Updated with report integration
├─ logs/
│  └─ alerts_log.json        ← Real-time alert log (auto-created)
├─ reports/
│  └─ Surveillance_Report_*.pdf  ← Generated reports
├─ evidence/
│  └─ ID*.jpg                ← Alert evidence images
└─ requirements.txt
```

---

## ⚙️ Configuration Options

### Report Generator
```python
from report_system import ReportGenerator

generator = ReportGenerator(output_dir="custom_reports/")
report_path = generator.generate_report(alerts, summary_data)
```

### Email Sender
```python
from report_system import EmailSender

sender = EmailSender(
    sender_email="your-email@gmail.com",
    app_password="your-app-password",
    recipient_email="recipient@gmail.com"
)

sender.send_report(
    report_path="reports/report.pdf",
    subject="Custom Subject Line"
)
```

### Alert Logger
```python
from report_system import AlertLogManager

logger = AlertLogManager(log_file="custom_logs/alerts.json")
logger.add_alert(alert_dict)
alerts = logger.get_alerts()
logger.clear_alerts()
```

---

## 🧪 Testing

### Test Report Generation (No Email)
```bash
python report_system.py
```

This generates a test report without sending email.

### Test Email Configuration
```python
from report_system import EmailSender

sender = EmailSender(
    sender_email="your-email@gmail.com",
    app_password="your-app-password",
    recipient_email="your-email@gmail.com"  # Send to yourself
)

# Try sending test email
success = sender.send_report("reports/test_report.pdf")
print(f"Email sent: {success}")
```

---

## 🚨 Troubleshooting

### "Authentication failed"
```
❌ Check:
1. Gmail App Password (not regular password)
2. 2-Step Verification is enabled
3. Copy-paste exactly (remove any spaces)
4. Correct email address
```

### "SSL: CERTIFICATE_VERIFY_FAILED"
```
Solution (Windows):
pip install certifi
/Applications/Python*/Install\ Certificates.command (macOS)
```

### "No alerts in report"
```
Check:
1. Is log_alert_to_report() being called?
2. Check logs/alerts_log.json for entries
3. Did you clear logs after previous report?
```

### Images not showing in PDF
```
Check:
1. Image path is correct and file exists
2. Image format is .jpg or .png
3. File permissions allow reading
4. Image is not corrupted
```

---

## 📊 Alert Log Format

**File:** `logs/alerts_log.json`

```json
[
  {
    "id": 3,
    "type": "Using Mobile",
    "time": "10:05:12",
    "image_path": "evidence/ID3_100512.jpg"
  },
  {
    "id": 7,
    "type": "Looking Around",
    "time": "10:10:30",
    "image_path": "evidence/ID7_101030.jpg"
  }
]
```

---

## 📄 PDF Report Features

✅ Professional header with title and date
✅ Summary statistics table
✅ Suspicious activity log table
✅ Evidence section with:
  - Student ID, behavior type, timestamp
  - Screenshot image (if available)
  - Maximum 10 alerts per report
  - Automatic page breaks

✅ Error handling for missing images
✅ Clean formatting with colors and styling

---

## 📧 Email Features

✅ Secure SMTP with TLS encryption
✅ Gmail App Password authentication
✅ Professional email body
✅ PDF attachment
✅ Error handling and logging
✅ Connection validation

---

## 🔐 Security Best Practices

1. **Never commit credentials to Git**
   - Use .env file with .gitignore
   - Or use environment variables

2. **Use Gmail App Password**
   - Don't use your main Gmail password
   - Can revoke easily in Google Account

3. **Secure evidence images**
   - Store in protected directory
   - Auto-clean old images periodically

4. **Log rotation**
   - Implement log cleanup
   - Don't store indefinitely

---

## 🚀 Full Integration Example

```python
from report_integration import (
    initialize_report_system,
    log_alert_to_report,
    generate_session_report
)
from datetime import datetime

# 1. Initialize at startup
initialize_report_system(
    sender_email="your-email@gmail.com",
    app_password="your-app-password",
    recipient_email="recipient@gmail.com"
)

# 2. During monitoring, when alert happens:
log_alert_to_report(
    student_id=tracking_id,
    behavior_type="Using Mobile",
    timestamp=datetime.now().strftime("%H:%M:%S"),
    image_path=f"evidence/ID{tracking_id}_{int(datetime.now().timestamp())}.jpg"
)

# 3. When monitoring ends:
result = generate_session_report(
    total_students=30,
    active_ids=28,
    total_alerts=5,
    normal_students=23,
    monitoring_time="00:45:30",
    send_email=True,
    clear_logs=True
)

print(f"✅ Report: {result}")
# Output: {
#   'success': True,
#   'report_path': 'reports/Surveillance_Report_20260418_145030.pdf',
#   'email_sent': True,
#   'logs_cleared': True,
#   'message': 'Report generated (5 alerts), email sent: True, logs cleared: True'
# }
```

---

## 📞 Support

For issues:
1. Check troubleshooting section above
2. Verify all dependencies installed: `pip install reportlab pillow`
3. Check logs: Console output shows detailed error messages
4. Verify email configuration with test

---

## ✨ Features Summary

✅ Real-time alert logging (no dummy data)
✅ Professional PDF generation with images
✅ Automatic email delivery
✅ Clean log clearing after send
✅ Full error handling
✅ Production-ready code
✅ Easy integration
✅ No external APIs
✅ Fully offline capable
✅ Modular design

---

**Last Updated:** 2026-04-18
**Status:** ✅ Production Ready
