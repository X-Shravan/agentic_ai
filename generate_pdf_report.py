"""
✅ FIXED PDF Report Generator for AI Exam Surveillance System
- Generates PDFs reliably
- Saves in reports folder
- Full debug logging
- Error handling included
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# 📦 reportlab imports
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, 
    Table, 
    TableStyle, 
    Paragraph, 
    Spacer, 
    Image, 
    PageBreak
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ===================================================
# GENERATE REPORT FUNCTION
# ===================================================

def generate_report(alerts_log: List[Dict], summary_data: Dict) -> Optional[str]:
    """
    Generate PDF report with full debug logging
    
    Args:
        alerts_log (List[Dict]): List of alert dictionaries with:
            - id: Student/Track ID
            - type: Behavior type (e.g., "Using Mobile")
            - time: Time of alert (HH:MM:SS)
            - image_path: Path to evidence image (optional)
        
        summary_data (Dict): Dictionary with:
            - total_students: Total students monitored
            - active_ids: Number of active IDs detected
            - total_alerts: Total alerts triggered
            - normal_students: Number of normal students
    
    Returns:
        str: Path to generated PDF file, or None if error
    
    Example:
        >>> alerts = [
        ...     {"id": 1, "type": "Using Mobile", "time": "10:05:12", "image_path": "evidence/1.jpg"},
        ...     {"id": 2, "type": "Looking Around", "time": "10:10:30", "image_path": "evidence/2.jpg"}
        ... ]
        >>> summary = {"total_students": 30, "active_ids": 28, "total_alerts": 2, "normal_students": 26}
        >>> pdf_path = generate_report(alerts, summary)
        >>> print(pdf_path)
        reports/report_20260419_143522.pdf
    """
    
    print("\n" + "="*60)
    print("📄 GENERATING PDF REPORT")
    print("="*60)
    
    try:
        # ===================================================
        # STEP 1: CREATE REPORTS FOLDER
        # ===================================================
        
        print("📁 Checking reports folder...")
        reports_dir = "reports"
        
        if not os.path.exists(reports_dir):
            print(f"   ⚠️  Folder '{reports_dir}' not found, creating...")
            os.makedirs(reports_dir, exist_ok=True)
            print(f"   ✅ Folder created: {reports_dir}/")
        else:
            print(f"   ✅ Folder exists: {reports_dir}/")
        
        # ===================================================
        # STEP 2: GENERATE FILENAME WITH TIMESTAMP
        # ===================================================
        
        print("\n📝 Generating filename...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.pdf"
        file_path = os.path.join(reports_dir, filename)
        print(f"   📌 Filename: {filename}")
        print(f"   📌 Full path: {file_path}")
        
        # ===================================================
        # STEP 3: CREATE PDF DOCUMENT
        # ===================================================
        
        print("\n📋 Creating PDF document...")
        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            title="AI Exam Surveillance Report"
        )
        print("   ✅ PDF document object created")
        
        # ===================================================
        # STEP 4: SETUP STYLES
        # ===================================================
        
        print("\n🎨 Setting up styles...")
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
        
        # Section heading style
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        # Alert text style
        alert_style = ParagraphStyle(
            'AlertText',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#d9534f'),
            spaceAfter=6,
            fontName='Helvetica'
        )
        
        print("   ✅ Styles configured")
        
        # ===================================================
        # STEP 5: BUILD REPORT ELEMENTS
        # ===================================================
        
        print("\n🏗️  Building report elements...")
        story = []
        
        # ---- HEADER SECTION ----
        print("   • Adding header...")
        title = Paragraph("🎓 AI EXAM SURVEILLANCE REPORT", title_style)
        story.append(title)
        
        # Date and time
        report_time = datetime.now().strftime("%B %d, %Y | %H:%M:%S")
        date_para = Paragraph(f"<b>Generated:</b> {report_time}", styles['Normal'])
        story.append(date_para)
        story.append(Spacer(1, 0.3*inch))
        
        # ---- SUMMARY SECTION ----
        print("   • Adding summary section...")
        summary_heading = Paragraph("📊 MONITORING SUMMARY", heading_style)
        story.append(summary_heading)
        
        # Extract summary data
        total_students = summary_data.get('total_students', 0)
        active_ids = summary_data.get('active_ids', 0)
        total_alerts = summary_data.get('total_alerts', 0)
        normal_students = summary_data.get('normal_students', 0)
        
        # Create summary table
        summary_table_data = [
            ['Metric', 'Count'],
            ['Total Students', str(total_students)],
            ['Active IDs', str(active_ids)],
            ['Total Alerts', str(total_alerts)],
            ['Normal Students', str(normal_students)],
        ]
        
        summary_table = Table(summary_table_data, colWidths=[3.5*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f0f0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # ---- ALERT TABLE SECTION ----
        if alerts_log:
            print("   • Adding alerts table...")
            alerts_heading = Paragraph("⚠️ ALERT DETAILS", heading_style)
            story.append(alerts_heading)
            
            # Create alerts table
            alerts_table_data = [['ID', 'Behavior', 'Time', 'Status']]
            
            for alert in alerts_log[:20]:  # Limit to 20 alerts
                alert_id = str(alert.get('id', 'N/A'))
                behavior = str(alert.get('type', 'Unknown'))
                alert_time = str(alert.get('time', 'N/A'))
                
                # Determine status based on behavior
                if 'Mobile' in behavior:
                    status = '🔴 ALERT'
                elif 'Copy' in behavior:
                    status = '🔴 ALERT'
                elif 'Looking' in behavior:
                    status = '🟠 WARNING'
                elif 'Leaning' in behavior:
                    status = '🟠 WARNING'
                else:
                    status = '⚪ INFO'
                
                alerts_table_data.append([alert_id, behavior, alert_time, status])
            
            # Create table
            alerts_table = Table(alerts_table_data, colWidths=[0.8*inch, 2.5*inch, 1.2*inch, 1.5*inch])
            alerts_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0504d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            
            story.append(alerts_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Show if there are more alerts
            if len(alerts_log) > 20:
                note = Paragraph(
                    f"<i>* Showing first 20 of {len(alerts_log)} total alerts</i>",
                    styles['Normal']
                )
                story.append(note)
        else:
            print("   • No alerts to display")
            no_alerts = Paragraph("✅ <b>No suspicious activity detected</b>", styles['Normal'])
            story.append(no_alerts)
            story.append(Spacer(1, 0.3*inch))
        
        # ---- EVIDENCE SECTION ----
        print("   • Adding evidence section...")
        story.append(PageBreak())
        evidence_heading = Paragraph("📸 EVIDENCE (IMAGE GALLERY)", heading_style)
        story.append(evidence_heading)
        
        if alerts_log:
            # Show top 10 alerts with images
            display_alerts = alerts_log[:10]
            
            for idx, alert in enumerate(display_alerts):
                try:
                    alert_id = alert.get('id', 'N/A')
                    alert_type = alert.get('type', 'Unknown')
                    alert_time = alert.get('time', 'N/A')
                    image_path = alert.get('image_path')
                    
                    # Alert caption
                    caption = f"<b>ID:</b> {alert_id} | <b>Behavior:</b> {alert_type} | <b>Time:</b> {alert_time}"
                    caption_para = Paragraph(caption, alert_style)
                    story.append(caption_para)
                    
                    # Try to add image if it exists
                    if image_path and os.path.exists(image_path):
                        try:
                            # Add image
                            img = Image(image_path, width=4.5*inch, height=3*inch)
                            story.append(img)
                            print(f"     ✅ Added image: {image_path}")
                        except Exception as img_error:
                            print(f"     ⚠️  Could not add image {image_path}: {img_error}")
                    else:
                        if image_path:
                            print(f"     ⚠️  Image not found: {image_path}")
                    
                    story.append(Spacer(1, 0.2*inch))
                    
                    # Page break after 3 images
                    if (idx + 1) % 3 == 0 and idx < len(display_alerts) - 1:
                        story.append(PageBreak())
                
                except Exception as e:
                    print(f"     ⚠️  Error processing alert {idx}: {e}")
                    continue
        else:
            no_evidence = Paragraph("No evidence images available.", styles['Normal'])
            story.append(no_evidence)
        
        # ---- FOOTER ----
        print("   • Adding footer...")
        story.append(Spacer(1, 0.3*inch))
        footer = Paragraph(
            "<i>This report was automatically generated by AI Exam Surveillance System</i>",
            styles['Normal']
        )
        story.append(footer)
        
        print("   ✅ All elements added to story")
        
        # ===================================================
        # STEP 6: BUILD PDF
        # ===================================================
        
        print("\n🔨 Building PDF document...")
        doc.build(story)
        print(f"   ✅ PDF built successfully")
        
        # ===================================================
        # STEP 7: VERIFY FILE EXISTS
        # ===================================================
        
        print("\n✅ VERIFYING REPORT")
        print("="*60)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"✅ Report generated successfully!")
            print(f"📁 Location: {os.path.abspath(file_path)}")
            print(f"💾 Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
            print(f"⏰ Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📊 Alerts: {len(alerts_log)}")
            print(f"📈 Summary: {total_students} students, {total_alerts} alerts")
            print("="*60 + "\n")
            
            return file_path
        else:
            print(f"❌ Error: PDF file was not created at {file_path}")
            return None
    
    except Exception as e:
        print(f"\n❌ ERROR DURING REPORT GENERATION")
        print("="*60)
        print(f"Exception: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print("="*60 + "\n")
        
        # Print detailed traceback for debugging
        import traceback
        traceback.print_exc()
        
        return None


# ===================================================
# TEST FUNCTION
# ===================================================

def test_generate_report():
    """Test report generation with sample data"""
    
    print("\n" + "#"*60)
    print("# 🧪 TESTING PDF REPORT GENERATION")
    print("#"*60 + "\n")
    
    # Sample alerts
    sample_alerts = [
        {
            "id": 1,
            "type": "Using Mobile",
            "time": "10:05:12",
            "image_path": None  # No image for test
        },
        {
            "id": 2,
            "type": "Looking Around",
            "time": "10:10:30",
            "image_path": None
        },
        {
            "id": 3,
            "type": "Leaning to Copy",
            "time": "10:15:45",
            "image_path": None
        },
        {
            "id": 5,
            "type": "Looking to Copy",
            "time": "10:20:15",
            "image_path": None
        },
    ]
    
    # Summary data
    summary_data = {
        "total_students": 30,
        "active_ids": 28,
        "total_alerts": 4,
        "normal_students": 24
    }
    
    # Generate report
    pdf_path = generate_report(sample_alerts, summary_data)
    
    if pdf_path:
        print(f"\n✅ TEST PASSED - Report generated: {pdf_path}")
        return pdf_path
    else:
        print(f"\n❌ TEST FAILED - No report generated")
        return None


# ===================================================
# MAIN
# ===================================================

if __name__ == "__main__":
    # Run test
    test_generate_report()
