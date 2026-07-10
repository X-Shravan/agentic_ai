#!/usr/bin/env python
"""
SETUP WIZARD: AI Exam Surveillance Report & Email System
Complete one-time setup for report generation and automatic email delivery
Run this ONCE before using the reporting system
"""

import os
import sys
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def print_step(step_num, text):
    """Print formatted step"""
    print(f"\n📍 Step {step_num}: {text}")
    print("-" * 70)


def check_dependencies():
    """Check if required packages are installed"""
    print_step(1, "Checking dependencies...")
    
    required_packages = {
        'reportlab': 'PDF report generation',
        'cv2': 'OpenCV image processing',
        'numpy': 'Numerical computing',
    }
    
    missing = []
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {package:15} - {description}")
        except ImportError:
            print(f"❌ {package:15} - {description} (MISSING)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("\nInstall with:")
        print(f"   pip install {' '.join(missing)}")
        
        response = input("\nContinue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("❌ Setup cancelled")
            return False
    
    return True


def create_directories():
    """Create necessary directories"""
    print_step(2, "Creating directories...")
    
    directories = [
        "logs",
        "reports", 
        "evidence",
        "archived_reports"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Directory created: {directory}/")
    
    print(f"\n✅ All directories ready!")
    return True


def setup_email():
    """Setup email configuration"""
    print_step(3, "Email Configuration Setup")
    
    print("""
📧 This system sends PDF reports via Gmail SMTP.

⚠️  IMPORTANT - You must:
    1. Enable 2-Factor Authentication on your Gmail account
    2. Generate a Gmail App Password (NOT your regular password)
    
    Steps:
    a) Go to: https://myaccount.google.com/security
    b) Enable "2-Step Verification" (if not already enabled)
    c) Go to: https://myaccount.google.com/apppasswords
    d) Select "Mail" and "Windows Computer"
    e) Copy the 16-character password generated
    
    ⚠️  DO NOT use your regular Gmail password!
""")
    
    response = input("Do you want to setup email now? (y/n): ").strip().lower()
    
    if response != 'y':
        print("⏭️  Email setup skipped. You can setup later by running:")
        print("   python -c \"from email_sender import interactive_setup; interactive_setup()\"")
        return True
    
    print("\n" + "-"*70)
    
    # Run interactive setup
    try:
        from email_sender import interactive_setup
        return interactive_setup()
    except Exception as e:
        print(f"❌ Error during email setup: {e}")
        return False


def test_alert_logger():
    """Test alert logger functionality"""
    print_step(4, "Testing Alert Logger")
    
    try:
        from alert_logger import AlertLogger
        
        # Create test logger
        logger = AlertLogger("logs", "test_setup.json")
        
        # Add test alert
        alert = logger.add_alert(
            student_id=999,
            behavior_type="Test Alert",
            confidence=0.95,
            image_path="test_image.jpg"
        )
        
        print(f"✅ Alert logged: {alert['type']} by Student {alert['id']}")
        
        # Get summary
        summary = logger.get_summary(total_students=30)
        print(f"✅ Summary retrieved: {summary['total_alerts']} alert(s)")
        
        # Clean up test
        os.remove("logs/test_setup.json")
        print(f"✅ Test log cleaned up")
        
        return True
    except Exception as e:
        print(f"❌ Alert logger test failed: {e}")
        return False


def test_report_generator():
    """Test report generator functionality"""
    print_step(5, "Testing Report Generator")
    
    try:
        from report_generator import generate_report
        
        # Create test data
        test_alerts = [
            {
                'id': 101,
                'type': 'Mobile',
                'confidence': 0.85,
                'time': '14:30:22.123',
                'timestamp': '2024-01-15T14:30:22.123456',
                'image_path': None
            }
        ]
        
        test_summary = {
            'total_students': 30,
            'active_ids': 5,
            'total_alerts': 1,
            'normal_students': 25,
            'alert_breakdown': {'Mobile': 1},
            'session_duration': '5m 30s',
            'average_confidence': 0.85
        }
        
        # Generate test report
        report_path = generate_report(test_alerts, test_summary)
        
        if report_path and os.path.exists(report_path):
            size = os.path.getsize(report_path) / 1024  # KB
            print(f"✅ Test report generated: {report_path} ({size:.1f} KB)")
            
            # Clean up
            os.remove(report_path)
            print(f"✅ Test report cleaned up")
            return True
        else:
            print(f"❌ Report generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Report generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_email_sender():
    """Test email sender configuration"""
    print_step(6, "Testing Email Sender")
    
    try:
        from email_sender import EmailConfig
        
        config = EmailConfig()
        
        if config.is_configured():
            print(f"✅ Email configured for: {config.sender_email}")
            print(f"✅ Reports will be sent to: {config.recipient_email}")
            
            # Try to test connection
            print("\n🔧 Testing SMTP connection...")
            
            import smtplib
            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(config.sender_email, config.app_password)
                server.quit()
                print(f"✅ SMTP connection successful!")
                return True
            except Exception as e:
                print(f"⚠️  SMTP test failed: {e}")
                print("   Check your Gmail App Password and try again")
                return False
        else:
            print("⏭️  Email not yet configured")
            print("   Run: python -c \"from email_sender import interactive_setup; interactive_setup()\"")
            return True
            
    except Exception as e:
        print(f"⚠️  Error testing email: {e}")
        return False


def show_next_steps():
    """Show what to do next"""
    print_header("✅ SETUP COMPLETE!")
    
    print("""
You're all set! Here's how to use the system:

🎬 START SURVEILLANCE:
   python main.py

📊 DURING MONITORING:
   The system automatically logs all alerts

📋 STOP MONITORING & GENERATE REPORT:
   Press ESC to stop the camera
   
   The system will:
   1. Generate a PDF report from logged alerts
   2. Send the report via email
   3. Clear logs for the next session

📁 OUTPUT FILES:
   ✓ PDF Reports: reports/surveillance_report_YYYYMMDD_HHMMSS.pdf
   ✓ Alert Logs:  logs/current_session.json
   ✓ Evidence:    evidence/ID_X_situation_TIMESTAMP.jpg

⚙️  CONFIGURATION:
   Email settings: email_config.txt
   System config:  config/config.yaml

📖 DOCUMENTATION:
   • REPORT_EMAIL_INTEGRATION.py - Complete integration guide
   • README.md - General overview
   • BEHAVIOR_DETECTION_GUIDE.md - Detection details

🆘 TROUBLESHOOTING:
   If email doesn't send:
   • Check email_config.txt exists
   • Verify Gmail App Password (not regular password)
   • Ensure 2FA is enabled on Gmail
   • Check firewall/network settings
   
   If reports don't generate:
   • Check reportlab is installed: pip install reportlab
   • Verify reports/ directory is writable
   • Check evidence images exist in evidence/ directory

💡 TIPS:
   • Archive old reports in archived_reports/ after review
   • Monitor logs/ directory for alert logs
   • Keep email_config.txt secure (don't share!)

Happy monitoring! 🎓
""")


def main():
    """Run complete setup wizard"""
    
    print_header("🚀 AI EXAM SURVEILLANCE REPORT & EMAIL SYSTEM SETUP")
    
    print("""
This wizard will:
✓ Check required dependencies
✓ Create necessary directories  
✓ Setup email configuration
✓ Test all components
✓ Show you what to do next

Let's get started!
""")
    
    input("Press Enter to continue...")
    
    # Run all setup steps
    steps = [
        ("Checking dependencies", check_dependencies),
        ("Creating directories", create_directories),
        ("Setting up email", setup_email),
        ("Testing alert logger", test_alert_logger),
        ("Testing report generator", test_report_generator),
        ("Testing email sender", test_email_sender),
    ]
    
    results = []
    
    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))
        except KeyboardInterrupt:
            print("\n\n⚠️  Setup cancelled by user")
            return False
        except Exception as e:
            print(f"\n❌ Error in {step_name}: {e}")
            results.append((step_name, False))
    
    # Show results
    print_header("📋 SETUP RESULTS")
    
    all_passed = True
    for step_name, result in results:
        status = "✅ PASS" if result else "⚠️  SKIP"
        print(f"  {status}: {step_name}")
        if not result and "Email" in step_name:
            all_passed = False  # Email failure is critical
    
    if all_passed:
        show_next_steps()
        return True
    else:
        print("\n⚠️  Some steps were skipped or failed")
        print("Run this wizard again to retry: python setup_wizard.py")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
