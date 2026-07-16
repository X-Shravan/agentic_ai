"""FastAPI alert, risk, and evidence endpoints for WebSocket alert dashboards."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.evidence_agent import EvidenceAgent
from backend.agents.gemini_agent import GeminiReasoningEngine
from backend.database.store import store
from backend.risk_engine.risk_calculator import RiskCalculator

router = APIRouter(prefix="/alerts", tags=["alerts"])
risk_calculator = RiskCalculator()
evidence_agent = EvidenceAgent()
gemini_agent = GeminiReasoningEngine()


class AlertCreate(BaseModel):
    student_id: str
    session_id: Optional[str] = None
    camera_id: Optional[str] = "CAM_01"
    tracking_id: Optional[int] = None
    alert_type: str = "SUSPICIOUS_BEHAVIOR"
    risk_score: float = 0.0
    severity: Optional[str] = None
    behaviors: list[dict] = []
    reason: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None


class RiskRequest(BaseModel):
    student_id: Optional[str] = None
    phone_score: float = 0.0
    gaze_score: float = 0.0
    pose_score: float = 0.0
    behavior_score: float = 0.0
    history_score: float = 0.0


@router.get("")
def list_alerts(session_id: Optional[str] = None, student_id: Optional[str] = None, severity: Optional[str] = None):
    return store.list("alerts", session_id=session_id, student_id=student_id, severity=severity)


@router.post("")
async def create_alert(alert: AlertCreate):
    severity = alert.severity or risk_calculator.level(alert.risk_score)
    alert_id = f"AL{uuid.uuid4().hex[:10].upper()}"
    reasoning = await gemini_agent.analyze_alert({
        "student_id": alert.student_id,
        "camera": alert.camera_id,
        "risk_score": alert.risk_score,
        "risk_level": severity,
        "behaviors": alert.behaviors,
        "mobile_detected": alert.alert_type.upper() in {"PHONE_DETECTED", "MOBILE_DETECTED"},
    })
    payload = {
        **alert.model_dump(),
        "alert_id": alert_id,
        "severity": severity,
        "gemini_explanation": reasoning.get("ai_explanation"),
        "recommendation": reasoning.get("recommendation"),
        "evidence_captured": bool(alert.evidence),
    }
    item = store.upsert("alerts", "alert_id", payload)
    store.append("risk_scores", {
        "student_id": alert.student_id,
        "session_id": alert.session_id,
        "camera_id": alert.camera_id,
        "tracking_id": alert.tracking_id,
        "risk_score": alert.risk_score,
        "risk_level": severity,
        "behaviors": alert.behaviors,
    })
    return item


@router.post("/risk")
def calculate_risk(request: RiskRequest):
    result = risk_calculator.calculate(**request.model_dump())
    if request.student_id:
        store.append("risk_scores", {"student_id": request.student_id, **result})
    return result


@router.get("/risk/history")
def risk_history(student_id: Optional[str] = None, session_id: Optional[str] = None):
    values = store.list("risk_scores")
    if student_id:
        values = [item for item in values if item.get("student_id") == student_id]
    if session_id:
        values = [item for item in values if item.get("session_id") == session_id]
    return values


@router.get("/evidence")
def list_evidence(student_id: Optional[str] = None, session_id: Optional[str] = None):
    return store.list("evidence", student_id=student_id, session_id=session_id)


@router.post("/evidence")
def register_evidence(payload: Dict[str, Any]):
    if "evidence_id" not in payload:
        payload["evidence_id"] = f"EV{uuid.uuid4().hex[:10].upper()}"
    return store.upsert("evidence", "evidence_id", payload)


@router.get("/{alert_id}")
def get_alert(alert_id: str):
    alert = next((item for item in store.list("alerts") if item.get("alert_id") == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["evidence"] = [item for item in store.evidence.values() if item.get("alert_id") == alert_id]
    return alert
