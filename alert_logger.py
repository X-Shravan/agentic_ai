"""
Real-Time Alert Logger for AI Exam Surveillance System
Collects actual detection logs during monitoring sessions
"""

import json
import os
from datetime import datetime
from threading import Lock


class AlertLogger:
    """
    Manages real-time alert logging with thread-safe operations.
    Logs are collected during surveillance and saved to JSON file.
    """
    
    def __init__(self, log_dir="logs", log_file="current_session.json"):
        """
        Initialize alert logger.
        
        Args:
            log_dir (str): Directory to store logs
            log_file (str): Name of current session log file
        """
        self.log_dir = log_dir
        self.log_file_path = os.path.join(log_dir, log_file)
        self.alerts = []
        self.lock = Lock()
        
        # Create log directory if needed
        os.makedirs(log_dir, exist_ok=True)
        
        # Load existing logs if available
        self.load_logs()
    
    def add_alert(self, student_id, behavior_type, confidence, image_path=None):
        """
        Add an alert to the log.
        
        Args:
            student_id (int): Student ID
            behavior_type (str): Type of behavior (Mobile, Looking Around, etc.)
            confidence (float): Confidence score (0-1)
            image_path (str): Path to evidence image (optional)
        
        Returns:
            dict: The alert that was added
        """
        with self.lock:
            alert = {
                'id': student_id,
                'type': behavior_type,
                'confidence': round(confidence, 2),
                'time': datetime.now().strftime("%H:%M:%S.%f")[:-3],  # HH:MM:SS.mmm
                'timestamp': datetime.now().isoformat(),
                'image_path': image_path
            }
            
            self.alerts.append(alert)
            self._save_logs()
            
            return alert
    
    def get_alerts(self):
        """
        Get all current alerts.
        
        Returns:
            list: List of alert dictionaries
        """
        with self.lock:
            return self.alerts.copy()
    
    def get_summary(self, total_students=0, active_ids=None):
        """
        Get summary statistics for current session.
        
        Returns:
            dict: Summary with total_students, active_ids, total_alerts, normal_students, 
                  alert_breakdown by type
        """
        with self.lock:
            if active_ids is None:
                active_ids = list(set(alert['id'] for alert in self.alerts))
            
            # Count by behavior type
            behavior_counts = {}
            for alert in self.alerts:
                behavior_type = alert['type']
                behavior_counts[behavior_type] = behavior_counts.get(behavior_type, 0) + 1
            
            return {
                'total_students': total_students,
                'active_ids': len(active_ids),
                'total_alerts': len(self.alerts),
                'normal_students': max(0, total_students - len(active_ids)),
                'alert_breakdown': behavior_counts,
                'session_duration': self._calculate_duration(),
                'average_confidence': self._calculate_avg_confidence()
            }
    
    def clear_logs(self):
        """Clear all logs and reset logger"""
        with self.lock:
            self.alerts = []
            if os.path.exists(self.log_file_path):
                os.remove(self.log_file_path)
            print(f"✅ Logs cleared from {self.log_file_path}")
    
    def _save_logs(self):
        """Save current alerts to JSON file"""
        try:
            with open(self.log_file_path, 'w') as f:
                json.dump({
                    'saved_at': datetime.now().isoformat(),
                    'total_alerts': len(self.alerts),
                    'alerts': self.alerts
                }, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving logs: {e}")
    
    def load_logs(self):
        """Load logs from JSON file if it exists"""
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, 'r') as f:
                    data = json.load(f)
                    self.alerts = data.get('alerts', [])
                print(f"✅ Loaded {len(self.alerts)} alerts from {self.log_file_path}")
            except Exception as e:
                print(f"⚠️ Error loading logs: {e}")
                self.alerts = []
    
    def _calculate_duration(self):
        """Calculate session duration"""
        if not self.alerts:
            return "0m 0s"
        
        first_time = datetime.fromisoformat(self.alerts[0]['timestamp'])
        last_time = datetime.fromisoformat(self.alerts[-1]['timestamp'])
        
        duration = (last_time - first_time).total_seconds()
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        return f"{minutes}m {seconds}s"
    
    def _calculate_avg_confidence(self):
        """Calculate average confidence of all alerts"""
        if not self.alerts:
            return 0.0
        
        total = sum(alert['confidence'] for alert in self.alerts)
        return round(total / len(self.alerts), 3)
    
    def export_alerts(self, output_path):
        """
        Export alerts to a new file.
        
        Args:
            output_path (str): Path to save exported logs
        
        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                with open(output_path, 'w') as f:
                    json.dump({
                        'exported_at': datetime.now().isoformat(),
                        'total_alerts': len(self.alerts),
                        'alerts': self.alerts
                    }, f, indent=2)
            
            print(f"✅ Alerts exported to {output_path}")
            return True
        except Exception as e:
            print(f"❌ Error exporting alerts: {e}")
            return False


# ================================================================
# INTEGRATION FUNCTIONS
# ================================================================

class RealtimeAlertSystem:
    """
    Complete real-time alert system with logging, reporting, and email.
    Designed for integration with main.py surveillance loop.
    """
    
    def __init__(self):
        """Initialize the alert system"""
        self.logger = AlertLogger()
        self.total_students = 0
        self.active_student_ids = set()
    
    def record_alert(self, student_id, behavior_type, confidence, image_path=None):
        """
        Record a new alert from surveillance.
        
        Args:
            student_id (int): Student ID
            behavior_type (str): Type of cheating detected
            confidence (float): Detection confidence (0-1)
            image_path (str): Path to evidence image
        
        Returns:
            dict: The recorded alert
        """
        self.active_student_ids.add(student_id)
        return self.logger.add_alert(student_id, behavior_type, confidence, image_path)
    
    def update_student_count(self, total_count):
        """Update total student count in session"""
        self.total_students = total_count
    
    def get_report_data(self):
        """
        Get all data needed for report generation.
        
        Returns:
            tuple: (alerts_log, summary_data)
                alerts_log: List of all alerts
                summary_data: Summary statistics
        """
        alerts = self.logger.get_alerts()
        summary = self.logger.get_summary(self.total_students, self.active_student_ids)
        
        return alerts, summary
    
    def generate_and_email_report(self, recipient_email=None):
        """
        Generate report and send via email.
        
        Args:
            recipient_email (str): Email recipient (optional)
        
        Returns:
            bool: True if successful
        """
        from report_generator import generate_report
        from email_sender import send_report_email
        
        # Generate report
        alerts, summary = self.get_report_data()
        report_path = generate_report(alerts, summary)
        
        if not report_path:
            print("❌ Failed to generate report")
            return False
        
        print(f"\n📄 Report generated: {report_path}")
        
        # Send email if configured
        if send_report_email(report_path, recipient_email):
            # Clear logs after successful email
            self.logger.clear_logs()
            self.active_student_ids.clear()
            return True
        
        return False


# ================================================================
# STANDALONE FUNCTIONS
# ================================================================

def create_alert_logger():
    """Create and return a new alert logger instance"""
    return AlertLogger()


def load_session_logs():
    """Load logs from current session"""
    logger = AlertLogger()
    return logger.get_alerts()


def clear_session_logs():
    """Clear current session logs"""
    logger = AlertLogger()
    logger.clear_logs()


# ================================================================
# COMMAND-LINE TESTING
# ================================================================

def test_logger():
    """Test alert logger functionality"""
    print("\n" + "="*60)
    print("🧪 ALERT LOGGER TEST")
    print("="*60 + "\n")
    
    # Create logger
    logger = AlertLogger("logs", "test_session.json")
    
    # Add test alerts
    print("📝 Adding test alerts...\n")
    
    behaviors = ["Mobile", "Looking Around", "Looking to Copy", "Leaning"]
    
    for i in range(1, 6):
        alert = logger.add_alert(
            student_id=100 + i,
            behavior_type=behaviors[i % len(behaviors)],
            confidence=0.75 + (i * 0.05),
            image_path=f"evidence/alert_{i}.jpg"
        )
        print(f"✅ Alert {i}: {alert['type']} by Student {alert['id']} @ {alert['time']}")
    
    # Get summary
    print("\n📊 Session Summary:")
    summary = logger.get_summary(total_students=30)
    for key, value in summary.items():
        if key != 'session_duration':
            print(f"  {key}: {value}")
    
    # Get alerts
    print("\n📋 All Alerts:")
    alerts = logger.get_alerts()
    for alert in alerts:
        print(f"  {alert['id']:3d} | {alert['type']:15s} | {alert['time']:12s} | {alert['confidence']:.2f}")
    
    print("\n✅ Test completed successfully!\n")


if __name__ == "__main__":
    test_logger()
