"""
Integration module for automatic student PDF report generation
Call this when surveillance ends to generate individual student reports
"""

from collections import defaultdict
from datetime import datetime
import os
from student_detection_pdf_generator import StudentDetectionReportGenerator


class StudentReportManager:
    """Manages collection and generation of student detection reports"""
    
    def __init__(self):
        self.detections_by_student = defaultdict(list)
        self.evidence_by_student = defaultdict(list)
        self.pdf_generator = StudentDetectionReportGenerator()
    
    def add_detection(self, student_id, detection_data):
        """
        Record a detection event for a student.
        
        Args:
            student_id (int): Student/Track ID
            detection_data (dict): Detection details
                - timestamp: Time of detection (HH:MM:SS format)
                - behavior_type: Type of behavior detected
                - confidence: Confidence score (0-1)
                - label: Alert/Suspicious/Normal
                - situation: Emoji description of situation
        """
        self.detections_by_student[student_id].append(detection_data)
    
    def add_evidence_image(self, student_id, image_path):
        """
        Record an evidence image for a student.
        
        Args:
            student_id (int): Student/Track ID
            image_path (str): Path to evidence image file
        """
        if os.path.exists(image_path):
            self.evidence_by_student[student_id].append(image_path)
    
    def generate_all_reports(self, output_dir="reports/student_reports"):
        """
        Generate PDF reports for all students with detections.
        
        Returns:
            list: Paths to generated PDF reports
        """
        if not self.detections_by_student:
            print("⚠️ No detections recorded for report generation")
            return []
        
        print(f"\n📄 Generating PDF reports for {len(self.detections_by_student)} students...")
        
        report_paths = []
        for student_id in sorted(self.detections_by_student.keys()):
            detections = self.detections_by_student[student_id]
            evidence = self.evidence_by_student.get(student_id, [])
            
            pdf_path = self.pdf_generator.generate_student_report(
                student_id=student_id,
                detections_log=detections,
                evidence_images=evidence
            )
            
            if pdf_path:
                report_paths.append(pdf_path)
        
        print(f"✅ Generated {len(report_paths)} student PDF reports")
        print(f"📁 Reports saved to: {output_dir}\n")
        
        return report_paths
    
    def generate_index_html(self, output_dir="reports/student_reports"):
        """
        Generate an HTML index page for all student reports.
        
        Returns:
            str: Path to index.html
        """
        index_path = os.path.join(output_dir, "index.html")
        
        # Get all PDF files
        pdf_files = []
        if os.path.exists(output_dir):
            pdf_files = sorted([f for f in os.listdir(output_dir) if f.endswith('.pdf')])
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Student Detection Reports</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #1f4788;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .container {{
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .report-list {{
            list-style-type: none;
            padding: 0;
        }}
        .report-item {{
            padding: 12px;
            margin: 8px 0;
            background-color: #f9f9f9;
            border-left: 4px solid #4472c4;
            border-radius: 3px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .report-item:hover {{
            background-color: #f0f0f0;
            transform: translateX(5px);
            transition: 0.2s;
        }}
        .report-link {{
            color: #4472c4;
            text-decoration: none;
            font-weight: bold;
        }}
        .report-link:hover {{
            text-decoration: underline;
        }}
        .timestamp {{
            color: #666;
            font-size: 0.9em;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 24px;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 12px;
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Student Detection Reports</h1>
        <p>AI Exam Surveillance System - Individual Student Analysis</p>
        <p style="font-size: 0.9em;">Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}</p>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{len(pdf_files)}</div>
                <div class="stat-label">Total Reports</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{datetime.now().strftime('%H:%M')}</div>
                <div class="stat-label">Generated Time</div>
            </div>
        </div>
        
        <h2>📁 Available Reports</h2>
        {'<p style="color: #999;">No reports generated yet.</p>' if not pdf_files else f'''
        <ul class="report-list">
            {''.join(f'''
            <li class="report-item">
                <a href="{pdf_file}" class="report-link" target="_blank">
                    📄 {pdf_file}
                </a>
                <span class="timestamp">{os.path.getctime(os.path.join(output_dir, pdf_file)) if os.path.exists(os.path.join(output_dir, pdf_file)) else 'N/A'}</span>
            </li>
            ''' for pdf_file in pdf_files)}
        </ul>
        '''}
        
        <hr style="margin: 20px 0;">
        <p style="color: #666; font-size: 0.9em;">
            <strong>Note:</strong> Each PDF contains:
            <ul>
                <li>📅 Detection timeline with timestamps</li>
                <li>📊 Behavior breakdown and statistics</li>
                <li>⚠️ Risk assessment score</li>
                <li>📸 Evidence images (if available)</li>
            </ul>
        </p>
    </div>
</body>
</html>
"""
        
        try:
            with open(index_path, 'w') as f:
                f.write(html_content)
            print(f"✅ Index page created: {index_path}")
            return index_path
        except Exception as e:
            print(f"❌ Error creating index: {e}")
            return None
    
    def get_report_summary(self):
        """Get summary statistics about all reports"""
        total_detections = sum(len(d) for d in self.detections_by_student.values())
        total_students = len(self.detections_by_student)
        total_evidence = sum(len(e) for e in self.evidence_by_student.values())
        
        return {
            "total_students": total_students,
            "total_detections": total_detections,
            "total_evidence_images": total_evidence,
            "avg_detections_per_student": total_detections / total_students if total_students > 0 else 0
        }


# ================================================================
# INTEGRATION WITH API SERVER
# ================================================================

# Global instance (initialize in api_server)
student_report_manager = None

def initialize_student_reports():
    """Initialize the student report manager"""
    global student_report_manager
    student_report_manager = StudentReportManager()
    print("📊 Student report manager initialized")
    return student_report_manager

def record_student_detection(student_id, detection_data):
    """Record a detection for report generation"""
    if student_report_manager:
        student_report_manager.add_detection(student_id, detection_data)

def record_student_evidence(student_id, image_path):
    """Record evidence image for report generation"""
    if student_report_manager:
        student_report_manager.add_evidence_image(student_id, image_path)

def generate_student_reports():
    """Generate all student reports"""
    if student_report_manager:
        report_paths = student_report_manager.generate_all_reports()
        student_report_manager.generate_index_html()
        return report_paths
    return []

def get_student_reports_summary():
    """Get summary of all reports"""
    if student_report_manager:
        return student_report_manager.get_report_summary()
    return None


# ================================================================
# USAGE EXAMPLE
# ================================================================
if __name__ == "__main__":
    # Initialize
    manager = StudentReportManager()
    
    # Simulate adding detections
    manager.add_detection(1, {
        "timestamp": "10:05:30",
        "behavior_type": "Using Mobile 📱",
        "confidence": 0.92,
        "label": "Alert 🚨",
        "situation": "using_mobile 📱 🚨"
    })
    
    manager.add_detection(1, {
        "timestamp": "10:10:15",
        "behavior_type": "Looking Around",
        "confidence": 0.78,
        "label": "Suspicious",
        "situation": "looking_around 👀"
    })
    
    manager.add_detection(2, {
        "timestamp": "10:15:45",
        "behavior_type": "Normal",
        "confidence": 1.0,
        "label": "Normal",
        "situation": "normal"
    })
    
    # Generate reports
    reports = manager.generate_all_reports()
    manager.generate_index_html()
    
    # Print summary
    summary = manager.get_report_summary()
    print("\n📊 Report Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
