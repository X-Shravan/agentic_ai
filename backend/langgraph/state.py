"""Shared LangGraph state definitions for exam surveillance workflows."""
from typing import Any, Dict, List, TypedDict

class SurveillanceState(TypedDict, total=False):
    camera_id: str
    frame_id: str
    detections: List[Dict[str, Any]]
    tracks: List[Dict[str, Any]]
    face_analysis: Dict[str, Any]
    gaze_analysis: Dict[str, Any]
    skeleton_analysis: Dict[str, Any]
    behaviors: List[Dict[str, Any]]
    risk: Dict[str, Any]
    evidence: Dict[str, Any]
    ai_reasoning: Dict[str, Any]
