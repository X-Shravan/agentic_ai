"""
Gemini Agentic AI Reasoning Engine
Performs multi-step reasoning on surveillance metadata
Generates intelligent explanations and risk assessment
Uses structured prompting for consistent outputs
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import asdict

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)


class GeminiReasoningEngine:
    """
    Agentic AI reasoning using Gemini API
    Processes structured metadata (never video frames)
    Performs multi-step analysis and decision-making
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Initialize Gemini reasoning engine
        
        Args:
            api_key: Google Gemini API key
            model: Model to use (gemini-2.0-flash for speed, gemini-pro for quality)
        """
        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)
        
        # System prompt for consistent behavior
        self.system_prompt = """You are an expert AI invigilation system analyzing exam surveillance data.
Your role is to:
1. Interpret student behavior patterns from structured metadata
2. Assess cheating likelihood with probabilistic reasoning
3. Distinguish between innocent behavior and actual cheating
4. Provide actionable insights with confidence levels

IMPORTANT GUIDELINES:
- Analyze probabilities, not certainties
- Consider context and temporal patterns
- Distinguish between isolated incidents and persistent behavior
- Avoid bias against nervous students
- Flag only behaviors with high confidence as suspicious

OUTPUT FORMAT: Always return valid JSON with this structure:
{
  "severity": "low|medium|high|critical",
  "confidence": 0.0-1.0,
  "primary_assessment": "Brief 1-2 sentence assessment",
  "reasoning": ["Logic step 1", "Logic step 2", ...],
  "risk_factors": ["Factor 1", "Factor 2", ...],
  "mitigating_factors": ["Factor 1", "Factor 2", ...],
  "recommendation": "Recommended action",
  "evidence_strength": "weak|moderate|strong",
  "false_positive_likelihood": 0.0-1.0
}"""
        
        logger.info(f"✅ Gemini reasoning engine initialized ({model})")
    
    async def analyze_alert(self, alert_metadata: Dict) -> Dict:
        """
        Analyze alert using Gemini reasoning
        
        Args:
            alert_metadata: Structured metadata from detection pipeline
            
        Returns:
            Reasoning output with severity, confidence, explanation
        """
        try:
            # Prepare prompt
            prompt = self._prepare_alert_prompt(alert_metadata)
            
            # Call Gemini API (async)
            response = await asyncio.to_thread(
                self._call_gemini,
                prompt
            )
            
            # Parse response
            result = self._parse_gemini_response(response)
            
            logger.info(f"✅ Alert analyzed: severity={result.get('severity')}, "
                       f"confidence={result.get('confidence')}")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Gemini analysis failed: {e}")
            return self._fallback_analysis(alert_metadata)
    
    async def analyze_student_pattern(self, student_metadata: Dict) -> Dict:
        """
        Analyze overall behavior pattern for a student
        
        Args:
            student_metadata: Historical behavior data for student
            
        Returns:
            Pattern analysis with risk assessment
        """
        try:
            prompt = self._prepare_pattern_prompt(student_metadata)
            
            response = await asyncio.to_thread(
                self._call_gemini,
                prompt
            )
            
            result = self._parse_gemini_response(response)
            
            logger.info(f"✅ Student pattern analyzed: {student_metadata.get('student_id')}")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Pattern analysis failed: {e}")
            return self._fallback_pattern_analysis(student_metadata)
    
    async def reason_about_scene(self, scene_metadata: Dict) -> Dict:
        """
        Multi-step reasoning about overall classroom scene
        
        Args:
            scene_metadata: Metadata about multiple students and events
            
        Returns:
            Scene analysis with insights
        """
        try:
            prompt = self._prepare_scene_prompt(scene_metadata)
            
            response = await asyncio.to_thread(
                self._call_gemini,
                prompt
            )
            
            result = self._parse_gemini_response(response)
            
            logger.info(f"✅ Scene analyzed: {len(scene_metadata.get('students', []))} students")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Scene analysis failed: {e}")
            return {"error": str(e)}
    
    def _prepare_alert_prompt(self, metadata: Dict) -> str:
        """Prepare structured prompt for alert analysis"""
        
        return f"""{self.system_prompt}

ANALYZE THIS ALERT:

Student ID: {metadata.get('student_id')}
Timestamp: {metadata.get('timestamp', datetime.now().isoformat())}
Camera: {metadata.get('camera_id', 'unknown')}

DETECTED BEHAVIORS:
{json.dumps(metadata.get('behaviors', []), indent=2)}

RISK SCORES:
- Gaze Risk: {metadata.get('gaze_score', 0.0):.2f}
- Pose Risk: {metadata.get('pose_score', 0.0):.2f}
- Phone Detection: {metadata.get('phone_score', 0.0):.2f}
- Movement Risk: {metadata.get('movement_score', 0.0):.2f}
- Overall: {metadata.get('overall_risk', 0.0):.2f}

TEMPORAL CONTEXT:
- Time into exam: {metadata.get('time_into_exam_min', 0)} minutes
- Previous alerts: {metadata.get('alert_count', 0)}
- Behavior persistence: {metadata.get('persistence_frames', 0)} frames

CONTEXTUAL INFO:
- Exam difficulty: {metadata.get('exam_difficulty', 'unknown')}
- Student stress level (estimated): {metadata.get('stress_estimate', 'unknown')}
- Environmental conditions: {metadata.get('environment', 'standard')}

PERFORM THIS ANALYSIS:
1. Are the detected behaviors consistent with cheating?
2. What is the probability this is a false positive?
3. What is the confidence in this assessment?
4. What additional information would help clarify?
5. What should the invigilator do?

Provide your analysis in JSON format."""
    
    def _prepare_pattern_prompt(self, metadata: Dict) -> str:
        """Prepare prompt for student pattern analysis"""
        
        behavior_summary = json.dumps(metadata.get('behavior_history', []), indent=2)
        
        return f"""{self.system_prompt}

ANALYZE STUDENT BEHAVIOR PATTERN:

Student ID: {metadata.get('student_id')}
Exam: {metadata.get('exam_id', 'unknown')}
Duration analyzed: {metadata.get('duration_minutes', 0)} minutes

BEHAVIOR HISTORY:
{behavior_summary}

STATISTICS:
- Total alerts: {metadata.get('alert_count', 0)}
- Most common behavior: {metadata.get('top_behavior', 'none')}
- Alert frequency: {metadata.get('alert_frequency', 'low')}
- Risk trend: {metadata.get('risk_trend', 'stable')}

PATTERN ANALYSIS:
1. What is the overall risk profile of this student?
2. Are behaviors indicative of attempted cheating or just nervousness?
3. What is the confidence in the pattern assessment?
4. Should this student be flagged for review?

Provide your analysis in JSON format."""
    
    def _prepare_scene_prompt(self, metadata: Dict) -> str:
        """Prepare prompt for scene-level reasoning"""
        
        students_info = json.dumps(metadata.get('students', [])[:10], indent=2)  # Limit to 10
        
        return f"""{self.system_prompt}

ANALYZE CLASSROOM SCENE:

Exam: {metadata.get('exam_id', 'unknown')}
Time: {metadata.get('timestamp', datetime.now().isoformat())}
Total Students: {metadata.get('total_students', 0)}
Cameras: {metadata.get('camera_count', 0)}

HIGH-RISK STUDENTS (top 10):
{students_info}

SCENE STATISTICS:
- Overall alert rate: {metadata.get('alert_rate', 0.0):.2%}
- Students flagged: {metadata.get('flagged_count', 0)}
- Critical alerts: {metadata.get('critical_count', 0)}
- Exam difficulty estimate: {metadata.get('exam_difficulty', 'unknown')}

MULTI-STEP REASONING:
1. What is the overall exam integrity assessment?
2. Are there patterns suggesting coordinated cheating?
3. What are the most critical areas needing attention?
4. What is the confidence in this assessment?
5. What recommendations do you have for exam administration?

Provide your analysis in JSON format."""
    
    def _call_gemini(self, prompt: str) -> str:
        """Synchronous call to Gemini API"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": 1000,
                    "temperature": 0.3,  # More deterministic
                    "top_p": 0.8,
                }
            )
            return response.text
        except GoogleAPIError as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def _parse_gemini_response(self, response_text: str) -> Dict:
        """Parse Gemini response, extract JSON"""
        try:
            # Try to find JSON in response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            else:
                # If no JSON, try parsing entire response
                return json.loads(response_text)
        
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from Gemini response")
            return {
                "error": "parse_error",
                "raw_response": response_text,
            }
    
    def _fallback_analysis(self, metadata: Dict) -> Dict:
        """Fallback analysis if Gemini API fails"""
        
        overall_risk = metadata.get('overall_risk', 0.0)
        behaviors = metadata.get('behaviors', [])
        
        # Simple rule-based assessment
        if overall_risk > 70:
            severity = "critical"
            confidence = 0.7
        elif overall_risk > 50:
            severity = "high"
            confidence = 0.65
        elif overall_risk > 30:
            severity = "medium"
            confidence = 0.6
        else:
            severity = "low"
            confidence = 0.5
        
        return {
            "severity": severity,
            "confidence": confidence,
            "primary_assessment": f"Risk score: {overall_risk:.0f}/100",
            "reasoning": [f"Detected {len(behaviors)} suspicious behaviors"],
            "risk_factors": behaviors,
            "mitigating_factors": [],
            "recommendation": "Review by invigilator",
            "evidence_strength": "moderate",
            "false_positive_likelihood": 1.0 - confidence,
            "note": "Fallback analysis (Gemini unavailable)"
        }
    
    def _fallback_pattern_analysis(self, metadata: Dict) -> Dict:
        """Fallback pattern analysis"""
        return {
            "pattern": "insufficient_data",
            "confidence": 0.3,
            "recommendation": "Collect more data before assessment"
        }
    
    async def explain_decision(self, decision_data: Dict) -> str:
        """
        Generate natural language explanation for a decision
        """
        try:
            prompt = f"""Explain this exam surveillance decision in 2-3 sentences for an invigilator:

Student: {decision_data.get('student_id')}
Severity: {decision_data.get('severity')}
Primary Concern: {decision_data.get('primary_concern')}
Evidence: {json.dumps(decision_data.get('backend/evidence', []), indent=2)}

Explanation:"""
            
            response = await asyncio.to_thread(
                self._call_gemini,
                prompt
            )
            
            return response.strip()
        
        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            return "Unable to generate explanation"


class GeminiBatchProcessor:
    """Process multiple alerts asynchronously using Gemini"""
    
    def __init__(self, reasoning_engine: GeminiReasoningEngine, batch_size: int = 5):
        self.engine = reasoning_engine
        self.batch_size = batch_size
        self.queue: List[Dict] = []
        self.results: Dict[str, Dict] = {}
    
    async def queue_alert(self, alert: Dict):
        """Queue alert for batch processing"""
        self.queue.append(alert)
        
        # Process batch if full
        if len(self.queue) >= self.batch_size:
            await self.process_batch()
    
    async def process_batch(self):
        """Process queued alerts in batch"""
        if not self.queue:
            return
        
        logger.info(f"🔄 Processing batch of {len(self.queue)} alerts with Gemini...")
        
        tasks = [
            self.engine.analyze_alert(alert)
            for alert in self.queue
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for alert, result in zip(self.queue, results):
            alert_id = alert.get('alert_id', str(datetime.now().timestamp()))
            self.results[alert_id] = result if isinstance(result, dict) else {"error": str(result)}
        
        self.queue.clear()
        logger.info(f"✅ Batch processing complete ({len(self.results)} results)")
    
    def get_result(self, alert_id: str) -> Optional[Dict]:
        """Get result for a specific alert"""
        return self.results.get(alert_id)
