# 🚀 Report System - Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies
```bash
pip install reportlab pillow
```

### Step 2: Get Gmail App Password
1. Go to https://myaccount.google.com
2. Security → App passwords
3. Select Mail → Windows Computer
4. Copy the 16-character password

### Step 3: Set Environment Variables

**Windows (CMD - Run as Admin):**
```batch
setx SURVEILLANCE_EMAIL "your-email@gmail.com"
setx SURVEILLANCE_APP_PASSWORD "abcdefghijklmnop"
setx SURVEILLANCE_RECIPIENT "recipient@gmail.com"
```

**Windows (PowerShell):**
```powershell
$env:SURVEILLANCE_EMAIL = "your-email@gmail.com"
$env:SURVEILLANCE_APP_PASSWORD = "abcdefghijklmnop"
$env:SURVEILLANCE_RECIPIENT = "recipient@gmail.com"
```

### Step 4: Test Setup
```python
python -c "
from report_system import ReportGenerator
print('✅ Report system is ready!')
"
```

---

## 📝 Usage Examples

### Example 1: Generate Report Only (No Email)
```python
from report_system import ReportGenerator

# Your real data
alerts = [
    {"id": 3, "type": "Using Mobile", "time": "10:05:12", "image_path": "evidence/ID3.jpg"},
    {"id": 7, "type": "Looking Around", "time": "10:10:30", "image_path": "evidence/ID7.jpg"}
]

summary = {
    "total_students": 30,
    "active_ids": 28,
    "total_alerts": 2,
    "normal_students": 26,
    "monitoring_time": "00:30:00"
}

# Generate
generator = ReportGenerator()
report_path = generator.generate_report(alerts, summary)
print(f"✅ Report saved to: {report_path}")
```

### Example 2: Log Alerts During Monitoring
```python
from report_integration import log_alert_to_report
from datetime import datetime

# When an alert is detected:
log_alert_to_report(
    student_id=3,
    behavior_type="Using Mobile",
    timestamp=datetime.now().strftime("%H:%M:%S"),
    image_path="evidence/ID3_100512.jpg"
)

print("✅ Alert logged for report")
```

### Example 3: Send Report via Email
```python
from report_system import EmailSender

sender = EmailSender(
    sender_email="your-email@gmail.com",
    app_password="abcdefghijklmnop",
    recipient_email="recipient@gmail.com"
)

success = sender.send_report(
    report_path="reports/report.pdf",
    subject="AI Surveillance Report"
)

if success:
    print("✅ Email sent!")
else:
    print("❌ Email failed - check console logs")
```

### Example 4: Complete Pipeline
```python
from report_integration import (
    initialize_report_system,
    log_alert_to_report,
    generate_session_report
)
from datetime import datetime

# Initialize once at startup
initialize_report_system(
    sender_email="your-email@gmail.com",
    app_password="abcdefghijklmnop",
    recipient_email="recipient@gmail.com"
)

# During monitoring, log each alert
for alert_data in alerts_detected:
    log_alert_to_report(
        student_id=alert_data['track_id'],
        behavior_type=alert_data['situation'],
        timestamp=datetime.now().strftime("%H:%M:%S"),
        image_path=alert_data['image_path']
    )

# When done monitoring, generate and send
result = generate_session_report(
    total_students=30,
    active_ids=28,
    total_alerts=5,
    normal_students=23,
    monitoring_time="00:45:30",
    send_email=True,      # Send to email
    clear_logs=True       # Clear logs after
)

print(f"✅ Report: {result['report_path']}")
print(f"📧 Email: {result['email_sent']}")
print(f"🧹 Logs cleared: {result['logs_cleared']}")
```

---

## 🔌 Integration with API Server

### Add to top of api_server.py:
```python
from report_integration import initialize_report_system, log_alert_to_report, generate_session_report
```

### In surveillance_loop() when alert detected:
```python
# When decision agent triggers alert
if dec.should_alert:
    log_alert_to_report(
        student_id=tid,
        behavior_type=score_data.get("situation", "Unknown"),
        timestamp=datetime.now().strftime("%H:%M:%S"),
        image_path=f"evidence/ID{tid}_{datetime.now().strftime('%H%M%S')}.jpg"
    )
```

### When monitoring stops:
```python
# Generate and send final report
result = generate_session_report(
    total_students=dashboard_data.total_students,
    active_ids=len(dashboard_data.active_ids),
    total_alerts=len(dashboard_data.alerts),
    normal_students=max(0, dashboard_data.total_students - len(dashboard_data.alerts)),
    monitoring_time=dashboard_data.monitoring_time,
    send_email=True,
    clear_logs=True
)

if result['success']:
    print(f"✅ Report generated and sent")
else:
    print(f"⚠️ Report issue: {result['message']}")
```

### At startup:
```python
if __name__ == '__main__':
    print("🔧 Starting AI Exam Surveillance Dashboard API Server...")
    
    # Initialize report system
    initialize_report_system()  # Uses environment variables
    
    # Rest of startup code...
```

---

## 📊 Data Format Reference

### Alert Log Entry
```python
{
    "id": 3,              # Student tracking ID
    "type": "Using Mobile",  # Behavior type
    "time": "10:05:12",   # Time (HH:MM:SS)
    "image_path": "evidence/ID3_100512.jpg"  # Evidence image
}
```

### Summary Data
```python
{
    "total_students": 30,    # Total students in exam
    "active_ids": 28,        # Students detected
    "total_alerts": 5,       # Suspicious behaviors
    "normal_students": 23,   # Students with no alerts
    "monitoring_time": "00:45:30"  # Duration (HH:MM:SS)
}
```

---

## 🧪 Testing Without Email

Test report generation without email setup:

```bash
python report_system.py
```

This will generate a test PDF report in `reports/` folder.

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| "App password not found" | Check environment variables set correctly |
| "Authentication failed" | Use app password, not regular Gmail password |
| "No alerts in report" | Check `logs/alerts_log.json` has entries |
| "Images not in PDF" | Verify image paths are correct and files exist |
| "Email not sent" | Check internet connection and Gmail settings |

---

## ✅ Verification Checklist

- [ ] Dependencies installed (`pip install reportlab pillow`)
- [ ] Environment variables set
- [ ] Gmail 2-Step Verification enabled
- [ ] App password created and copied
- [ ] Test report generated successfully
- [ ] Email sent successfully to test recipient
- [ ] Alert log created in `logs/` folder
- [ ] Reports generated in `reports/` folder

---

## 📂 Files Created

| File | Purpose |
|------|---------|
| `report_system.py` | Main report generation module |
| `report_integration.py` | Integration functions |
| `logs/alerts_log.json` | Real-time alert log |
| `reports/*.pdf` | Generated reports |

---

## 🎯 Next Steps

1. **Setup Gmail** (5 min)
   - Get app password
   - Set environment variables

2. **Test Report Generation** (2 min)
   - Run `python report_system.py`
   - Check `reports/` folder

3. **Integrate with API** (10 min)
   - Add imports to api_server.py
   - Add logging calls
   - Add final report generation

4. **Test Full Pipeline** (5 min)
   - Run surveillance system
   - Trigger some alerts
   - Check email receipt

---

## 🚀 One-Line Summary

```
Initialize system → Log alerts during monitoring → Generate & send report when done → Logs auto-cleared
```

---

**Ready to go! Let's build reports.** 📊✉️
