"""
Enhanced PDF Report Generator for Individual Student Detection
Generates detailed PDF reports for each student with detection timeline and evidence
"""

import os
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, 
    PageBreak, KeepTogether
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from collections import defaultdict


class StudentDetectionReportGenerator:
    """Generate individual PDF reports for each student with detection details"""
    
    def __init__(self, output_dir="reports/student_reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_student_report(self, student_id, detections_log, evidence_images):
        """
        Generate a detailed PDF report for one student.
        
        Args:
            student_id (int): Student/Track ID
            detections_log (list): List of detection events
            evidence_images (list): List of evidence image file paths
        
        Returns:
            str: Path to generated PDF
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Student_ID_{student_id}_Report_{timestamp}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        # Create PDF
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )
        
        elements = []
        
        # Header with student ID
        elements.extend(self._create_student_header(student_id))
        elements.append(Spacer(1, 0.2*inch))
        
        # Summary statistics
        elements.extend(self._create_student_summary(detections_log))
        elements.append(Spacer(1, 0.2*inch))
        
        # Detection timeline table
        elements.extend(self._create_detection_timeline(detections_log))
        elements.append(Spacer(1, 0.2*inch))
        
        # Behavior breakdown
        elements.extend(self._create_behavior_breakdown(detections_log))
        elements.append(Spacer(1, 0.2*inch))
        
        # Risk assessment
        elements.extend(self._create_risk_assessment(detections_log))
        
        # Evidence section
        if evidence_images:
            elements.append(PageBreak())
            elements.extend(self._create_evidence_gallery(evidence_images))
        
        # Footer
        elements.append(Spacer(1, 0.3*inch))
        elements.extend(self._create_footer())
        
        # Build PDF
        try:
            doc.build(elements)
            print(f"✅ Student Report Generated: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error generating student report: {e}")
            return None
    
    # ================================================================
    # HEADER SECTION
    # ================================================================
    def _create_student_header(self, student_id):
        """Create header with student ID"""
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'StudentTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#1f4788'),
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'StudentSubtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#4472c4'),
            alignment=TA_CENTER,
            spaceAfter=6
        )
        
        elements.append(Paragraph(f"📋 EXAM SURVEILLANCE REPORT", title_style))
        elements.append(Paragraph(f"Student ID: {student_id}", subtitle_style))
        elements.append(Paragraph(
            f"Report Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}",
            subtitle_style
        ))
        
        return elements
    
    # ================================================================
    # SUMMARY SECTION
    # ================================================================
    def _create_student_summary(self, detections_log):
        """Create summary statistics"""
        elements = []
        styles = getSampleStyleSheet()
        
        if not detections_log:
            elements.append(Paragraph(
                "✅ No suspicious behavior detected during exam.",
                styles['Normal']
            ))
            return elements
        
        # Count by behavior type
        behavior_counts = defaultdict(int)
        total_alerts = 0
        mobile_alerts = 0
        
        for detection in detections_log:
            behavior_type = detection.get("behavior_type", "Unknown")
            behavior_counts[behavior_type] += 1
            
            if "Alert" in str(detection.get("label", "")):
                total_alerts += 1
            if "mobile" in behavior_type.lower():
                mobile_alerts += 1
        
        # Create summary table
        summary_data = [
            ["Metric", "Value"],
            ["Total Events Detected", str(len(detections_log))],
            ["Alert-Level Events", str(total_alerts)],
            ["Mobile Phone Detections", str(mobile_alerts)],
            ["Most Common Behavior", max(behavior_counts, key=behavior_counts.get) if behavior_counts else "None"],
            ["Exam Duration", "N/A (See timestamps)"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(Paragraph("📊 Detection Summary", styles['Heading2']))
        elements.append(summary_table)
        
        return elements
    
    # ================================================================
    # TIMELINE SECTION
    # ================================================================
    def _create_detection_timeline(self, detections_log):
        """Create detailed detection timeline"""
        elements = []
        styles = getSampleStyleSheet()
        
        if not detections_log:
            return elements
        
        elements.append(Paragraph("📅 Detection Timeline", styles['Heading2']))
        
        # Create timeline table
        timeline_data = [["Time", "Behavior Type", "Confidence", "Status", "Details"]]
        
        for i, detection in enumerate(detections_log[:20]):  # First 20 detections
            time_str = detection.get("timestamp", "N/A")[:8]  # HH:MM:SS
            behavior = detection.get("behavior_type", "Unknown")
            confidence = detection.get("confidence", 0.0)
            label = detection.get("label", "Normal")
            situation = detection.get("situation", "")
            
            status_icon = "🚨" if "Alert" in label else "⚠️" if "Suspicious" in label else "✅"
            
            timeline_data.append([
                time_str,
                behavior[:15],  # Truncate long names
                f"{confidence:.0%}",
                status_icon,
                situation[:25]
            ])
        
        timeline_table = Table(timeline_data, colWidths=[0.8*inch, 1.2*inch, 0.8*inch, 0.5*inch, 1.7*inch])
        timeline_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(timeline_table)
        
        if len(detections_log) > 20:
            elements.append(Paragraph(
                f"... and {len(detections_log) - 20} more events",
                styles['Normal']
            ))
        
        return elements
    
    # ================================================================
    # BEHAVIOR BREAKDOWN
    # ================================================================
    def _create_behavior_breakdown(self, detections_log):
        """Create behavior frequency breakdown"""
        elements = []
        styles = getSampleStyleSheet()
        
        if not detections_log:
            return elements
        
        # Count behaviors
        behavior_counts = defaultdict(int)
        for detection in detections_log:
            behavior = detection.get("behavior_type", "Unknown")
            behavior_counts[behavior] += 1
        
        elements.append(Paragraph("📊 Behavior Breakdown", styles['Heading2']))
        
        breakdown_data = [["Behavior Type", "Count", "Percentage"]]
        total = len(detections_log)
        
        for behavior, count in sorted(behavior_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            breakdown_data.append([
                behavior[:20],
                str(count),
                f"{percentage:.1f}%"
            ])
        
        breakdown_table = Table(breakdown_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
        breakdown_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472c4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        elements.append(breakdown_table)
        
        return elements
    
    # ================================================================
    # RISK ASSESSMENT
    # ================================================================
    def _create_risk_assessment(self, detections_log):
        """Create risk assessment section"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Calculate risk score
        alert_count = sum(1 for d in detections_log if "Alert" in str(d.get("label", "")))
        suspicious_count = sum(1 for d in detections_log if "Suspicious" in str(d.get("label", "")))
        mobile_count = sum(1 for d in detections_log if "mobile" in d.get("behavior_type", "").lower())
        
        # Risk scoring (0-100)
        risk_score = 0
        if alert_count > 0:
            risk_score += min(40, alert_count * 10)
        if mobile_count > 0:
            risk_score += 30  # Mobile is highest priority
        if suspicious_count > 0:
            risk_score += min(20, suspicious_count * 5)
        
        risk_score = min(100, risk_score)
        
        # Risk level
        if risk_score >= 75:
            risk_level = "🔴 HIGH RISK"
            risk_color = colors.red
        elif risk_score >= 40:
            risk_level = "🟡 MEDIUM RISK"
            risk_color = colors.orange
        else:
            risk_level = "🟢 LOW RISK"
            risk_color = colors.green
        
        elements.append(Paragraph("⚠️ Risk Assessment", styles['Heading2']))
        
        risk_data = [
            ["Risk Factor", "Count", "Impact"],
            ["Alert-Level Events", str(alert_count), "High" if alert_count > 0 else "None"],
            ["Mobile Phone Detections", str(mobile_count), "High" if mobile_count > 0 else "None"],
            ["Suspicious Events", str(suspicious_count), "Medium" if suspicious_count > 0 else "None"],
        ]
        
        risk_table = Table(risk_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), risk_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(risk_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Overall risk score
        score_style = ParagraphStyle(
            'RiskScore',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=risk_color,
            alignment=TA_CENTER,
        )
        elements.append(Paragraph(f"{risk_level} - Score: {risk_score}/100", score_style))
        
        return elements
    
    # ================================================================
    # EVIDENCE SECTION
    # ================================================================
    def _create_evidence_gallery(self, evidence_images):
        """Create evidence image gallery"""
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("📸 Evidence Gallery", styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Add images (up to 6 per page)
        for i, image_path in enumerate(evidence_images[:6]):
            if not os.path.exists(image_path):
                continue
            
            try:
                # Add image with caption
                img = Image(image_path, width=3*inch, height=2.25*inch)
                caption_text = f"Evidence #{i+1}: {os.path.basename(image_path)}"
                
                img_table = Table([[img]], colWidths=[3.2*inch])
                img_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                elements.append(img_table)
                elements.append(Paragraph(caption_text, styles['Normal']))
                elements.append(Spacer(1, 0.2*inch))
                
                # Page break after every 2 images
                if (i + 1) % 2 == 0 and i + 1 < len(evidence_images[:6]):
                    elements.append(PageBreak())
                    
            except Exception as e:
                print(f"⚠️ Could not add image {image_path}: {e}")
        
        if len(evidence_images) > 6:
            elements.append(Paragraph(
                f"... and {len(evidence_images) - 6} more evidence images available in evidence folder",
                styles['Normal']
            ))
        
        return elements
    
    # ================================================================
    # FOOTER
    # ================================================================
    def _create_footer(self):
        """Create footer section"""
        elements = []
        styles = getSampleStyleSheet()
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )
        
        elements.append(Paragraph(
            "This report is generated automatically by AI Exam Surveillance System. "
            "It contains confidential information.",
            footer_style
        ))
        elements.append(Paragraph(
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            footer_style
        ))
        
        return elements
    
    # ================================================================
    # BATCH GENERATE
    # ================================================================
    def generate_batch_reports(self, all_detections_by_student, evidence_by_student):
        """
        Generate reports for all students at once.
        
        Args:
            all_detections_by_student (dict): {student_id: [detections]}
            evidence_by_student (dict): {student_id: [image_paths]}
        
        Returns:
            list: Paths to generated reports
        """
        report_paths = []
        
        for student_id, detections in all_detections_by_student.items():
            evidence = evidence_by_student.get(student_id, [])
            pdf_path = self.generate_student_report(student_id, detections, evidence)
            if pdf_path:
                report_paths.append(pdf_path)
        
        print(f"\n✅ Generated {len(report_paths)} student reports in: {self.output_dir}")
        return report_paths


# ================================================================
# USAGE EXAMPLE
# ================================================================
if __name__ == "__main__":
    # Example usage
    generator = StudentDetectionReportGenerator()
    
    # Sample data
    sample_detections = [
        {
            "timestamp": "10:05:30",
            "behavior_type": "Using Mobile 📱",
            "confidence": 0.92,
            "label": "Alert 🚨",
            "situation": "using_mobile 📱 🚨"
        },
        {
            "timestamp": "10:10:15",
            "behavior_type": "Looking Around",
            "confidence": 0.78,
            "label": "Suspicious",
            "situation": "looking_around 👀"
        }
    ]
    
    sample_evidence = ["evidence/student_1_mobile.jpg"]
    
    # Generate report
    pdf_path = generator.generate_student_report(
        student_id=1,
        detections_log=sample_detections,
        evidence_images=sample_evidence
    )
    
    print(f"Report saved to: {pdf_path}")
