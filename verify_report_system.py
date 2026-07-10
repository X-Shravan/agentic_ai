#!/usr/bin/env python
"""
Report System - Environment Verification & Setup Checker
Verifies all dependencies and configuration are ready
"""

import sys
import os
from pathlib import Path

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"📌 Python Version: {version.major}.{version.minor}.{version.micro}")
    if version.major >= 3 and version.minor >= 8:
        print("   ✅ Python 3.8+ detected")
        return True
    else:
        print("   ❌ Python 3.8+ required")
        return False

def check_dependencies():
    """Check required dependencies"""
    print("\n📦 Checking Dependencies...")
    
    dependencies = {
        'reportlab': 'PDF generation',
        'PIL': 'Image processing',
        'flask': 'Web framework',
        'flask_socketio': 'WebSocket'
    }
    
    all_installed = True
    
    for module, description in dependencies.items():
        try:
            __import__(module)
            print(f"   ✅ {module}: {description}")
        except ImportError:
            print(f"   ❌ {module}: Missing - {description}")
            all_installed = False
    
    return all_installed

def check_directories():
    """Check/create required directories"""
    print("\n📁 Checking Directories...")
    
    dirs = [
        'logs',
        'reports',
        'evidence'
    ]
    
    for directory in dirs:
        path = Path(directory)
        if path.exists():
            print(f"   ✅ {directory}/")
        else:
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"   ✅ {directory}/ (created)")
            except Exception as e:
                print(f"   ❌ {directory}/ - {e}")
                return False
    
    return True

def check_report_modules():
    """Check if report modules exist"""
    print("\n📄 Checking Report Modules...")
    
    modules = [
        'report_system.py',
        'report_integration.py'
    ]
    
    all_exist = True
    for module in modules:
        if Path(module).exists():
            print(f"   ✅ {module}")
        else:
            print(f"   ❌ {module} - Missing")
            all_exist = False
    
    return all_exist

def check_email_config():
    """Check email configuration"""
    print("\n📧 Checking Email Configuration...")
    
    email = os.getenv('SURVEILLANCE_EMAIL')
    password = os.getenv('SURVEILLANCE_APP_PASSWORD')
    recipient = os.getenv('SURVEILLANCE_RECIPIENT')
    
    checks = {
        'SURVEILLANCE_EMAIL': email,
        'SURVEILLANCE_APP_PASSWORD': password,
        'SURVEILLANCE_RECIPIENT': recipient
    }
    
    all_configured = True
    for var, value in checks.items():
        if value:
            masked = value[:5] + "..." if len(value) > 5 else value
            print(f"   ✅ {var}: {masked}")
        else:
            print(f"   ❌ {var}: Not set")
            all_configured = False
    
    return all_configured

def check_imports():
    """Check if report modules can be imported"""
    print("\n🔍 Checking Module Imports...")
    
    try:
        from report_system import ReportGenerator, AlertLogManager, EmailSender
        print("   ✅ report_system module imports successfully")
    except ImportError as e:
        print(f"   ❌ report_system: {e}")
        return False
    
    try:
        from report_integration import initialize_report_system, log_alert_to_report, generate_session_report
        print("   ✅ report_integration module imports successfully")
    except ImportError as e:
        print(f"   ❌ report_integration: {e}")
        return False
    
    return True

def test_report_generation():
    """Test basic report generation"""
    print("\n🧪 Testing Report Generation...")
    
    try:
        from report_system import ReportGenerator
        
        test_alerts = [
            {"id": 1, "type": "Test Alert", "time": "12:00:00", "image_path": None}
        ]
        
        test_summary = {
            "total_students": 10,
            "active_ids": 9,
            "total_alerts": 1,
            "normal_students": 8,
            "monitoring_time": "00:10:00"
        }
        
        generator = ReportGenerator()
        report_path = generator.generate_report(test_alerts, test_summary, session_name="Test_Report")
        
        if Path(report_path).exists():
            size = Path(report_path).stat().st_size / 1024
            print(f"   ✅ Test report generated: {report_path}")
            print(f"   📊 Report size: {size:.1f} KB")
            return True
        else:
            print(f"   ❌ Report file not created")
            return False
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def show_setup_instructions():
    """Show setup instructions"""
    print("\n" + "="*60)
    print("SETUP INSTRUCTIONS")
    print("="*60)
    
    print("\n1️⃣ Install Dependencies (if not already done):")
    print("   pip install reportlab pillow")
    
    print("\n2️⃣ Setup Email Configuration:")
    print("   Windows CMD (as Admin):")
    print("   setx SURVEILLANCE_EMAIL \"your-email@gmail.com\"")
    print("   setx SURVEILLANCE_APP_PASSWORD \"16charapppassword\"")
    print("   setx SURVEILLANCE_RECIPIENT \"recipient@gmail.com\"")
    
    print("\n3️⃣ Get Gmail App Password:")
    print("   https://myaccount.google.com")
    print("   Security → App passwords")
    print("   Select Mail → Windows Computer")
    print("   Copy 16-character password")
    
    print("\n4️⃣ Verify Setup:")
    print("   python verify_report_system.py")
    
    print("\n5️⃣ Run Tests:")
    print("   python -c 'from report_system import ReportGenerator; print(\"✅ Ready\")'")

def main():
    """Run all checks"""
    print("\n" + "="*60)
    print("   AI EXAM SURVEILLANCE - REPORT SYSTEM VERIFICATION")
    print("="*60 + "\n")
    
    results = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'Directories': check_directories(),
        'Report Modules': check_report_modules(),
        'Module Imports': check_imports(),
    }
    
    # Only check email if modules import successfully
    if results['Module Imports']:
        results['Email Config'] = check_email_config()
        results['Report Generation'] = test_report_generation()
    else:
        print("\n⚠️ Skipping tests (module import failed)")
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60 + "\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {check}")
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Update api_server.py with report integration")
        print("  2. Run: python api_server.py")
        print("  3. Reports will auto-generate when monitoring stops")
        return 0
    else:
        print("\n⚠️ Some checks failed. See above for details.")
        show_setup_instructions()
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nVerification cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Verification error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
