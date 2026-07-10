"""
EXAMPLE: main.py Integration Template
Shows exactly where to add alert logging and report generation
Copy these sections into your existing main.py
"""

# ================================================================
# SECTION 1: ADD THESE IMPORTS AT THE TOP OF main.py
# ================================================================

"""
from alert_logger import AlertLogger
from report_generator import generate_report  
from email_sender import send_report_email
"""


# ================================================================
# SECTION 2: ADD THIS IN YOUR INITIALIZATION SECTION
# ================================================================

"""
# Initialize alert logging for this session
alert_logger = AlertLogger("logs", "current_session.json")

# Set total students in exam (for reporting)
TOTAL_STUDENTS = 30  # Change this to your actual student count
alert_logger.update_student_count(TOTAL_STUDENTS)

print(f"📝 Alert logging initialized (Session ID: {datetime.now().strftime('%Y%m%d_%H%M%S')})")
"""


# ================================================================
# SECTION 3: IN YOUR MAIN DETECTION LOOP WHERE YOU DETECT ALERTS
# ================================================================

"""
# Inside your surveillance loop, when you detect a behavior:

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # ... your detection code ...
    
    # When you detect behavior, log it BEFORE displaying:
    for detection in detections:
        if is_alert:
            # Log the alert
            alert_logger.add_alert(
                student_id=student_id,
                behavior_type=behavior_type,  # E.g., "Mobile", "Looking to Copy"
                confidence=confidence_score,
                image_path=evidence_image_path  # Path saved by evidence_capture.py
            )
            
            print(f"🚨 ALERT: Student {student_id} - {behavior_type}")
    
    # ... rest of your frame display code ...
    
    if cv2.waitKey(1) & 0xFF == 27:  # ESC key
        break

cap.release()
cv2.destroyAllWindows()
"""


# ================================================================
# SECTION 4: AFTER MONITORING ENDS (ADD THIS AFTER YOUR MAIN LOOP)
# ================================================================

"""
# When monitoring stops (ESC pressed), generate and send report:

print("\\n" + "="*70)
print("🛑 MONITORING STOPPED - GENERATING SESSION REPORT")
print("="*70)

# Step 1: Get all logged alerts and summary
alerts = alert_logger.get_alerts()
summary = alert_logger.get_summary(total_students=TOTAL_STUDENTS)

print(f"\\n📊 Session Summary:")
print(f"   Total Alerts: {summary['total_alerts']}")
print(f"   Students with alerts: {summary['active_ids']}")
print(f"   Average confidence: {summary['average_confidence']:.1%}")
print(f"   Session duration: {summary['session_duration']}")

# Step 2: Generate PDF report
print(f"\\n📄 Generating PDF report...")
report_path = generate_report(alerts, summary)

if report_path:
    print(f"✅ Report saved to: {report_path}")
    
    # Step 3: Send via email (if configured)
    print(f"\\n📧 Sending report via email...")
    if send_report_email(report_path):
        print(f"✅ Report emailed successfully!")
        
        # Clear logs after successful send
        alert_logger.clear_logs()
        print(f"✅ Session logs cleared")
    else:
        print(f"⚠️  Email failed to send (but PDF report was saved)")
else:
    print(f"❌ Failed to generate report")
"""


# ================================================================
# SECTION 5: COMPLETE MINIMAL EXAMPLE
# ================================================================

"""
Here's a complete minimal example of how main.py should be structured:

import cv2
import numpy as np
from datetime import datetime
from alert_logger import AlertLogger
from report_generator import generate_report
from email_sender import send_report_email

# ... your other imports ...

def main():
    # Initialize
    cap = cv2.VideoCapture(0)
    alert_logger = AlertLogger()
    alert_logger.update_student_count(30)
    
    print("🎬 Starting surveillance... (Press ESC to stop)")
    
    # Main loop
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # ... your detection code ...
        
        # When you detect an alert:
        if behavior_detected:
            alert_logger.add_alert(
                student_id=student_id,
                behavior_type=behavior_name,
                confidence=confidence,
                image_path=f"evidence/{student_id}_{timestamp}.jpg"
            )
        
        # Display frame
        cv2.imshow("Surveillance", frame)
        
        # Check for ESC
        if cv2.waitKey(1) & 0xFF == 27:
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    # Generate and send report
    print("\\n" + "="*70)
    print("📊 GENERATING SESSION REPORT")
    print("="*70)
    
    alerts = alert_logger.get_alerts()
    summary = alert_logger.get_summary(total_students=30)
    
    report_path = generate_report(alerts, summary)
    if report_path:
        print(f"✅ Report: {report_path}")
        
        if send_report_email(report_path):
            alert_logger.clear_logs()
            print("✅ Report sent and logs cleared!")

if __name__ == "__main__":
    main()
"""


# ================================================================
# SECTION 6: BEHAVIOR TYPE CONSTANTS
# ================================================================

"""
Use these exact strings for behavior_type when logging alerts:

BEHAVIOR_TYPES = {
    "Mobile": "Student using mobile phone",
    "Looking Around": "Student looking around suspiciously",
    "Looking to Copy": "Student leaning to copy from neighbor",
    "Leaning": "Student leaning in unusual position",
}

# Example:
alert_logger.add_alert(
    student_id=101,
    behavior_type="Mobile",  # Use exact string from above
    confidence=0.92,
    image_path="evidence/alert.jpg"
)
"""


# ================================================================
# SECTION 7: EVIDENCE IMAGE NAMING CONVENTION
# ================================================================

"""
Save evidence images with this naming pattern:

Format: evidence/ID_X_{situation}_{timestamp}.jpg

Example:
  evidence/ID_101_mobile_20240115_143022.jpg
  evidence/ID_105_looking_to_copy_20240115_143045.jpg

This is already handled by alerts/evidence_capture.py
Just pass the full path to alert_logger.add_alert():

from alerts.evidence_capture import save_evidence_frame

image_path = save_evidence_frame(
    frame=frame,
    student_id=student_id,
    behavior_type=behavior_type,
    confidence=confidence
)

# Then log it:
alert_logger.add_alert(
    student_id=student_id,
    behavior_type=behavior_type,
    confidence=confidence,
    image_path=image_path
)
"""


# ================================================================
# SECTION 8: FULL WORKING EXAMPLE WITH YOUR DETECTION
# ================================================================

"""
Here's how to add to your actual detection code:

# At top of file:
from alert_logger import AlertLogger
from report_generator import generate_report
from email_sender import send_report_email
from agents.behavior_analysis_agent import BehaviorAnalysisAgent
from agents.tracking_agent import TrackingAgent

# In main():
behavior_analyzer = BehaviorAnalysisAgent()
tracker = TrackingAgent()
alert_logger = AlertLogger()
alert_logger.update_student_count(30)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # Get detections
    results = detector(frame)
    
    # Track objects
    tracked_objects = tracker.update_tracking(results, frame)
    
    # Analyze behavior
    for obj_id, obj in tracked_objects.items():
        behavior_status = behavior_analyzer.analyze_behavior(obj)
        
        if behavior_status['is_alert']:  # If alert triggered
            # Save evidence
            evidence_path = save_evidence_frame(
                frame=frame,
                student_id=obj_id,
                behavior_type=behavior_status['type'],
                confidence=behavior_status['confidence']
            )
            
            # Log alert
            alert_logger.add_alert(
                student_id=obj_id,
                behavior_type=behavior_status['type'],
                confidence=behavior_status['confidence'],
                image_path=evidence_path
            )
    
    # Display...
    cv2.imshow("Surveillance", frame)
    
    if cv2.waitKey(1) & 0xFF == 27:
        break

# When done:
cap.release()
cv2.destroyAllWindows()

# Generate report
alerts, summary = alert_logger.get_alerts(), alert_logger.get_summary(30)
report_path = generate_report(alerts, summary)
send_report_email(report_path)
alert_logger.clear_logs()
"""


# ================================================================
# PRINTING THIS AS DOCUMENTATION
# ================================================================

if __name__ == "__main__":
    # Print the documentation
    import re
    
    # Get the content between triple quotes
    content = __doc__
    
    # Print with formatting
    lines = content.split('\n')
    current_section = ""
    
    for line in lines:
        if '# ====' in line:
            print("\n" + "="*70)
            current_section = line.split('# ====')[1].strip('= \n')
            print(f"  {current_section}")
            print("="*70)
        elif line.strip() and not line.startswith('"""'):
            print(line)
    
    print("\n" + "="*70)
    print("\n✅ Copy the sections above into your main.py\n")
