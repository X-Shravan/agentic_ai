"""LangGraph workflow for the enterprise surveillance decision pipeline."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

from backend.agents.behavior_agent import FusionInput, MultiModalFusionEngine
from backend.agents.evidence_agent import EvidenceAgent
from backend.agents.face_agent import FaceAnalysisAgent
from backend.agents.gaze_agent import GazeAgent
from backend.agents.gemini_agent import GeminiReasoningEngine
from backend.agents.report_agent import ReportAgent
from backend.agents.skeleton_agent import SkeletonAnalyzer
from backend.langgraph.state import SurveillanceState
from backend.risk_engine.risk_calculator import RiskCalculator

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"
    StateGraph = None


WORKFLOW_STEPS = [
    "detection",
    "tracking",
    "face",
    "gaze",
    "skeleton",
    "behavior",
    "risk",
    "evidence",
    "gemini",
    "report",
]


class SurveillanceWorkflow:
    """Composable pipeline nodes for frame-level and metadata-only processing."""

    def __init__(
        self,
        detection_agent: Any = None,
        tracking_agent: Any = None,
        face_agent: Optional[FaceAnalysisAgent] = None,
        gaze_agent: Optional[GazeAgent] = None,
        skeleton_agent: Optional[SkeletonAnalyzer] = None,
        behavior_agent: Optional[MultiModalFusionEngine] = None,
        risk_calculator: Optional[RiskCalculator] = None,
        evidence_agent: Optional[EvidenceAgent] = None,
        gemini_agent: Optional[GeminiReasoningEngine] = None,
        report_agent: Optional[ReportAgent] = None,
    ):
        self.detection_agent = detection_agent
        self.tracking_agent = tracking_agent
        self.face_agent = face_agent or FaceAnalysisAgent()
        self.gaze_agent = gaze_agent or GazeAgent()
        self.skeleton_agent = skeleton_agent or SkeletonAnalyzer()
        self.behavior_agent = behavior_agent or MultiModalFusionEngine()
        self.risk_calculator = risk_calculator or RiskCalculator()
        self.evidence_agent = evidence_agent or EvidenceAgent()
        self.gemini_agent = gemini_agent or GeminiReasoningEngine()
        self.report_agent = report_agent or ReportAgent()

    def detection_node(self, state: SurveillanceState) -> SurveillanceState:
        frame = state.get("frame")
        if self.detection_agent and frame is not None:
            detections = self.detection_agent.detect(frame)
            state["raw_detections"] = detections
            state["detections"] = [d.to_dict() if hasattr(d, "to_dict") else d for d in detections]
        return state

    def tracking_node(self, state: SurveillanceState) -> SurveillanceState:
        detections = state.get("raw_detections") or state.get("detections") or []
        if self.tracking_agent:
            tracks = self.tracking_agent.update(detections)
            state["raw_tracks"] = tracks
            state["tracks"] = [self._track_to_dict(t, state) for t in tracks]
        return state

    def face_node(self, state: SurveillanceState) -> SurveillanceState:
        frame = state.get("frame")
        track = (state.get("raw_tracks") or [None])[0] if state.get("raw_tracks") else None
        state["face_analysis"] = self.face_agent.analyze(frame, track) if frame is not None else {}
        return state

    def gaze_node(self, state: SurveillanceState) -> SurveillanceState:
        frame = state.get("frame")
        track = (state.get("raw_tracks") or [None])[0] if state.get("raw_tracks") else None
        state["gaze_analysis"] = self.gaze_agent.analyze(frame, state.get("face_analysis"), track) if frame is not None else {}
        return state

    def skeleton_node(self, state: SurveillanceState) -> SurveillanceState:
        frame = state.get("frame")
        if frame is None:
            state["skeleton_analysis"] = {}
            return state
        analysis = self.skeleton_agent.analyze(frame)
        payload = analysis.__dict__.copy()
        payload["keypoints"] = {k: v.__dict__ for k, v in analysis.keypoints.items()}
        state["skeleton_analysis"] = payload
        return state

    def behavior_node(self, state: SurveillanceState) -> SurveillanceState:
        fusion_input = self._build_fusion_input(state)
        output = self.behavior_agent.fuse(fusion_input)
        state["behavior_fusion"] = output.__dict__.copy()
        state["behavior_fusion"]["risk_level"] = output.risk_level.value
        state["behaviors"] = [
            {"behavior": b.upper(), "confidence": output.overall_confidence} for b in output.primary_behaviors
        ] or [{"behavior": b.upper(), "confidence": output.overall_confidence * 0.75} for b in output.secondary_behaviors]
        return state

    def risk_node(self, state: SurveillanceState) -> SurveillanceState:
        state["risk"] = self.risk_calculator.from_pipeline(state)
        return state

    def evidence_node(self, state: SurveillanceState) -> SurveillanceState:
        risk = state.get("risk", {})
        if risk.get("risk_score", 0) < float(state.get("evidence_threshold", 40)):
            return state
        event = (state.get("behaviors") or [{"behavior": "RISK_ALERT"}])[0].get("behavior", "RISK_ALERT")
        state["evidence"] = self.evidence_agent.capture(
            state.get("frame"),
            state.get("annotated_frame"),
            student_id=state.get("student_id", "UNKNOWN"),
            event=event,
            camera_id=state.get("camera_id", "CAM_01"),
            tracking_id=state.get("tracking_id"),
            seat=state.get("seat"),
            confidence=max((b.get("confidence", 0.0) for b in state.get("behaviors", [])), default=0.0),
            risk_score=risk.get("risk_score", 0.0),
            metadata={"risk": risk, "behaviors": state.get("behaviors", []), "privacy": "local_evidence_only"},
        )
        return state

    async def gemini_node(self, state: SurveillanceState) -> SurveillanceState:
        state["ai_reasoning"] = await self.gemini_agent.analyze_alert(self._gemini_payload(state))
        return state

    def report_node(self, state: SurveillanceState) -> SurveillanceState:
        events = state.get("report_events") or []
        if state.get("evidence"):
            events.append(state["evidence"])
        state["report_summary"] = self.report_agent.build_summary(state.get("session_id", "LIVE"), events)
        return state

    async def run_async(self, initial_state: SurveillanceState) -> SurveillanceState:
        state = initial_state
        for node in [
            self.detection_node,
            self.tracking_node,
            self.face_node,
            self.gaze_node,
            self.skeleton_node,
            self.behavior_node,
            self.risk_node,
            self.evidence_node,
        ]:
            state = node(state)
        state = await self.gemini_node(state)
        return self.report_node(state)

    def run(self, initial_state: SurveillanceState) -> SurveillanceState:
        return asyncio.run(self.run_async(initial_state))

    def _build_fusion_input(self, state: SurveillanceState) -> FusionInput:
        face = state.get("face_analysis", {}) or {}
        gaze = state.get("gaze_analysis", {}) or {}
        skeleton = state.get("skeleton_analysis", {}) or {}
        detections = state.get("detections", []) or []
        gaze_dir = str(gaze.get("gaze") or gaze.get("direction") or "").upper()
        return FusionInput(
            gaze_left_score=gaze.get("confidence", 0.0) if gaze_dir == "LEFT" else 0.0,
            gaze_right_score=gaze.get("confidence", 0.0) if gaze_dir == "RIGHT" else 0.0,
            gaze_down_score=gaze.get("confidence", 0.0) if gaze_dir == "DOWN" else 0.0,
            head_yaw_degrees=float(face.get("yaw") or 0.0),
            head_pitch_degrees=float(face.get("pitch") or 0.0),
            head_roll_degrees=float(face.get("roll") or 0.0),
            leaning_score=float(skeleton.get("leaning_severity") or 0.0),
            wrist_below_desk_score=float(skeleton.get("wrist_movement_severity") or 0.0),
            arm_extension_score=float(skeleton.get("arm_movement_severity") or 0.0),
            shoulder_movement_score=min(1.0, abs(float(skeleton.get("shoulder_angle_degrees") or 0.0)) / 45.0),
            phone_visible_score=max((d.get("confidence", 0.0) for d in detections if d.get("class") in {"mobile", "cell phone"}), default=0.0),
        )

    def _gemini_payload(self, state: SurveillanceState) -> Dict[str, Any]:
        risk = state.get("risk", {})
        gaze = state.get("gaze_analysis", {}) or {}
        face = state.get("face_analysis", {}) or {}
        skeleton = state.get("skeleton_analysis", {}) or {}
        return {
            "student_id": state.get("student_id", "UNKNOWN"),
            "seat": state.get("seat", state.get("student_id", "UNKNOWN")),
            "camera": state.get("camera_id", "CAM_01"),
            "risk_score": risk.get("risk_score", 0),
            "risk_level": risk.get("level"),
            "eye_gaze": gaze.get("gaze") or gaze.get("direction"),
            "head_pose": face.get("head_pose"),
            "pose": "LEANING" if skeleton.get("leaning_detected") else "HIDDEN_HAND" if skeleton.get("wrist_below_desk") else "NORMAL",
            "mobile_detected": any(d.get("class") in {"mobile", "cell phone"} for d in state.get("detections", [])),
            "timeline": state.get("timeline", []),
            "behaviors": state.get("behaviors", []),
            "tracking_id": state.get("tracking_id"),
            "evidence_id": (state.get("evidence") or {}).get("evidence_id"),
        }

    def _track_to_dict(self, track: Any, state: SurveillanceState) -> Dict[str, Any]:
        tracking_id = int(getattr(track, "track_id", 0))
        return {
            "student_id": state.get("seat_map", {}).get(tracking_id, f"S{tracking_id:02d}"),
            "tracking_id": tracking_id,
            "bbox": list(getattr(track, "bbox", [])),
            "confidence": float(getattr(track, "confidence", 0.0)),
        }


def build_workflow(pipeline: Optional[SurveillanceWorkflow] = None):
    """Build a LangGraph StateGraph when installed, otherwise return executable workflow."""
    pipeline = pipeline or SurveillanceWorkflow()
    if StateGraph is None:
        return pipeline

    graph = StateGraph(SurveillanceState)
    graph.add_node("detection", pipeline.detection_node)
    graph.add_node("tracking", pipeline.tracking_node)
    graph.add_node("face", pipeline.face_node)
    graph.add_node("gaze", pipeline.gaze_node)
    graph.add_node("skeleton", pipeline.skeleton_node)
    graph.add_node("behavior", pipeline.behavior_node)
    graph.add_node("risk", pipeline.risk_node)
    graph.add_node("evidence", pipeline.evidence_node)
    graph.add_node("gemini", pipeline.gemini_node)
    graph.add_node("report", pipeline.report_node)
    graph.set_entry_point("detection")
    for left, right in zip(WORKFLOW_STEPS, WORKFLOW_STEPS[1:]):
        graph.add_edge(left, right)
    graph.add_edge("report", END)
    return graph.compile()
