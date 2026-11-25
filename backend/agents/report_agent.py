"""ReportLab PDF report generation for invigilation sessions."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class ReportResult:
    report_id: str
    session_id: str
    pdf_path: str
    generated_at: str
    total_events: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReportAgent:
    """Builds executive summaries and professional PDF reports."""

    def __init__(self, output_dir: str = "storage/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()

    def build_summary(self, session_id: str, events: list[dict]) -> Dict[str, Any]:
        critical = [e for e in events if str(e.get("risk_level") or e.get("severity", "")).upper() == "CRITICAL"]
        high = [e for e in events if str(e.get("risk_level") or e.get("severity", "")).upper() == "HIGH"]
        students = sorted({str(e.get("student_id") or e.get("student") or "UNKNOWN") for e in events})
        return {
            "session_id": session_id,
            "event_count": len(events),
            "students_flagged": len(students),
            "critical_alerts": len(critical),
            "high_alerts": len(high),
            "students": students,
            "events": events,
        }

    def generate_pdf(
        self,
        session_id: str,
        events: List[Dict[str, Any]],
        gemini_summary: Optional[Dict[str, Any]] = None,
        exam: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from reportlab.lib.styles import ParagraphStyle
        
        report_id = f"RP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        pdf_path = self.output_dir / f"{report_id}.pdf"
        exam = exam or {}
        gemini_summary = gemini_summary or {}
        
        # Setup custom styles if not already present
        if "ReportTitle" not in self.styles:
            self.styles.add(ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=22,
                leading=26,
                textColor=colors.HexColor("#1A365D"),
                spaceAfter=6
            ))
        if "SubTitle" not in self.styles:
            self.styles.add(ParagraphStyle(
                name="SubTitle",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#718096"),
                spaceAfter=15
            ))
        if "SectionHeading" not in self.styles:
            self.styles.add(ParagraphStyle(
                name="SectionHeading",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                textColor=colors.HexColor("#2B6CB0"),
                spaceBefore=12,
                spaceAfter=6,
                keepWithNext=True
            ))
        if "MetaLabel" not in self.styles:
            self.styles.add(ParagraphStyle(
                name="MetaLabel",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                textColor=colors.HexColor("#4A5568")
            ))
        if "MetaValue" not in self.styles:
            self.styles.add(ParagraphStyle(
                name="MetaValue",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=12,
                textColor=colors.HexColor("#2D3748")
            ))
        if "BriefReason" not in self.styles:
            self.styles.add(ParagraphStyle(
                name="BriefReason",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=14,
                textColor=colors.HexColor("#2D3748")
            ))

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        story: list[Any] = []
        
        # Header banner
        story.append(Paragraph("AI Exam Surveillance Report", self.styles["ReportTitle"]))
        story.append(Paragraph(f"Session ID: {session_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", self.styles["SubTitle"]))
        
        # Extract metadata from event if available
        student_id = "N/A"
        track_id = "N/A"
        camera_id = "N/A"
        evidence_id = "N/A"
        timestamp = "N/A"
        risk_score = 0.0
        confidence = 0.0
        all_behaviors = []
        image_path = None
        
        if events:
            event = events[0]
            student_id = event.get("student_id") or event.get("student") or "N/A"
            track_id = str(event.get("tracking_id", "N/A"))
            camera_id = event.get("camera_id") or "N/A"
            evidence_id = event.get("evidence_id") or "N/A"
            timestamp = event.get("timestamp") or "N/A"
            risk_score = event.get("risk_score") or 0.0
            confidence = event.get("confidence") or 0.0
            image_path = event.get("annotated_image_path") or event.get("image_path")
            
            all_behaviors = event.get("metadata", {}).get("behaviors", [])
            if not all_behaviors:
                all_behaviors = [event.get("behaviour") or event.get("event") or "Suspicious Activity"]
                
        # Primary behavior description
        primary_behavior = gemini_summary.get("primary_assessment") or (events[0].get("behaviour") if events else "Suspicious Behavior Alert")
        
        # Risk level string
        risk_level = "LOW"
        if risk_score >= 90:
            risk_level = "CRITICAL"
        elif risk_score >= 75:
            risk_level = "HIGH"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
        risk_str = f"{risk_score:.1f} / 100 ({risk_level})"
        
        # Section 1: Student Information & Incident Summary Box
        story.append(Paragraph("Student & Incident Information", self.styles["SectionHeading"]))
        
        info_data = [
            [Paragraph("Student ID:", self.styles["MetaLabel"]), Paragraph(str(student_id), self.styles["MetaValue"]),
             Paragraph("Risk Score:", self.styles["MetaLabel"]), Paragraph(risk_str, self.styles["MetaValue"])],
            [Paragraph("Track ID:", self.styles["MetaLabel"]), Paragraph(str(track_id), self.styles["MetaValue"]),
             Paragraph("Confidence:", self.styles["MetaLabel"]), Paragraph(f"{confidence:.2f}", self.styles["MetaValue"])],
            [Paragraph("Camera ID:", self.styles["MetaLabel"]), Paragraph(str(camera_id), self.styles["MetaValue"]),
             Paragraph("Evidence ID:", self.styles["MetaLabel"]), Paragraph(str(evidence_id), self.styles["MetaValue"])],
            [Paragraph("Incident Time:", self.styles["MetaLabel"]), Paragraph(str(timestamp)[:19], self.styles["MetaValue"]),
             Paragraph("Exam Subject:", self.styles["MetaLabel"]), Paragraph(exam.get("subject", "N/A"), self.styles["MetaValue"])]
        ]
        
        t = Table(info_data, colWidths=[1.3 * inch, 2.0 * inch, 1.3 * inch, 2.7 * inch])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.15 * inch))
        
        # Section 2: Detected Behaviours & Timeline
        story.append(Paragraph("Detected Behaviours", self.styles["SectionHeading"]))
        story.append(Paragraph(f"<b>Primary Incident:</b> {primary_behavior}", self.styles["BriefReason"]))
        story.append(Spacer(1, 0.05 * inch))
        
        # Timeline / bullet list of all behaviors
        for b in all_behaviors:
            b_name = b.replace("_", " ").title()
            story.append(Paragraph(f"• {b_name}", self.styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))
        
        # Section 3: AI Analysis (Gemini Explanation)
        story.append(Paragraph("Gemini AI Explanation", self.styles["SectionHeading"]))
        ai_text = gemini_summary.get("pdf_report_summary") or gemini_summary.get("primary_assessment") or "No AI summary available."
        story.append(Paragraph(str(ai_text), self.styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))
        
        # Section 4: CrewAI Invigilation Decision & Recommendation
        story.append(Paragraph("CrewAI Invigilation Decision", self.styles["SectionHeading"]))
        crew_decision = gemini_summary.get("crew_decision") or "No CrewAI decision recorded."
        recommendation = gemini_summary.get("recommendation") or "Immediate invigilator review."
        
        decision_data = [
            [Paragraph("Invigilation Decision:", self.styles["MetaLabel"]), Paragraph(crew_decision, self.styles["MetaValue"])],
            [Paragraph("Recommendation:", self.styles["MetaLabel"]), Paragraph(recommendation, self.styles["MetaValue"])]
        ]
        t_decision = Table(decision_data, colWidths=[1.8 * inch, 5.5 * inch])
        t_decision.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t_decision)
        story.append(Spacer(1, 0.15 * inch))
        
        # Section 5: Evidence Frame
        if image_path:
            abs_path = str(Path(image_path).resolve())
            if os.path.exists(abs_path):
                story.append(Paragraph("Captured Evidence Frame", self.styles["SectionHeading"]))
                story.append(Spacer(1, 0.05 * inch))
                story.append(Image(abs_path, width=5.2 * inch, height=2.9 * inch))
                story.append(Spacer(1, 0.1 * inch))
            else:
                print(f"[ERROR] PDF generator requested image does not exist at {abs_path}")
        
        doc.build(story)
        return ReportResult(report_id, session_id, str(pdf_path), datetime.utcnow().isoformat(), len(events)).to_dict()

    def _table(self, rows: list[list[Any]], widths: list[float], header: bool = False) -> Table:
        table = Table(rows, colWidths=widths)
        style = [("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if header:
            style.extend([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("TEXTCOLOR", (0, 0), (-1, 0), colors.black)])
        table.setStyle(TableStyle(style))
        return table
