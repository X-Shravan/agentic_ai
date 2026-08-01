"""Student and session roster API endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database.store import store

router = APIRouter(prefix="/students", tags=["students"])


class StudentCreate(BaseModel):
    student_id: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    roll_number: Optional[str] = None
    email: Optional[str] = None
    seat: Optional[str] = None
    seat_x: Optional[float] = None
    seat_y: Optional[float] = None
    camera_id: Optional[str] = None
    tracking_id: Optional[int] = None


@router.get("")
def list_students(session_id: Optional[str] = None, camera_id: Optional[str] = None):
    return store.list("students", session_id=session_id, camera_id=camera_id)


@router.post("")
def upsert_student(student: StudentCreate):
    return store.upsert("students", "student_id", student.model_dump())


@router.get("/{student_id}")
def get_student(student_id: str):
    student = next((item for item in store.list("students") if item.get("student_id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student["risk_history"] = [item for item in store.risk_scores if item.get("student_id") == student_id]
    student["behavior_history"] = [item for item in store.behavior_history if item.get("student_id") == student_id]
    student["evidence"] = [item for item in store.evidence.values() if item.get("student_id") == student_id]
    return student


@router.post("/sessions")
def create_session(payload: dict):
    if "session_id" not in payload:
        raise HTTPException(status_code=400, detail="session_id is required")
    return store.upsert("exam_sessions", "session_id", payload)


@router.get("/sessions/list")
def list_sessions():
    return store.list("exam_sessions")
