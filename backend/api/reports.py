"""Report API routes for PDF generation and report retrieval."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.agents.gemini_agent import GeminiReasoningEngine
from backend.agents.report_agent import ReportAgent
from backend.database.store import store

router = APIRouter(prefix="/reports", tags=["reports"])
report_agent = ReportAgent()
gemini_agent = GeminiReasoningEngine()


class ReportRequest(BaseModel):
    session_id: str
    exam: Dict[str, Any] = {}
    include_gemini: bool = True


@router.get("")
def list_reports(session_id: Optional[str] = None):
    return store.list("reports", session_id=session_id)


@router.post("/generate")
async def generate_report(request: ReportRequest):
    events = [item for item in store.evidence.values() if item.get("session_id") == request.session_id]
    if not events:
        events = [item for item in store.alerts.values() if item.get("session_id") == request.session_id]
    gemini_summary = {}
    if request.include_gemini:
        gemini_summary = await gemini_agent.reason_about_scene({"students": events, "session_id": request.session_id})
    result = report_agent.generate_pdf(request.session_id, events, gemini_summary, request.exam)
    store.upsert("reports", "report_id", {**result, "session_id": request.session_id, "summary": report_agent.build_summary(request.session_id, events), "gemini_summary": gemini_summary})
    return result


@router.get("/{report_id}")
def get_report(report_id: str):
    report = next((item for item in store.list("reports") if item.get("report_id") == report_id), None)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/download")
def download_report(report_id: str):
    report = get_report(report_id)
    path = Path(report.get("pdf_path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)


import os
from datetime import datetime

class EmailReportRequest(BaseModel):
    recipient_email: str
    subject: Optional[str] = None
    body: Optional[str] = None

@router.post("/{report_id}/email")
async def email_report(report_id: str, request: EmailReportRequest):
    report = get_report(report_id)
    pdf_path = report.get("pdf_path", "")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found for report")

    # Extract details from report metadata if available
    summary = report.get("summary", {}) or {}
    events = summary.get("events", []) or []
    
    student_id = "UNKNOWN"
    camera_id = "CAM_01"
    behaviour = "Suspicious Behavior Alert"
    risk_score = 0.0
    evidence_image = None
    evidence_video = None
    behaviors = []
    confidence = 0.90
    
    if events:
        first_event = events[0]
        student_id = first_event.get("student_id") or first_event.get("student") or "UNKNOWN"
        camera_id = first_event.get("camera_id") or "CAM_01"
        behaviour = first_event.get("event") or first_event.get("behaviour") or "Suspicious Behavior Alert"
        risk_score = first_event.get("risk_score") or 0.0
        evidence_image = first_event.get("annotated_frame_path") or first_event.get("evidence_image_path")
        evidence_video = first_event.get("evidence_video_path")
        behaviors = first_event.get("metadata", {}).get("behaviors", []) or [behaviour]
        confidence = first_event.get("confidence", 0.90)
        
    gemini_summary_data = report.get("gemini_summary", {}) or {}
    gemini_explanation = gemini_summary_data.get("pdf_report_summary") or gemini_summary_data.get("primary_assessment") or ""

    # Trigger background email delivery
    from email_sender import send_email_with_retries
    send_email_with_retries(
        recipient_email=request.recipient_email,
        pdf_path=pdf_path,
        student_id=student_id,
        camera_id=camera_id,
        behaviour=behaviour,
        risk_score=risk_score,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        gemini_explanation=gemini_explanation,
        crew_decision="Manual Report Email Request",
        evidence_image=evidence_image,
        evidence_video=evidence_video,
        report_id=report_id,
        behaviors=behaviors,
        confidence=confidence
    )

    return {"status": "sending", "message": "Email delivery has been initiated in the background."}
