"""CrewAI agent registry for enterprise AI invigilation workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from crewai import Agent
except Exception:  # pragma: no cover - keep backend importable without CrewAI installed
    Agent = None


@dataclass
class LocalCrewAgent:
    role: str
    goal: str
    backstory: str
    allow_delegation: bool = False
    verbose: bool = False


AGENT_SPECS: List[Dict[str, Any]] = [
    {
        "key": "detection",
        "role": "Detection Agent",
        "goal": "Run YOLO detections for students, mobile phones, and suspicious objects while filtering false positives.",
        "backstory": "Computer vision specialist responsible only for local object-detection metadata, never cloud reasoning.",
    },
    {
        "key": "tracking",
        "role": "Tracking Agent",
        "goal": "Maintain persistent DeepSORT identities, re-identification continuity, and seat mapping.",
        "backstory": "Identity-tracking engineer focused on stable IDs across multi-camera exam rooms.",
    },
    {
        "key": "face",
        "role": "Face Agent",
        "goal": "Estimate yaw, pitch, roll, and repeated head movement from local MediaPipe Face Mesh signals.",
        "backstory": "Head-pose specialist that produces structured posture metadata without storing biometric templates.",
    },
    {
        "key": "gaze",
        "role": "Gaze Agent",
        "goal": "Classify iris gaze as LEFT, RIGHT, DOWN, or CENTER with confidence.",
        "backstory": "Iris-analysis specialist focused on privacy-safe gaze direction signals.",
    },
    {
        "key": "skeleton",
        "role": "Skeleton Agent",
        "goal": "Analyze shoulders, elbows, wrists, torso, and hips for leaning, reaching, paper passing, and hand-below-desk behavior.",
        "backstory": "Pose-estimation specialist interpreting body mechanics from local MediaPipe Pose output.",
    },
    {
        "key": "behavior",
        "role": "Behavior Agent",
        "goal": "Fuse YOLO, tracking, face, gaze, pose, and history into behavior classifications.",
        "backstory": "Multi-modal fusion expert that requires corroboration before escalating suspicious behavior.",
    },
    {
        "key": "risk",
        "role": "Risk Agent",
        "goal": "Calculate LOW, MEDIUM, HIGH, and CRITICAL risk levels from weighted evidence components.",
        "backstory": "Risk calibration specialist balancing sensitivity and false-positive reduction.",
    },
    {
        "key": "evidence",
        "role": "Evidence Agent",
        "goal": "Capture original frames, annotated frames, clips, and metadata locally for evidence-backed alerts.",
        "backstory": "Evidence custodian enforcing local storage and auditable metadata trails.",
    },
    {
        "key": "gemini",
        "role": "Gemini Reasoning Agent",
        "goal": "Explain structured surveillance events, risk interpretation, summaries, recommendations, and uncertainty.",
        "backstory": "Privacy-safe reasoning assistant that never receives CCTV, faces, raw images, or video.",
    },
    {
        "key": "report",
        "role": "Report Agent",
        "goal": "Create professional PDF reports with executive summary, timeline, evidence, findings, and recommendations.",
        "backstory": "Compliance reporting specialist for invigilation audit documents.",
    },
    {
        "key": "invigilator",
        "role": "Invigilator Agent",
        "goal": "Coordinate alerts, recommend manual verification, and avoid misconduct conclusions from isolated events.",
        "backstory": "Human-in-the-loop supervisor that prioritizes fairness, uncertainty, and corroborating evidence.",
        "allow_delegation": True,
    },
]


def create_agent(spec: Dict[str, Any]):
    payload = {
        "role": spec["role"],
        "goal": spec["goal"],
        "backstory": spec["backstory"],
        "allow_delegation": spec.get("allow_delegation", False),
        "verbose": spec.get("verbose", False),
    }
    if Agent is None:
        return LocalCrewAgent(**payload)
    return Agent(**payload)


def create_crewai_agents() -> Dict[str, Any]:
    """Create actual CrewAI Agent objects when CrewAI is installed, with local fallback objects."""
    return {spec["key"]: create_agent(spec) for spec in AGENT_SPECS}


AGENTS = create_crewai_agents()
AGENT_ROLES = [spec["key"] for spec in AGENT_SPECS]

__all__ = ["AGENTS", "AGENT_ROLES", "AGENT_SPECS", "LocalCrewAgent", "create_agent", "create_crewai_agents"]
