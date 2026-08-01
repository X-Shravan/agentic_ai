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
    
    def send_report(self, recipient_email, report_path, subject=None, body=None):
        """
        Send surveillance report via email.
        
        Args:
            recipient_email (str): Email address to send to
            report_path (str): Path to PDF report
            subject (str): Email subject (optional)
            body (str): Email body (optional)
        
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

This report contains:
• Session summary statistics
• Alert details and timeline
• Evidence images for suspicious activities

For any concerns or questions regarding the monitoring results, please review the attached report.

Best regards,
AI Exam Surveillance System
"""
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = subject
            
            # Attach body
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach PDF
            with open(report_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(report_path)}')
            msg.attach(part)
            
            # Send email
            print(f"\n📧 Connecting to {self.smtp_server}:{self.smtp_port}...")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Start TLS encryption
                server.starttls()
                print("✅ TLS connection established")
                
                # Login
                server.login(self.sender_email, self.app_password)
                print(f"✅ Authenticated as {self.sender_email}")
                
                # Send email
                server.send_message(msg)
                print(f"✅ Email sent to {recipient_email}")
                
            print(f"✅ Report successfully emailed!\n")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print(f"❌ Authentication failed!")
            print("   • Check your Gmail address")
            print("   • Verify App Password (NOT your regular Gmail password)")
            print("   • Ensure 'Less secure app access' is disabled")
            return False
            
        except smtplib.SMTPException as e:
            print(f"❌ SMTP error: {e}")
            return False
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False


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
load_dotenv()
def interactive_setup():
    """Load email configuration from .env and test it"""

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
