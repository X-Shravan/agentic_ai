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

    def __init__(self, output_dir: str = "backend/storage/reports"):
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
        report_id = f"RP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        pdf_path = self.output_dir / f"{report_id}.pdf"
        summary = self.build_summary(session_id, events)
        exam = exam or {}
        gemini_summary = gemini_summary or {}

        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story: list[Any] = []
        story.append(Paragraph("AI Invigilation Report", self.styles["Title"]))
        story.append(Paragraph(f"Session: {session_id}", self.styles["Normal"]))
        story.append(Paragraph(f"Generated: {datetime.utcnow().isoformat()} UTC", self.styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph("Exam Summary", self.styles["Heading2"]))
        summary_rows = [
            ["Exam", exam.get("name", exam.get("exam_name", "N/A"))],
            ["Subject", exam.get("subject", "N/A")],
            ["Total Events", str(summary["event_count"])],
            ["Students Flagged", str(summary["students_flagged"])],
            ["Critical Alerts", str(summary["critical_alerts"])],
            ["High Alerts", str(summary["high_alerts"])],
        ]
        story.append(self._table(summary_rows, [2.0 * inch, 4.2 * inch]))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph("AI Findings", self.styles["Heading2"]))
        ai_text = gemini_summary.get("pdf_report_summary") or gemini_summary.get("primary_assessment") or "No AI summary available."
        story.append(Paragraph(str(ai_text), self.styles["BodyText"]))
        if gemini_summary.get("recommendation"):
            story.append(Paragraph(f"Recommendation: {gemini_summary['recommendation']}", self.styles["BodyText"]))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph("Evidence Timeline", self.styles["Heading2"]))
        rows = [["Time", "Student", "Event", "Risk", "Camera"]]
        for event in events[:60]:
            rows.append([
                str(event.get("timestamp", "N/A"))[:19],
                str(event.get("student_id") or event.get("student") or "UNKNOWN"),
                str(event.get("event") or event.get("behavior") or event.get("type") or "Alert")[:40],
                str(event.get("risk_score", event.get("score", "N/A"))),
                str(event.get("camera_id", event.get("camera", "N/A"))),
            ])
        story.append(self._table(rows, [1.35 * inch, 1.0 * inch, 2.25 * inch, 0.75 * inch, 0.9 * inch], header=True))

        for event in events[:6]:
            image_path = event.get("annotated_frame_path") or event.get("image_path")
            if image_path and os.path.exists(image_path):
                story.append(Spacer(1, 0.15 * inch))
                story.append(Paragraph(f"Evidence: {event.get('evidence_id', '')}", self.styles["Heading3"]))
                story.append(Image(image_path, width=4.8 * inch, height=2.7 * inch))

        doc.build(story)
        return ReportResult(report_id, session_id, str(pdf_path), datetime.utcnow().isoformat(), len(events)).to_dict()

    def _table(self, rows: list[list[Any]], widths: list[float], header: bool = False) -> Table:
        table = Table(rows, colWidths=widths)
        style = [("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if header:
            style.extend([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("TEXTCOLOR", (0, 0), (-1, 0), colors.black)])
        table.setStyle(TableStyle(style))
        return table
