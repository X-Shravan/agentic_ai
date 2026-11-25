# Setup Completion Notes

The local setup has been prepared for the AI Exam Surveillance report and email workflow.

## Completed Locally

- The project virtual environment `.venv` exists.
- Core report dependencies are installed.
- Runtime folders are present: `logs/`, `reports/`, `evidence/`, and `archived_reports/`.
- Report/email user documentation is present in `README_REPORTS_EMAIL.md`.
- `SYSTEM_STATUS.py` is the final readiness check for the report/email setup.

## Manual Email Step

Email delivery still requires private Gmail credentials and cannot be completed automatically.

1. Enable 2-Step Verification on the Gmail sender account.
2. Generate a Gmail App Password.
3. Create `.env` in the project root:

```env
EMAIL_USER=your.email@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
RECIPIENT_EMAIL=recipient@example.com
```

4. Run:

```powershell
python -c "from email_sender import interactive_setup; interactive_setup()"
```

5. Confirm `email_config.txt` is created and keep it private.

## Verification

Run these commands after dependency or credential changes:

```powershell
python SYSTEM_STATUS.py
python TEST_SETUP.py
python test_pdf_generation.py
```

Setup is complete when `SYSTEM_STATUS.py` reports `READY FOR DEPLOYMENT` and the required email SMTP test succeeds.
