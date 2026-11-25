# Reports And Email Setup Guide

This guide covers the report generation and email delivery pieces of the AI Exam Surveillance project.

## What This Setup Provides

- Collects real surveillance alerts with `alert_logger.py`.
- Generates PDF reports with `report_generator.py` and `reportlab`.
- Sends reports through Gmail SMTP with `email_sender.py`.
- Stores runtime files in `logs/`, `reports/`, `evidence/`, and `archived_reports/`.

## Prerequisites

- Python 3.10 or newer available on `PATH`.
- A project virtual environment, usually `.venv`.
- Dependencies from `requirements.txt` installed.
- Gmail account with 2-Step Verification enabled if email delivery is required.
- Gmail App Password for SMTP authentication; do not use your regular Gmail password.

## Local Setup

Run these commands from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python setup_wizard.py
python SYSTEM_STATUS.py
```

`setup_wizard.py` creates the required runtime folders and runs component checks.

## Email Configuration

The current `email_sender.py` loads Gmail settings from `.env`, then writes `email_config.txt` after a successful SMTP login.

Create `.env` in the project root with these keys:

```env
EMAIL_USER=your.email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
RECIPIENT_EMAIL=recipient@example.com
```

Then run:

```powershell
python -c "from email_sender import interactive_setup; interactive_setup()"
```

If authentication succeeds, `email_config.txt` is created for later report sending. Keep both `.env` and `email_config.txt` private and do not commit them.

## Report Workflow

1. The surveillance loop records detections through `AlertLogger`.
2. Evidence images are saved under `evidence/` when available.
3. Session data is persisted in `logs/current_session.json`.
4. `generate_report(alerts, summary)` creates a PDF in `reports/`.
5. `send_report_email(report_path, recipient_email)` emails the PDF.
6. Logs are cleared after a successful send so the next session starts clean.

## Integration Reference

Use `MAIN_INTEGRATION_TEMPLATE.py` for copy-paste snippets. The core imports are:

```python
from alert_logger import AlertLogger
from report_generator import generate_report
from email_sender import send_report_email
```

Typical session setup:

```python
alert_logger = AlertLogger("logs", "current_session.json")
alert_logger.update_student_count(30)
```

Typical report generation:

```python
alerts = alert_logger.get_alerts()
summary = alert_logger.get_summary(total_students=30)
report_path = generate_report(alerts, summary)
if send_report_email(report_path, recipient_email=None):
    alert_logger.clear_logs()
```

## Verification Commands

```powershell
python SYSTEM_STATUS.py
python TEST_SETUP.py
python test_pdf_generation.py
python test_pdf_reports.py
```

`SYSTEM_STATUS.py` should show all required files, documentation, directories, and core Python modules as present.

## Troubleshooting

- If `reportlab` is missing, rerun `python -m pip install -r requirements.txt` inside `.venv`.
- If `dotenv` is missing, install dependencies again; `python-dotenv` is required by `email_sender.py`.
- If Gmail login fails, confirm 2-Step Verification is enabled and regenerate the App Password.
- If reports are not created, confirm `reports/` exists and is writable.
- If evidence images are missing, confirm detection code writes image paths under `evidence/`.
