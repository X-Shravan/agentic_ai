"""Gemini reasoning agent for privacy-safe structured surveillance events."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from google.api_core.exceptions import GoogleAPIError
except Exception:  # pragma: no cover - optional dependency in local deployments
    genai = None

    class GoogleAPIError(Exception):
        pass


GEMINI_SYSTEM_PROMPT = """You are an AI Invigilation Assistant.

You receive structured surveillance events.

You never analyze video.

You never perform detection.

You explain AI findings.

You generate risk interpretations.

You summarize evidence.

You create professional invigilation reports.

You always indicate uncertainty when evidence is weak.

You never conclude misconduct from a single event.

You require corroborating signals."""


class GeminiReasoningEngine:
    """Uses Gemini only on structured JSON and falls back to deterministic local reasoning."""

    ALLOWED_KEYS = {
        "student_id",
        "seat",
        "camera",
        "camera_id",
        "risk_score",
        "risk_level",
        "eye_gaze",
        "head_pose",
        "pose",
        "mobile_detected",
        "timeline",
        "behaviors",
        "confidence",
        "timestamp",
        "tracking_id",
        "evidence_id",
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = model
        self.model = None
        if self.api_key and genai is not None:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model)
        logger.info("Gemini reasoning engine initialized; remote=%s", bool(self.model))

    async def analyze_alert(self, alert_metadata: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._privacy_filter(alert_metadata)
        if not self.model:
            return self._fallback_analysis(payload)
        try:
            response = await asyncio.to_thread(self._call_gemini, self._prompt(payload))
            parsed = self._parse_gemini_response(response)
            if "error" in parsed:
                return self._fallback_analysis(payload)
            return parsed
        except Exception as exc:
            logger.warning("Gemini unavailable, using local reasoning: %s", exc)
            return self._fallback_analysis(payload)

    async def analyze_student_pattern(self, student_metadata: Dict[str, Any]) -> Dict[str, Any]:
        return await self.analyze_alert(student_metadata)

    async def reason_about_scene(self, scene_metadata: Dict[str, Any]) -> Dict[str, Any]:
        scene = self._privacy_filter(scene_metadata)
        scene["students"] = [self._privacy_filter(item) for item in scene_metadata.get("students", [])[:20]]
        if not self.model:
            return self._fallback_scene(scene)
        try:
            response = await asyncio.to_thread(self._call_gemini, self._scene_prompt(scene))
            parsed = self._parse_gemini_response(response)
            return parsed if "error" not in parsed else self._fallback_scene(scene)
        except Exception:
            return self._fallback_scene(scene)

    async def explain_decision(self, decision_data: Dict[str, Any]) -> str:
        result = await self.analyze_alert(decision_data)
        return result.get("ai_explanation") or result.get("primary_assessment", "No explanation available.")

    def _privacy_filter(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        filtered = {key: metadata.get(key) for key in self.ALLOWED_KEYS if key in metadata}
        if "camera_id" in filtered and "camera" not in filtered:
            filtered["camera"] = filtered.pop("camera_id")
        return filtered

    def _prompt(self, payload: Dict[str, Any]) -> str:
        return f"""{GEMINI_SYSTEM_PROMPT}

Analyze this structured JSON only. Do not request or infer from video/images.

INPUT:
{json.dumps(payload, indent=2, default=str)}

Return valid JSON with:
- ai_explanation
- risk_interpretation
- event_summary
- recommendation
- false_positive_analysis
- dashboard_summary
- pdf_report_summary
- severity
- confidence
- evidence_strength
- uncertainty
"""

    def _scene_prompt(self, payload: Dict[str, Any]) -> str:
        return f"""{GEMINI_SYSTEM_PROMPT}

Create an exam-level report summary from structured JSON only.

INPUT:
{json.dumps(payload, indent=2, default=str)}

Return valid JSON with executive_summary, student_summary, risk_assessment, ai_findings, recommendations."""

    def _call_gemini(self, prompt: str) -> str:
        if not self.model:
            raise RuntimeError("Gemini model is not configured")
        response = self.model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 1200, "temperature": 0.2, "top_p": 0.8},
        )
        return response.text

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            return json.loads(match.group(0) if match else response_text)
        except Exception:
            return {"error": "parse_error", "raw_response": response_text}

    def _fallback_analysis(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        risk_score = float(metadata.get("risk_score") or metadata.get("overall_risk") or 0.0)
        level = metadata.get("risk_level") or self._level(risk_score)
        gaze = metadata.get("eye_gaze") or metadata.get("gaze") or "UNKNOWN"
        head_pose = metadata.get("head_pose") or "UNKNOWN"
        pose = metadata.get("pose") or "UNKNOWN"
        mobile = bool(metadata.get("mobile_detected"))
        behaviors = metadata.get("behaviors") or []
        corroborating = sum([mobile, gaze in {"LEFT", "RIGHT", "DOWN"}, head_pose in {"LEFT", "RIGHT", "DOWN"}, pose not in {"UNKNOWN", "CENTER", "NORMAL"}, bool(behaviors)])

        if mobile and corroborating >= 2:
            summary = "Possible unauthorized mobile usage behavior observed."
            recommendation = "Immediate Review" if risk_score >= 71 else "Manual Verification"
            strength = "strong"
        elif corroborating >= 2:
            summary = "Multiple suspicious behavioral signals were observed."
            recommendation = "Observe Closely"
            strength = "moderate"
        elif corroborating == 1:
            summary = "A single weak suspicious signal was observed."
            recommendation = "Continue Monitoring"
            strength = "weak"
        else:
            summary = "No suspicious activity detected."
            recommendation = "Continue Monitoring"
            strength = "weak"

        explanation = self._compose_explanation(metadata, risk_score, level, summary)
        uncertainty = "Evidence should be manually reviewed; misconduct is not concluded from one event."
        return {
            "severity": str(level).lower(),
            "confidence": 0.82 if strength == "strong" else 0.64 if strength == "moderate" else 0.45,
            "ai_explanation": explanation,
            "primary_assessment": explanation,
            "risk_interpretation": f"{risk_score:.0f} maps to {level} because corroborating structured signals produced elevated risk.",
            "event_summary": summary,
            "recommendation": recommendation,
            "false_positive_analysis": self._false_positive_text(metadata, strength),
            "dashboard_summary": self._dashboard_summary(mobile, gaze, summary),
            "pdf_report_summary": f"Executive Summary: {summary}\nRisk Assessment: {level} ({risk_score:.0f}/100).\nAI Findings: {explanation}\nRecommendations: {recommendation}.",
            "evidence_strength": strength,
            "uncertainty": uncertainty,
            "risk_factors": behaviors,
            "mitigating_factors": [] if strength != "weak" else ["Limited corroborating signals"],
            "false_positive_likelihood": 0.2 if strength == "strong" else 0.4 if strength == "moderate" else 0.65,
        }

    def _fallback_scene(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        students = metadata.get("students", [])
        critical = [s for s in students if float(s.get("risk_score", 0) or 0) >= 71]
        return {
            "executive_summary": f"Processed structured events for {len(students)} students with {len(critical)} critical cases.",
            "student_summary": students[:10],
            "risk_assessment": "Manual review recommended for high and critical risk students.",
            "ai_findings": "Only structured metadata was analyzed; no video, faces, or raw images were sent.",
            "recommendations": ["Continue monitoring", "Review corroborated critical alerts", "Document evidence before action"],
        }

    def _compose_explanation(self, metadata: Dict[str, Any], risk_score: float, level: str, summary: str) -> str:
        parts = [f"Student {metadata.get('student_id', 'UNKNOWN')} has a {level} risk score of {risk_score:.0f}."]
        if metadata.get("mobile_detected"):
            parts.append("A mobile-device signal was present.")
        if metadata.get("eye_gaze"):
            parts.append(f"Eye gaze was classified as {metadata.get('eye_gaze')}.")
        if metadata.get("head_pose"):
            parts.append(f"Head pose was classified as {metadata.get('head_pose')}.")
        if metadata.get("pose"):
            parts.append(f"Pose signal was {metadata.get('pose')}.")
        parts.append(summary)
        return " ".join(parts)

    def _false_positive_text(self, metadata: Dict[str, Any], strength: str) -> str:
        if strength == "weak":
            return "Evidence is weak or isolated. Manual review recommended before escalation."
        if metadata.get("mobile_detected") and float(metadata.get("confidence", 1.0) or 1.0) < 0.7:
            return "Mobile confidence is moderate. Corroborating gaze and pose should be reviewed manually."
        return "Signals are corroborated, but final misconduct determination requires human review."

    def _dashboard_summary(self, mobile: bool, gaze: str, summary: str) -> str:
        if mobile:
            return "Mobile usage detected. Repeated gaze shifts observed." if gaze in {"LEFT", "RIGHT", "DOWN"} else "Mobile usage detected."
        if gaze in {"LEFT", "RIGHT"}:
            return "Repeated gaze shifts observed."
        return summary

    def _level(self, score: float) -> str:
        if score <= 20:
            return "LOW"
        if score <= 40:
            return "MEDIUM"
        if score <= 70:
            return "HIGH"
        return "CRITICAL"


class GeminiBatchProcessor:
    """Processes structured alert batches asynchronously."""

    def __init__(self, reasoning_engine: GeminiReasoningEngine, batch_size: int = 5):
        self.engine = reasoning_engine
        self.batch_size = batch_size
        self.queue: List[Dict[str, Any]] = []
        self.results: Dict[str, Dict[str, Any]] = {}

    async def queue_alert(self, alert: Dict[str, Any]) -> None:
        self.queue.append(alert)
        if len(self.queue) >= self.batch_size:
            await self.process_batch()

    async def process_batch(self) -> None:
        if not self.queue:
            return
        results = await asyncio.gather(*(self.engine.analyze_alert(alert) for alert in self.queue), return_exceptions=True)
        for alert, result in zip(self.queue, results):
            alert_id = alert.get("alert_id") or alert.get("evidence_id") or str(datetime.utcnow().timestamp())
            self.results[str(alert_id)] = result if isinstance(result, dict) else {"error": str(result)}
        self.queue.clear()

    def get_result(self, alert_id: str) -> Optional[Dict[str, Any]]:
        return self.results.get(alert_id)
