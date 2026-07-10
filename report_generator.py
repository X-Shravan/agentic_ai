"""
Professional Report Generator for AI Exam Surveillance System
Generates PDF reports with real-time detection logs and evidence images
"""

import os
import json
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


class SurveillanceReportGenerator:
    """Generate professional PDF reports from surveillance logs"""
    
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_report(self, alerts_log, summary_data, report_name=None):
        """
        Generate a professional PDF report with logs and evidence.
        
        Args:
            alerts_log (list): List of alert dictionaries
            summary_data (dict): Dictionary with summary statistics
            report_name (str): Custom report filename (optional)
        
        Returns:
            str: Path to generated PDF report
        """
        
        # Create report filename with timestamp
        if report_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_name = f"surveillance_report_{timestamp}.pdf"
        
        report_path = os.path.join(self.output_dir, report_name)
        
        # Create PDF document
        doc = SimpleDocTemplate(
            report_path,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )
        
        # Container for PDF elements
        elements = []
        
        # Add header section
        elements.extend(self._create_header(summary_data))
        elements.append(Spacer(1, 0.3*inch))
        
        # Add summary section
        elements.extend(self._create_summary(summary_data))
        elements.append(Spacer(1, 0.3*inch))
        
        # Add alerts table
        elements.extend(self._create_alerts_table(alerts_log))
        elements.append(Spacer(1, 0.3*inch))
        
        # Add evidence section
        if alerts_log:
            elements.append(PageBreak())
            elements.extend(self._create_evidence_section(alerts_log))
        else:
            elements.extend(self._create_no_alerts_section())
        
        # Add footer
        elements.append(Spacer(1, 0.3*inch))
        elements.extend(self._create_footer())
        
        # Build PDF
        try:
            doc.build(elements)
            print(f"✅ Report generated: {report_path}")
            return report_path
        except Exception as e:
            print(f"❌ Error generating report: {e}")
            return None
    
    # ================================================================
    # HEADER SECTION
    # ================================================================
    def _create_header(self, summary_data):
        """Create report header"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Title
        title = Paragraph("🎓 AI EXAM SURVEILLANCE REPORT", title_style)
        elements.append(title)
        
        # Date and time
        report_time = datetime.now().strftime("%B %d, %Y | %H:%M:%S")
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#555555'),
            alignment=TA_CENTER,
            spaceAfter=6
        )
        elements.append(Paragraph(f"Report Generated: {report_time}", date_style))
        
        # Separator line
        line_data = [['']]
        line_table = Table(line_data, colWidths=[7.5*inch])
        line_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, -1), 2, colors.HexColor('#1f4788')),
        ]))
        elements.append(line_table)
        
        return elements
    
    # ================================================================
    # SUMMARY SECTION
    # ================================================================
    def _create_summary(self, summary_data):
        """Create summary statistics section"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Section title
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("📊 Session Summary", section_style))
        
        # Summary data
        total_students = summary_data.get('total_students', 0)
        active_ids = summary_data.get('active_ids', 0)
        total_alerts = summary_data.get('total_alerts', 0)
        normal_students = summary_data.get('normal_students', 0)
        
        # Create summary table
        summary_data_list = [
            ['Metric', 'Count'],
            ['Total Students', str(total_students)],
            ['Students Monitored', str(active_ids)],
            ['Total Alerts Detected', str(total_alerts)],
            ['Normal Behavior', str(normal_students)],
        ]
        
        table = Table(summary_data_list, colWidths=[3.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f0f0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
        ]))
        
        elements.append(table)
        return elements
    
    # ================================================================
    # ALERTS TABLE
    # ================================================================
    def _create_alerts_table(self, alerts_log):
        """Create alerts summary table"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Section title
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("⚠️ Alert Details", section_style))
        
        if not alerts_log:
            elements.append(Paragraph("No alerts detected during monitoring session.", styles['Normal']))
            return elements
        
        # Create alerts table
        table_data = [['ID', 'Behavior Type', 'Time', 'Status']]
        
        for alert in alerts_log[:20]:  # Limit to 20 alerts in table
            alert_id = str(alert.get('id', 'N/A'))
            alert_type = alert.get('type', 'Unknown')
            alert_time = alert.get('time', 'N/A')
            
            # Determine status emoji based on alert type
            if 'Mobile' in alert_type:
                status = '🔴 ALERT'
            elif 'Copy' in alert_type:
                status = '🔴 ALERT'
            elif 'Looking' in alert_type:
                status = '🟠 WARNING'
            elif 'Leaning' in alert_type:
                status = '🟠 WARNING'
            else:
                status = '⚪ INFO'
            
            table_data.append([alert_id, alert_type, alert_time, status])
        
        # Create table
        table = Table(table_data, colWidths=[1.2*inch, 2.5*inch, 1.5*inch, 2.3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(table)
        
        # Show if truncated
        if len(alerts_log) > 20:
            elements.append(Spacer(1, 0.1*inch))
            note_style = ParagraphStyle(
                'Note',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#999999'),
                fontName='Helvetica-Oblique'
            )
            elements.append(Paragraph(
                f"* Showing first 20 of {len(alerts_log)} total alerts. See evidence section for details.",
                note_style
            ))
        
        return elements
    
    # ================================================================
    # EVIDENCE SECTION
    # ================================================================
    def _create_evidence_section(self, alerts_log):
        """Create evidence section with images"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Section title
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("📸 Evidence (Time-Based)", section_style))
        
        # Limit to top 10 alerts (most important ones)
        display_alerts = alerts_log[:10]
        
        # Process each alert
        for idx, alert in enumerate(display_alerts):
            try:
                alert_id = alert.get('id', 'Unknown')
                alert_type = alert.get('type', 'Unknown')
                alert_time = alert.get('time', 'N/A')
                image_path = alert.get('image_path', None)
                
                # Alert header
                alert_header = f"ID {alert_id} → {alert_type} → {alert_time}"
                
                header_style = ParagraphStyle(
                    'AlertHeader',
                    parent=styles['Normal'],
                    fontSize=11,
                    textColor=colors.HexColor('#d9534f'),
                    fontName='Helvetica-Bold',
                    spaceAfter=6,
                    topMargin=10,
                    bottomMargin=4
                )
                elements.append(Paragraph(alert_header, header_style))
                
                # Add image if it exists
                if image_path and os.path.exists(image_path):
                    try:
                        # Resize image to fit page width
                        img = Image(image_path, width=6*inch, height=4.5*inch)
                        
                        # Create container for image
                        img_data = [[img]]
                        img_table = Table(img_data, colWidths=[6.5*inch])
                        img_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                            ('BORDER', (0, 0), (0, 0), 1, colors.HexColor('#cccccc')),
                        ]))
                        elements.append(img_table)
                        
                    except Exception as e:
                        print(f"⚠️ Could not load image {image_path}: {e}")
                        elements.append(Paragraph(
                            f"<i>Image not available: {os.path.basename(image_path)}</i>",
                            styles['Normal']
                        ))
                else:
                    elements.append(Paragraph(
                        "<i>No image available for this alert</i>",
                        styles['Normal']
                    ))
                
                # Add spacing between alerts
                elements.append(Spacer(1, 0.3*inch))
                
                # Page break after every 3 alerts (for better layout)
                if (idx + 1) % 3 == 0 and idx + 1 < len(display_alerts):
                    elements.append(PageBreak())
                    elements.append(Paragraph("📸 Evidence Continued", section_style))
                    elements.append(Spacer(1, 0.2*inch))
                    
            except Exception as e:
                print(f"⚠️ Error processing alert {idx}: {e}")
                continue
        
        return elements
    
    # ================================================================
    # NO ALERTS SECTION
    # ================================================================
    def _create_no_alerts_section(self):
        """Create section when no alerts exist"""
        elements = []
        styles = getSampleStyleSheet()
        
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#28a745'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        elements.append(Paragraph("✅ Monitoring Status", section_style))
        
        message_style = ParagraphStyle(
            'Message',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#28a745'),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        elements.append(Paragraph(
            "✓ No suspicious activity detected during monitoring session",
            message_style
        ))
        
        elements.append(Spacer(1, 0.2*inch))
        
        detail_style = ParagraphStyle(
            'Detail',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#555555'),
            alignment=TA_CENTER
        )
        
        elements.append(Paragraph(
            "All students demonstrated normal behavior throughout the examination period.",
            detail_style
        ))
        
        return elements
    
    # ================================================================
    # FOOTER
    # ================================================================
    def _create_footer(self):
        """Create report footer"""
        elements = []
        styles = getSampleStyleSheet()
        
        # Separator line
        line_data = [['']]
        line_table = Table(line_data, colWidths=[7.5*inch])
        line_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ]))
        elements.append(line_table)
        
        elements.append(Spacer(1, 0.15*inch))
        
        # Footer text
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER
        )
        
        footer_text = "This report was automatically generated by AI Exam Surveillance System"
        elements.append(Paragraph(footer_text, footer_style))
        
        footer_text2 = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elements.append(Paragraph(footer_text2, footer_style))
        
        return elements


# ================================================================
# STANDALONE FUNCTIONS FOR INTEGRATION
# ================================================================

def generate_report(alerts_log, summary_data, output_dir="reports", report_name=None):
    """
    Generate a surveillance report (standalone function).
    
    Args:
        alerts_log (list): List of alert dictionaries
        summary_data (dict): Dictionary with summary statistics
        output_dir (str): Directory to save report
        report_name (str): Custom report name
    
    Returns:
        str: Path to generated report or None on error
    """
    generator = SurveillanceReportGenerator(output_dir=output_dir)
    return generator.generate_report(alerts_log, summary_data, report_name)


if __name__ == "__main__":
    # Example usage
    print("🔧 Report Generator Test\n")
    
    # Sample data (for testing)
    sample_alerts = [
        {
            "id": 1,
            "type": "Using Mobile",
            "time": "10:05:12",
            "image_path": "evidence/ID1_100512.jpg"
        },
        {
            "id": 2,
            "type": "Looking to Copy",
            "time": "10:10:30",
            "image_path": "evidence/ID2_101030.jpg"
        },
        {
            "id": 3,
            "type": "Looking Around",
            "time": "10:15:45",
            "image_path": "evidence/ID3_101545.jpg"
        },
    ]
    
    sample_summary = {
        "total_students": 30,
        "active_ids": 28,
        "total_alerts": 3,
        "normal_students": 25,
    }
    
    # Generate report
    report_path = generate_report(sample_alerts, sample_summary)
    
    if report_path:
        print(f"✅ Test report generated: {report_path}")
    else:
        print("❌ Failed to generate test report")
