"""
AI Exam Surveillance - Report Generation & Email System
Real-time log processing, PDF generation, and automated email delivery
"""

from __future__ import annotations
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.encoders import encode_base64
import logging

# PDF Generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, 
    PageBreak, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage

# ===================================================
# LOGGING CONFIGURATION
# ===================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# ===================================================
# REPORT LOG MANAGER
# ===================================================

class AlertLogManager:
    """Manages real-time alert logging"""
    
    def __init__(self, log_file: str = "logs/alerts_log.json"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_log()
    
    def _initialize_log(self):
        """Initialize log file if it doesn't exist"""
        if not self.log_file.exists():
            self._save_log([])
            logger.info(f"📝 Initialized alert log: {self.log_file}")
    
    def _save_log(self, alerts: List[Dict]):
        """Save alerts to JSON file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(alerts, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving log: {e}")
    
    def add_alert(self, alert: Dict[str, Any]):
        """Add an alert to the log"""
        try:
            alerts = self.get_alerts()
            alerts.append(alert)
            self._save_log(alerts)
            logger.info(f"✅ Alert logged: ID {alert.get('id')} - {alert.get('type')}")
        except Exception as e:
            logger.error(f"❌ Error adding alert: {e}")
    
    def get_alerts(self) -> List[Dict]:
        """Get all logged alerts"""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"❌ Error reading alerts: {e}")
            return []
    
    def clear_alerts(self):
        """Clear all logged alerts"""
        try:
            self._save_log([])
            logger.info("🧹 Alert log cleared")
        except Exception as e:
            logger.error(f"❌ Error clearing alerts: {e}")
    
    def get_alert_count(self) -> int:
        """Get count of alerts"""
        return len(self.get_alerts())


# ===================================================
# PDF REPORT GENERATOR
# ===================================================

class ReportGenerator:
    """Generates professional PDF reports with evidence"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Heading style
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        ))
        
        # Alert item style
        self.styles.add(ParagraphStyle(
            name='AlertItem',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#e74c3c'),
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
    
    def _resize_image(self, image_path: str, max_width: float = 5.5, max_height: float = 4) -> str:
        """Resize image to fit in report"""
        try:
            img = PILImage.open(image_path)
            img.thumbnail((int(max_width * 72), int(max_height * 72)), PILImage.Resampling.LANCZOS)
            
            # Save resized image
            resized_path = Path(image_path).stem + "_resized.jpg"
            img.save(resized_path, quality=85)
            return resized_path
        except Exception as e:
            logger.warning(f"⚠️ Could not resize image {image_path}: {e}")
            return None
    
    def _image_exists(self, image_path: str) -> bool:
        """Check if image exists"""
        return Path(image_path).exists()
    
    def generate_report(
        self,
        alerts_log: List[Dict],
        summary_data: Dict[str, Any],
        session_name: str = None
    ) -> str:
        """
        Generate comprehensive PDF report
        
        Args:
            alerts_log: List of alert dictionaries
            summary_data: Dictionary with monitoring session summary
            session_name: Optional custom session name
        
        Returns:
            Path to generated report
        """
        try:
            # Generate report filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = session_name or f"Surveillance_Report_{timestamp}"
            report_path = self.output_dir / f"{session_name}.pdf"
            
            logger.info(f"📄 Generating report: {report_path}")
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(report_path),
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )
            
            story = []
            
            # 1. HEADER SECTION
            story.extend(self._create_header(summary_data))
            
            # 2. SUMMARY SECTION
            story.extend(self._create_summary(summary_data))
            
            # 3. ALERT TABLE
            if alerts_log:
                story.append(Spacer(1, 0.3*inch))
                story.extend(self._create_alert_table(alerts_log))
            
            # 4. EVIDENCE SECTION
            story.append(Spacer(1, 0.3*inch))
            story.extend(self._create_evidence_section(alerts_log))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"✅ Report generated successfully: {report_path}")
            return str(report_path)
        
        except Exception as e:
            logger.error(f"❌ Error generating report: {e}")
            raise
    
    def _create_header(self, summary_data: Dict) -> List:
        """Create report header section"""
        elements = []
        
        # Title
        title = Paragraph("AI EXAM SURVEILLANCE REPORT", self.styles['CustomTitle'])
        elements.append(title)
        
        # Date and Time
        now = datetime.now()
        date_str = now.strftime("%B %d, %Y at %I:%M %p")
        date_para = Paragraph(f"<b>Generated:</b> {date_str}", self.styles['Normal'])
        elements.append(date_para)
        
        # Session info
        monitoring_time = summary_data.get('monitoring_time', 'N/A')
        session_info = Paragraph(
            f"<b>Monitoring Duration:</b> {monitoring_time}",
            self.styles['Normal']
        )
        elements.append(session_info)
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Divider
        elements.append(self._create_divider())
        
        return elements
    
    def _create_summary(self, summary_data: Dict) -> List:
        """Create summary statistics section"""
        elements = []
        
        elements.append(Spacer(1, 0.2*inch))
        heading = Paragraph("MONITORING SUMMARY", self.styles['CustomHeading'])
        elements.append(heading)
        
        # Summary table
        total_students = summary_data.get('total_students', 0)
        active_ids = summary_data.get('active_ids', 0)
        total_alerts = summary_data.get('total_alerts', 0)
        normal_students = summary_data.get('normal_students', 0)
        
        summary_data_list = [
            ['Metric', 'Count'],
            ['Total Students', str(total_students)],
            ['Students Detected', str(active_ids)],
            ['Total Alerts', str(total_alerts)],
            ['Normal Students', str(normal_students)],
        ]
        
        table = Table(summary_data_list, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_alert_table(self, alerts_log: List[Dict]) -> List:
        """Create alerts table"""
        elements = []
        
        heading = Paragraph("SUSPICIOUS ACTIVITY LOG", self.styles['CustomHeading'])
        elements.append(heading)
        
        # Alert table data
        table_data = [['Student ID', 'Behavior', 'Time']]
        
        for alert in alerts_log:
            table_data.append([
                str(alert.get('id', 'N/A')),
                str(alert.get('type', 'N/A')),
                str(alert.get('time', 'N/A'))
            ])
        
        table = Table(table_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fadbd8')]),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_evidence_section(self, alerts_log: List[Dict]) -> List:
        """Create evidence section with images"""
        elements = []
        
        elements.append(Spacer(1, 0.3*inch))
        heading = Paragraph("EVIDENCE (TIME-BASED)", self.styles['CustomHeading'])
        elements.append(heading)
        
        if not alerts_log:
            no_alerts = Paragraph(
                "<b>✅ No suspicious activity detected</b>",
                self.styles['Normal']
            )
            elements.append(no_alerts)
            return elements
        
        # Limit to top 10 alerts
        alerts_to_show = alerts_log[-10:]
        
        for idx, alert in enumerate(alerts_to_show):
            try:
                # Alert header
                alert_id = alert.get('id', 'N/A')
                alert_type = alert.get('type', 'N/A')
                alert_time = alert.get('time', 'N/A')
                
                alert_header = Paragraph(
                    f"<b>Student ID:</b> {alert_id} | <b>Behavior:</b> {alert_type} | <b>Time:</b> {alert_time}",
                    self.styles['AlertItem']
                )
                elements.append(alert_header)
                
                # Try to include image
                image_path = alert.get('image_path')
                if image_path and self._image_exists(image_path):
                    try:
                        resized = self._resize_image(image_path)
                        if resized:
                            img = Image(resized, width=5.5*inch, height=4*inch)
                            elements.append(img)
                            
                            # Clean up resized image
                            try:
                                os.remove(resized)
                            except:
                                pass
                    except Exception as e:
                        logger.warning(f"⚠️ Could not include image: {e}")
                
                elements.append(Spacer(1, 0.2*inch))
                
                # Page break after every 3 items (except last)
                if (idx + 1) % 3 == 0 and idx < len(alerts_to_show) - 1:
                    elements.append(PageBreak())
            
            except Exception as e:
                logger.warning(f"⚠️ Error processing alert {idx}: {e}")
                continue
        
        return elements
    
    def _create_divider(self):
        """Create a visual divider"""
        divider_style = [
            ('ALIGNMENT', (0, 0), (-1, -1), 'CENTER'),
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#bdc3c7')),
        ]
        table = Table([['_' * 60]], colWidths=[6*inch])
        table.setStyle(TableStyle(divider_style))
        return table


# ===================================================
# EMAIL SENDER
# ===================================================

class EmailSender:
    """Sends reports via Gmail SMTP"""
    
    def __init__(
        self,
        sender_email: str = None,
        app_password: str = None,
        recipient_email: str = "shravanwargantiwar@gmail.com"
    ):
        """
        Initialize email sender
        
        Args:
            sender_email: Gmail address
            app_password: Gmail app password (16-char)
            recipient_email: Recipient email address
        """
        self.sender_email = sender_email or os.getenv('SURVEILLANCE_EMAIL')
        self.app_password = app_password or os.getenv('SURVEILLANCE_APP_PASSWORD')
        self.recipient_email = recipient_email
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
    
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        if not self.sender_email:
            logger.error("❌ Sender email not configured")
            return False
        if not self.app_password:
            logger.error("❌ App password not configured")
            return False
        return True
    
    def send_report(self, report_path: str, subject: str = None) -> bool:
        """
        Send report via email
        
        Args:
            report_path: Path to PDF report
            subject: Email subject line
        
        Returns:
            Success status
        """
        if not self._validate_config():
            logger.warning("⚠️ Email not configured. Report generated but not sent.")
            return False
        
        try:
            logger.info(f"📧 Sending report to {self.recipient_email}...")
            
            # Check report exists
            if not Path(report_path).exists():
                logger.error(f"❌ Report file not found: {report_path}")
                return False
            
            # Create message
            message = MIMEMultipart()
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            message['Subject'] = subject or "AI Exam Surveillance Report"
            
            # Email body
            body = """
Hello,

Please find attached the AI Exam Surveillance Report from the recent monitoring session.

Report Details:
- Generated: {timestamp}
- Contains detailed alert logs and evidence

Best regards,
AI Surveillance System
            """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            message.attach(MIMEText(body, 'plain'))
            
            # Attach PDF
            with open(report_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {Path(report_path).name}'
                )
                message.attach(part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.app_password)
                server.send_message(message)
            
            logger.info(f"✅ Report sent successfully to {self.recipient_email}")
            return True
        
        except smtplib.SMTPAuthenticationError:
            logger.error("❌ Authentication failed. Check email and app password.")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False


# ===================================================
# MAIN REPORT PIPELINE
# ===================================================

class ReportPipeline:
    """Complete report generation and delivery pipeline"""
    
    def __init__(
        self,
        sender_email: str = None,
        app_password: str = None,
        recipient_email: str = "shravanwargantiwar@gmail.com"
    ):
        self.alert_logger = AlertLogManager()
        self.report_generator = ReportGenerator()
        self.email_sender = EmailSender(sender_email, app_password, recipient_email)
    
    def add_alert(self, alert: Dict[str, Any]):
        """Add alert to log (called from surveillance system)"""
        self.alert_logger.add_alert(alert)
    
    def generate_and_send_report(
        self,
        summary_data: Dict[str, Any],
        send_email: bool = True,
        clear_logs: bool = True
    ) -> Dict[str, Any]:
        """
        Complete pipeline: generate report, send email, clear logs
        
        Args:
            summary_data: Monitoring session summary
            send_email: Whether to send email
            clear_logs: Whether to clear logs after sending
        
        Returns:
            Status dictionary
        """
        status = {
            'success': False,
            'report_path': None,
            'email_sent': False,
            'logs_cleared': False,
            'message': None
        }
        
        try:
            # Get current alerts
            alerts = self.alert_logger.get_alerts()
            alert_count = len(alerts)
            
            logger.info(f"📊 Processing {alert_count} alerts for report generation")
            
            # Generate report
            report_path = self.report_generator.generate_report(
                alerts,
                summary_data,
                session_name=f"Surveillance_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            status['report_path'] = report_path
            
            # Send email if configured
            if send_email:
                email_sent = self.email_sender.send_report(report_path)
                status['email_sent'] = email_sent
            
            # Clear logs
            if clear_logs:
                self.alert_logger.clear_alerts()
                status['logs_cleared'] = True
            
            status['success'] = True
            status['message'] = f"Report generated ({alert_count} alerts), email sent: {send_email}, logs cleared: {clear_logs}"
            
            logger.info(f"✅ Report pipeline completed: {status['message']}")
        
        except Exception as e:
            status['message'] = f"Error in report pipeline: {e}"
            logger.error(f"❌ {status['message']}")
        
        return status


# ===================================================
# STANDALONE TEST FUNCTION
# ===================================================

def test_report_generation():
    """Test report generation with sample data"""
    logger.info("🧪 Testing report generation...")
    
    # Sample alerts (from real monitoring)
    sample_alerts = [
        {
            "id": 3,
            "type": "Using Mobile",
            "time": "10:05:12",
            "image_path": "evidence/sample_1.jpg"
        },
        {
            "id": 7,
            "type": "Looking Around",
            "time": "10:10:30",
            "image_path": "evidence/sample_2.jpg"
        },
        {
            "id": 12,
            "type": "Leaning to Copy",
            "time": "10:15:45",
            "image_path": "evidence/sample_3.jpg"
        }
    ]
    
    # Summary data
    summary_data = {
        "total_students": 30,
        "active_ids": 28,
        "total_alerts": 3,
        "normal_students": 25,
        "monitoring_time": "00:15:30"
    }
    
    # Generate report (without email for testing)
    generator = ReportGenerator()
    report_path = generator.generate_report(sample_alerts, summary_data)
    
    logger.info(f"📄 Test report generated: {report_path}")
    return report_path


if __name__ == "__main__":
    # Test the system
    test_report_generation()
