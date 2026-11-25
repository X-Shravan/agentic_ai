"""
Automated Email Sender for AI Exam Surveillance Reports
Sends PDF reports via Gmail with app password authentication
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, List



class SurveillanceEmailSender:
    """Send surveillance reports via email"""
    
    def __init__(self, sender_email, app_password, smtp_server="smtp.gmail.com", smtp_port=587):
        """
        Initialize email sender.
        
        Args:
            sender_email (str): Gmail address to send from
            app_password (str): Gmail App Password (NOT regular password)
            smtp_server (str): SMTP server address
            smtp_port (int): SMTP server port
        """
        self.sender_email = sender_email
        self.app_password = app_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
    
    def send_report(self, recipient_email, report_path, subject=None, body=None, attachments=None, html_body=None, evidence_image=None):
        """
        Send surveillance report via email.
        
        Args:
            recipient_email (str): Email address to send to
            report_path (str): Path to PDF report
            subject (str): Email subject (optional)
            body (str): Email body (optional)
            attachments (list[str]): Optional list of paths to attach (images, videos, etc.)
            html_body (str): Rich HTML body (optional)
            evidence_image (str): Path to evidence image for inline display (optional)
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        
        # Validate inputs
        if not os.path.exists(report_path):
            print(f"❌ Report file not found: {report_path}")
            return False
        
        # Default subject and body
        if subject is None:
            subject = "🎓 AI Exam Surveillance Report"
        
        if body is None:
            report_date = datetime.now().strftime("%B %d, %Y at %H:%M")
            body = f"""
Dear Administrator,

Please find attached the AI Exam Surveillance Report generated on {report_date}.

Best regards,
AI Exam Surveillance System
"""
        
        try:
            # Create email message (mixed for attachments)
            msg = MIMEMultipart('mixed')
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = subject
            
            # Create alternative body part (for text and HTML)
            body_part = MIMEMultipart('alternative')
            body_part.attach(MIMEText(body, 'plain'))
            if html_body:
                body_part.attach(MIMEText(html_body, 'html'))
            msg.attach(body_part)
            
            # Attach PDF
            with open(report_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(report_path)}')
            msg.attach(part)

            # Attach extra attachments if provided
            if attachments:
                for path in attachments:
                    if path and os.path.exists(path):
                        try:
                            filename = os.path.basename(path)
                            with open(path, 'rb') as f:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename={filename}')
                            
                            # Inline image handling using CID
                            if evidence_image and os.path.abspath(path) == os.path.abspath(evidence_image):
                                part.add_header('Content-ID', '<evidence_img>')
                                
                            msg.attach(part)
                            print(f"Attachment added: {filename}")
                        except Exception as e:
                            print(f"Failed to attach {path}: {e}")
            
            # Send email
            print(f"\nConnecting to {self.smtp_server}:{self.smtp_port}...")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Start TLS encryption
                server.starttls()
                print("TLS connection established")
                
                # Login
                server.login(self.sender_email, self.app_password)
                print(f"Authenticated as {self.sender_email}")
                
                # Send email
                server.send_message(msg)
                print(f"Email sent to {recipient_email}")
                
            print(f"Report successfully emailed!\n")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print(f"Authentication failed!")
            print("   • Check your Gmail address")
            print("   • Verify App Password (NOT your regular Gmail password)")
            print("   • Ensure 'Less secure app access' is disabled")
            return False
            
        except smtplib.SMTPException as e:
            print(f"SMTP error: {e}")
            return False
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False


import threading
import time

def send_email_with_retries(
    recipient_email: str,
    pdf_path: str,
    student_id: str,
    camera_id: str,
    behaviour: str,
    risk_score: float,
    timestamp: str,
    gemini_explanation: Optional[str] = None,
    crew_decision: Optional[str] = None,
    evidence_image: Optional[str] = None,
    evidence_video: Optional[str] = None,
    report_id: Optional[str] = None,
    behaviors: Optional[List[str]] = None,
    confidence: float = 0.90
):
    """Sends incident reports asynchronously with 10s, 30s, 60s retry logic."""
    def worker():
        # Load env variables (if not loaded)
        _load_project_environment()
        
        sender_email = os.getenv("EMAIL_USER")
        app_password = os.getenv("EMAIL_PASSWORD")
        
        target_recipient = recipient_email
        # Fallback to local config file if env is empty
        if not sender_email or not app_password:
            config = EmailConfig()
            if config.is_configured():
                sender_email = config.sender_email
                app_password = config.app_password
                if not target_recipient:
                    target_recipient = config.recipient_email
        
        if not target_recipient:
            target_recipient = os.getenv("RECIPIENT_EMAIL") or sender_email
            
        if not sender_email or not app_password or not target_recipient:
            print("Email sender not configured. Cannot send email. Mark as Pending Email.")
            if report_id:
                try:
                    from backend.database.store import store
                    report = next((item for item in store.list("reports") if item.get("report_id") == report_id), None)
                    if report:
                        report["email_status"] = "failed_pending"
                        store.upsert("reports", "report_id", report)
                except Exception as ex:
                    print(f"Database update failed: {ex}")
            return False
            
        subject = f"AI Exam Surveillance Alert - Student {student_id}"
        
        # Format behaviors list
        behaviors_list_html = ""
        if behaviors:
            behaviors_list_html = "".join([f"<li style='margin-bottom: 5px;'>{str(b).replace('_', ' ').title()}</li>" for b in behaviors])
        else:
            behaviors_list_html = f"<li style='margin-bottom: 5px;'>{behaviour.replace('_', ' ').title()}</li>"
            
        # Parse ids and values
        parts = student_id.split('_')
        track_id = parts[-1] if len(parts) > 1 else student_id
        evidence_id = Path(evidence_image).stem if evidence_image else "N/A"
        
        # Risk level mapping
        risk_level = "LOW"
        risk_level_class = "low"
        if risk_score >= 90:
            risk_level = "CRITICAL"
            risk_level_class = "critical"
        elif risk_score >= 75:
            risk_level = "HIGH"
            risk_level_class = "high"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            risk_level_class = "medium"
            
        risk_score_str = f"{risk_score:.1f} / 100 ({risk_level})"
        
        # Inline evidence image HTML
        image_html = ""
        if evidence_image and os.path.exists(evidence_image):
            image_html = f"""
            <div class="section-title">Evidence screenshot</div>
            <div class="image-box">
                <img src="cid:evidence_img" alt="Evidence Bounding Box Screenshot" />
            </div>
            """
        
        # HTML template
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        .header {{ background-color: #1A365D; color: #ffffff; padding: 25px 20px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; letter-spacing: 0.5px; }}
        .header p {{ margin: 5px 0 0 0; font-size: 14px; opacity: 0.8; }}
        .content {{ padding: 20px; background-color: #ffffff; }}
        .summary-box {{ background-color: #f7fafc; border: 1px solid #edf2f7; border-radius: 6px; padding: 15px; margin-bottom: 20px; }}
        .summary-title {{ font-weight: bold; font-size: 15px; color: #2d3748; margin-top: 0; margin-bottom: 10px; border-bottom: 1px solid #edf2f7; padding-bottom: 5px; }}
        .grid {{ display: table; width: 100%; }}
        .row {{ display: table-row; }}
        .label {{ display: table-cell; font-weight: 600; color: #4a5568; padding: 6px 0; width: 35%; font-size: 14px; }}
        .value {{ display: table-cell; color: #2d3748; padding: 6px 0; font-size: 14px; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; color: #ffffff; text-transform: uppercase; }}
        .badge-critical {{ background-color: #E53E3E; }}
        .badge-high {{ background-color: #DD6B20; }}
        .badge-medium {{ background-color: #D69E2E; }}
        .badge-low {{ background-color: #38A169; }}
        .section-title {{ font-size: 16px; font-weight: 600; color: #1A365D; margin-top: 20px; margin-bottom: 10px; border-left: 4px solid #2B6CB0; padding-left: 10px; }}
        .text-content {{ font-size: 14px; color: #2d3748; line-height: 1.6; background-color: #f8fafc; border-left: 3px solid #cbd5e1; padding: 12px; border-radius: 4px; white-space: pre-wrap; font-family: monospace; }}
        .decision-box {{ background-color: #ebf8ff; border: 1px solid #bee3f8; border-left: 4px solid #3182ce; border-radius: 4px; padding: 12px; margin-top: 15px; font-size: 14px; color: #2b6cb0; font-weight: 600; }}
        .image-box {{ text-align: center; margin-top: 10px; }}
        .image-box img {{ max-width: 100%; border-radius: 4px; border: 1px solid #edf2f7; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        .footer {{ background-color: #edf2f7; color: #718096; text-align: center; padding: 15px; font-size: 12px; border-top: 1px solid #e2e8f0; }}
        ul {{ margin: 0; padding-left: 20px; }}
        li {{ margin-bottom: 5px; font-size: 14px; color: #2d3748; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Exam Surveillance Incident Alert</h1>
            <p>Automated Proctoring & Invigilation System</p>
        </div>
        <div class="content">
            <div class="summary-box">
                <div class="summary-title">Incident Summary</div>
                <div class="grid">
                    <div class="row">
                        <div class="label">Student ID:</div>
                        <div class="value">{student_id}</div>
                    </div>
                    <div class="row">
                        <div class="label">Track ID:</div>
                        <div class="value">{track_id}</div>
                    </div>
                    <div class="row">
                        <div class="label">Camera ID:</div>
                        <div class="value">{camera_id}</div>
                    </div>
                    <div class="row">
                        <div class="label">Evidence ID:</div>
                        <div class="value">{evidence_id}</div>
                    </div>
                    <div class="row">
                        <div class="label">Confidence:</div>
                        <div class="value">{confidence:.2f}</div>
                    </div>
                    <div class="row">
                        <div class="label">Risk Score:</div>
                        <div class="value">
                            <span class="badge badge-{risk_level_class}">{risk_score_str}</span>
                        </div>
                    </div>
                    <div class="row">
                        <div class="label">Timestamp:</div>
                        <div class="value">{timestamp}</div>
                    </div>
                </div>
            </div>

            <div class="section-title">Primary Incident</div>
            <p style="font-size: 14px; font-weight: 600; color: #2d3748; margin-top: 5px; margin-bottom: 15px;">{behaviour}</p>

            <div class="section-title">Detected Behaviours</div>
            <ul>
                {behaviors_list_html}
            </ul>

            <div class="section-title">Gemini AI Explanation</div>
            <div class="text-content">{gemini_explanation or 'No AI explanation available.'}</div>

            <div class="section-title">CrewAI Invigilation Decision</div>
            <div class="decision-box">
                🛡️ Decision: {crew_decision or 'No CrewAI decision recorded.'}
            </div>

            {image_html}
        </div>
        <div class="footer">
            This is an automated notification. Please review the attached PDF report for full compliance details.
        </div>
    </div>
</body>
</html>
"""

        body = f"""AI Exam Surveillance Alert

============================================================
INCIDENT SUMMARY
============================================================
Student ID:        {student_id}
Camera ID:         {camera_id}
Detected Event:    {behaviour}
Risk Score:        {risk_score_str}
Timestamp:         {timestamp}
============================================================

Gemini AI Explanation:
------------------------------------------------------------
{gemini_explanation or 'No AI explanation available.'}

CrewAI Invigilation Decision:
------------------------------------------------------------
{crew_decision or 'No CrewAI decision recorded.'}

============================================================
Attachments included:
• PDF Incident Report
• Evidence Image
• Short Video Clip
============================================================
"""
        # Gather attachments
        attachments = []
        if pdf_path and os.path.exists(pdf_path):
            # Report agent output is the primary attachment
            attachments.append(pdf_path)
        if evidence_image and os.path.exists(evidence_image):
            attachments.append(evidence_image)
        if evidence_video and os.path.exists(evidence_video):
            attachments.append(evidence_video)
            
        sender = SurveillanceEmailSender(sender_email, app_password)
        
        delays = [10, 30, 60]
        max_attempts = 4
        
        # Mark as sending
        try:
            from backend.database.store import store
            if report_id:
                report = next((item for item in store.list("reports") if item.get("report_id") == report_id), None)
                if report:
                    report["email_status"] = "sending"
                    store.upsert("reports", "report_id", report)
        except Exception as ex:
            print(f"Database update failed: {ex}")
                
        for attempt in range(max_attempts):
            print(f"Attempt {attempt + 1}: Sending alert email to {target_recipient}...")
            try:
                success = sender.send_report(
                    recipient_email=target_recipient,
                    report_path=pdf_path,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                    html_body=html_body,
                    evidence_image=evidence_image
                )
                if success:
                    print(f"Alert email delivered successfully on attempt {attempt + 1}")
                    if report_id:
                        report = next((item for item in store.list("reports") if item.get("report_id") == report_id), None)
                        if report:
                            report["email_status"] = "sent"
                            store.upsert("reports", "report_id", report)
                    return True
            except Exception as e:
                print(f"Attempt {attempt + 1} failed with error: {e}")
                
            if attempt < len(delays):
                delay = delays[attempt]
                print(f"Retry {attempt + 1} scheduled in {delay} seconds...")
                time.sleep(delay)
                
        print(f"All {max_attempts} email attempts failed. Report marked as Pending Email.")
        try:
            if report_id:
                report = next((item for item in store.list("reports") if item.get("report_id") == report_id), None)
                if report:
                    report["email_status"] = "failed_pending"
                    store.upsert("reports", "report_id", report)
        except Exception as ex:
            print(f"Database update failed: {ex}")
        return False

    # Start the worker thread
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


# ================================================================
# CONFIGURATION CLASS
# ================================================================

class EmailConfig:
    """Email configuration management"""
    
    def __init__(self, config_file="email_config.txt"):
        """
        Initialize email configuration.
        
        Args:
            config_file (str): Path to configuration file
        """
        self.config_file = config_file
        self.sender_email = None
        self.app_password = None
        self.recipient_email = None
        
        # Try to load from file
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.startswith('SENDER_EMAIL='):
                            self.sender_email = line.split('=', 1)[1].strip()
                        elif line.startswith('APP_PASSWORD='):
                            self.app_password = line.split('=', 1)[1].strip()
                        elif line.startswith('RECIPIENT_EMAIL='):
                            self.recipient_email = line.split('=', 1)[1].strip()
                
                if self.sender_email and self.app_password:
                    print(f"✅ Email config loaded from {self.config_file}")
                    return True
            except Exception as e:
                print(f"⚠️ Error loading config: {e}")
        
        return False
    
    def save_config(self, sender_email, app_password, recipient_email):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                f.write(f"SENDER_EMAIL={sender_email}\n")
                f.write(f"APP_PASSWORD={app_password}\n")
                f.write(f"RECIPIENT_EMAIL={recipient_email}\n")
            
            self.sender_email = sender_email
            self.app_password = app_password
            self.recipient_email = recipient_email
            
            print(f"✅ Config saved to {self.config_file}")
            return True
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False
    
    def is_configured(self):
        """Check if email is properly configured"""
        return self.sender_email and self.app_password


# ================================================================
# STANDALONE FUNCTIONS FOR INTEGRATION
# ================================================================

def send_report_email(report_path, recipient_email, 
                     sender_email=None, app_password=None,
                     subject=None, body=None):
    """
    Send surveillance report via email (standalone function).
    
    Args:
        report_path (str): Path to PDF report
        recipient_email (str): Email to send to
        sender_email (str): Sender Gmail address
        app_password (str): Gmail App Password
        subject (str): Email subject
        body (str): Email body
    
    Returns:
        bool: True if sent successfully
    """
    
    # Load config if credentials not provided
    if sender_email is None or app_password is None:
        config = EmailConfig()
        if config.is_configured():
            sender_email = config.sender_email
            app_password = config.app_password
            if recipient_email is None:
                recipient_email = config.recipient_email
        else:
            print("❌ Email credentials not provided and config not found")
            return False
    
    # Create sender and send
    sender = SurveillanceEmailSender(sender_email, app_password)
    return sender.send_report(recipient_email, report_path, subject, body)


def setup_email_config(sender_email, app_password, recipient_email):
    """
    Setup email configuration for future use.
    
    Args:
        sender_email (str): Gmail address
        app_password (str): Gmail App Password
        recipient_email (str): Default recipient email
    
    Returns:
        bool: True if setup successful
    """
    config = EmailConfig()
    return config.save_config(sender_email, app_password, recipient_email)


# ================================================================
# COMMAND-LINE SETUP
# ================================================================


def _load_project_environment():
    """Load the project .env file with precedence over existing shell variables."""

    env_path = Path(__file__).resolve().parent / ".env"

    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        return env_path

    # Fall back to any environment already present if .env is unavailable.
    load_dotenv(override=False)
    return None


def interactive_setup():
    """Load email configuration from .env and test it"""

    env_path = _load_project_environment()

    sender_email = os.getenv("EMAIL_USER")
    app_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")

    # Validate
    if not sender_email:
        print("❌ EMAIL_USER not found in .env")
        return False

    if not app_password:
        print("❌ EMAIL_PASSWORD not found in .env")
        return False

    if not recipient_email:
        recipient_email = sender_email

    if env_path:
        print(f"✅ Loaded email settings from {env_path.name}")

    print("\n" + "=" * 60)
    print("📧 AI SURVEILLANCE EMAIL SETUP")
    print("=" * 60)

    print(f"\n📤 Sender Email    : {sender_email}")
    print(f"📥 Recipient Email : {recipient_email}")

    print("\n🔧 Testing email configuration...")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)

        print("✅ Authentication successful!")

        if setup_email_config(
            sender_email,
            app_password,
            recipient_email
        ):
            print("\n✅ Email configuration loaded successfully!")
            print(f"📧 Reports will be sent to: {recipient_email}")
            return True

    except Exception as e:
        print(f"❌ Test failed: {e}")

        print("\nPlease check:")
        print("  • EMAIL_USER is correct")
        print("  • EMAIL_PASSWORD is Gmail App Password")
        print("  • 2-Step Verification is enabled")
        print("  • App Password is active")

        return False


if __name__ == "__main__":
    interactive_setup()
