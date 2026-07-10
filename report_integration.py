"""
AI Exam Surveillance - Integration with Report System
Integrates report generation into the API server
"""

from __future__ import annotations
from report_system import ReportPipeline, AlertLogManager
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ===================================================
# GLOBAL REPORT PIPELINE
# ===================================================

# Initialize report pipeline (globally accessible)
report_pipeline = None

def initialize_report_system(
    sender_email: str = None,
    app_password: str = None,
    recipient_email: str = "shravanwargantiwar@gmail.com"
) -> ReportPipeline:
    """
    Initialize the report system
    Call this once when API server starts
    
    Args:
        sender_email: Gmail address
        app_password: Gmail app password
        recipient_email: Recipient email
    
    Returns:
        ReportPipeline instance
    """
    global report_pipeline
    report_pipeline = ReportPipeline(sender_email, app_password, recipient_email)
    logger.info("📊 Report system initialized")
    return report_pipeline

def log_alert_to_report(
    student_id: int,
    behavior_type: str,
    timestamp: str,
    image_path: str = None
) -> None:
    """
    Log an alert for report generation
    Call this when an alert is detected
    
    Args:
        student_id: Student tracking ID
        behavior_type: Type of suspicious behavior
        timestamp: Time of detection (HH:MM:SS format)
        image_path: Path to evidence image
    """
    if report_pipeline is None:
        logger.warning("⚠️ Report system not initialized")
        return
    
    alert = {
        "id": student_id,
        "type": behavior_type,
        "time": timestamp,
        "image_path": image_path
    }
    
    report_pipeline.add_alert(alert)
    logger.info(f"📌 Alert logged for report: {alert}")

def generate_session_report(
    total_students: int,
    active_ids: int,
    total_alerts: int,
    normal_students: int,
    monitoring_time: str,
    send_email: bool = True,
    clear_logs: bool = True
) -> Dict[str, Any]:
    """
    Generate and send report after monitoring session ends
    
    Args:
        total_students: Total students monitored
        active_ids: Number of students detected
        total_alerts: Number of alerts triggered
        normal_students: Number of normal students
        monitoring_time: Duration of monitoring (HH:MM:SS)
        send_email: Whether to send email
        clear_logs: Whether to clear logs after sending
    
    Returns:
        Status dictionary with report details
    """
    if report_pipeline is None:
        logger.error("❌ Report system not initialized")
        return {"success": False, "message": "Report system not initialized"}
    
    summary_data = {
        "total_students": total_students,
        "active_ids": active_ids,
        "total_alerts": total_alerts,
        "normal_students": normal_students,
        "monitoring_time": monitoring_time
    }
    
    logger.info("🚀 Generating session report...")
    return report_pipeline.generate_and_send_report(
        summary_data,
        send_email=send_email,
        clear_logs=clear_logs
    )

# ===================================================
# DECORATOR FOR DECISION AGENT
# ===================================================

def create_alert_logger():
    """Create a closure for logging alerts from decision agent"""
    def log_alert_from_decision(decision_result: Dict[str, Any], frame_data: Any = None) -> None:
        """
        Log alert from decision agent
        
        Args:
            decision_result: Decision agent result with:
                - track_id: Student ID
                - risk_score: Risk score
                - situation: Behavior type (e.g., "Using Mobile")
                - should_alert: Whether to trigger alert
            frame_data: Optional frame for image capture
        """
        if not decision_result.get('should_alert'):
            return
        
        track_id = decision_result.get('track_id')
        situation = decision_result.get('situation', 'Unknown')
        risk_score = decision_result.get('risk_score', 0)
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Get image path if available
        image_path = None
        if frame_data is not None:
            # Evidence images are saved by the surveillance system
            image_path = f"evidence/ID{track_id}_{datetime.now().strftime('%H%M%S')}.jpg"
        
        # Log to report system
        log_alert_to_report(track_id, situation, timestamp, image_path)
    
    return log_alert_from_decision

# ===================================================
# EXAMPLE USAGE IN API SERVER
# ===================================================

"""
Example integration in api_server.py:

from report_integration import initialize_report_system, log_alert_to_report, generate_session_report

# At startup:
if __name__ == '__main__':
    # Initialize report system with Gmail credentials
    initialize_report_system(
        sender_email="your-email@gmail.com",
        app_password="your-app-password",  # 16-char app password
        recipient_email="recipient@gmail.com"
    )
    
    # Then when alert is detected in surveillance loop:
    # log_alert_to_report(student_id, behavior_type, timestamp, image_path)
    
    # When monitoring ends:
    result = generate_session_report(
        total_students=30,
        active_ids=28,
        total_alerts=5,
        normal_students=23,
        monitoring_time="00:45:30",
        send_email=True,
        clear_logs=True
    )
    print(f"Report status: {result}")
"""

if __name__ == "__main__":
    # Test the integration
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("📊 Report Integration Module")
    print("Import functions from this module to use in your system:")
    print("  - initialize_report_system()")
    print("  - log_alert_to_report()")
    print("  - generate_session_report()")
