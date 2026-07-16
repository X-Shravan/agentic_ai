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
