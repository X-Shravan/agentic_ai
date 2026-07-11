"""LangGraph workflow layout for the surveillance decision pipeline."""
from backend.langgraph.state import SurveillanceState

WORKFLOW_STEPS = [
    "camera_stream", "yolo_detection", "deepsort_tracking", "face_analysis",
    "eye_gaze_analysis", "skeleton_analysis", "behavior_analysis", "risk_engine",
    "evidence_collection", "gemini_reasoning", "report_generation", "dashboard",
]

def build_workflow():
    """Return the canonical workflow step list until LangGraph runtime is configured."""
    return WORKFLOW_STEPS.copy()
