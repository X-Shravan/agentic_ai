"""Gemini Vision verification engine for scientific calculators.
Completely standalone module; independent of Book, Answer Sheet, Mobile, and Smartwatch systems.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from calculator_verification.config import CalculatorConfig
from calculator_verification.models import (
    CalculatorCandidate,
    CalculatorClassification,
    CalculatorObjectType,
    CalculatorVerificationResult,
)

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from PIL import Image
except Exception as exc:
    genai = None
    logger.warning("Generative AI or PIL dependencies missing in calculator verifier: %s", exc)


class CalculatorGeminiVerifier:
    """Asynchronously verifies live candidate crops with Gemini Vision."""

    def __init__(self, config: Optional[CalculatorConfig] = None):
        self.config = config or CalculatorConfig()
        
        # Ensure fresh loading of active GEMINI_API_KEY from project .env
        try:
            root_env = Path(__file__).resolve().parent.parent / ".env"
            if root_env.exists():
                load_dotenv(dotenv_path=root_env, override=True)
            else:
                load_dotenv(override=True)
        except Exception as e:
            logger.debug("Could not load dotenv in calculator verifier: %s", e)

        self.api_key = (
            self.config.gemini_api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        self.model = None
        self.reference_images: List[Any] = []

        # Circuit breaker / rate-limit backoff state
        self._circuit_breaker_until: float = 0.0
        self._consecutive_429: int = 0

        # In-memory verification cache:
        # Key: (camera_id, track_id) or spatial key -> CalculatorVerificationResult
        self.cache: Dict[Any, CalculatorVerificationResult] = {}
        self._in_flight_tasks: set = set()

        if self.config.enabled and self.api_key and genai is not None:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.config.gemini_model)
                logger.info(
                    "Calculator Gemini Verifier initialized using model %s",
                    self.config.gemini_model,
                )
                self._load_reference_images()
            except Exception as e:
                logger.error("Failed to initialize Calculator Gemini model: %s", e)

        self.prompt = """
You are an expert visual analyzer evaluating whether a detected handheld object is an approved scientific calculator for an exam.

Question:
Is this object a scientific calculator?

Your ONLY task is to determine whether the cropped object is:
1. scientific_calculator
2. not_scientific_calculator
3. uncertain

Rules:
- A scientific calculator typically has a multi-line mathematical LCD/matrix display, numeric keypad, and scientific/trigonometric/function keys (e.g. sin, cos, log, brackets, shift/alpha).
- A smartphone or mobile phone is NOT a scientific calculator (classify as not_scientific_calculator).
- A book, paper sheet, or notebook is NOT a scientific calculator (classify as not_scientific_calculator).
- A smartwatch or wristwatch is NOT a scientific calculator (classify as not_scientific_calculator).
- If the object is too blurry or obscured to identify reliably, classify as uncertain.

Return ONLY structured JSON:
{
  "classification": "scientific_calculator" | "not_scientific_calculator" | "uncertain",
  "confidence": 0.0 - 1.0,
  "reason": "short explanation of visual features observed"
}
"""

    def _load_reference_images(self) -> None:
        """Load optional reference images exclusively from reference_data/calculator/."""
        ref_dir = self.config.reference_dir
        if not ref_dir.exists():
            return
        try:
            for fname in sorted(os.listdir(ref_dir)):
                if fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    fpath = ref_dir / fname
                    with Image.open(fpath) as img:
                        self.reference_images.append(img.convert("RGB").copy())
                        logger.info("Loaded calculator reference image: %s", fname)
                        if len(self.reference_images) >= 2:
                            break
        except Exception as err:
            logger.warning("Error reading calculator reference images: %s", err)

    def crop_candidate_from_frame(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
    ) -> Optional[np.ndarray]:
        """Crop candidate region from the CURRENT live camera frame."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        h_f, w_f = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(w_f - 1, int(x1)))
        y1 = max(0, min(h_f - 1, int(y1)))
        x2 = max(x1 + 1, min(w_f, int(x2)))
        y2 = max(y1 + 1, min(h_f, int(y2)))

        if (x2 - x1) < 16 or (y2 - y1) < 16:
            return None

        return frame[y1:y2, x1:x2].copy()

    def get_cached_result(
        self,
        camera_id: str,
        track_id: Optional[int],
        bbox: Tuple[int, int, int, int],
    ) -> Optional[CalculatorVerificationResult]:
        """Check if a fresh verification result is cached for this track or spatial region."""
        now = time.time()
        cache_key = (camera_id, track_id) if track_id is not None else None

        # 1. Track ID cache
        if cache_key and cache_key in self.cache:
            res = self.cache[cache_key]
            if (now - res.timestamp) < self.config.cache_duration:
                # Validate spatial consistency
                if bbox == (0, 0, 0, 0) or not res.bbox or res.bbox == (0, 0, 0, 0):
                    return res
                iou = self._compute_iou(bbox, res.bbox)
                if iou >= self.config.spatial_iou_threshold:
                    return res
                c1 = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
                c2 = ((res.bbox[0] + res.bbox[2]) // 2, (res.bbox[1] + res.bbox[3]) // 2)
                dist = ((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)**0.5
                diag = ((bbox[2] - bbox[0])**2 + (bbox[3] - bbox[1])**2)**0.5
                if dist < max(60.0, diag * 0.8):
                    return res

        # 2. Spatial cache lookup for candidates without confirmed track IDs
        for key, res in list(self.cache.items()):
            if isinstance(key, tuple) and key[0] == camera_id:
                if (now - res.timestamp) < self.config.cache_duration:
                    if self._compute_iou(bbox, res.bbox) >= 0.50:
                        return res

        return None

    async def verify_crop(
        self,
        crop: np.ndarray,
        bbox: Tuple[int, int, int, int] = (0, 0, 0, 0),
        track_id: Optional[int] = None,
    ) -> CalculatorVerificationResult:
        """
        Verify live crop with Gemini Vision.
        Returns a structured CalculatorVerificationResult.
        """
        now = time.time()
        if crop is None or crop.size == 0 or crop.shape[0] < 16 or crop.shape[1] < 16:
            return CalculatorVerificationResult(
                object_type=CalculatorObjectType.UNKNOWN.value,
                classification=CalculatorClassification.UNCERTAIN.value,
                confidence=0.0,
                safe=False,
                reason="Invalid or empty crop",
                bbox=bbox,
                timestamp=now,
                track_id=track_id,
                verification_status="uncertain",
            )

        # Check circuit breaker cooldown
        if now < self._circuit_breaker_until:
            remaining = self._circuit_breaker_until - now
            logger.warning("[GEMINI] 429 temporarily unavailable (cooling down %.1fs)", remaining)
            return CalculatorVerificationResult(
                object_type=CalculatorObjectType.UNKNOWN.value,
                classification=CalculatorClassification.UNCERTAIN.value,
                confidence=0.0,
                safe=False,
                reason="Gemini temporarily unavailable (circuit breaker cooldown)",
                bbox=bbox,
                timestamp=now,
                track_id=track_id,
                verification_status="temporarily_unavailable",
            )

        if not self.config.enabled or not self.model:
            return CalculatorVerificationResult(
                object_type=CalculatorObjectType.UNKNOWN.value,
                classification=CalculatorClassification.UNCERTAIN.value,
                confidence=0.0,
                safe=False,
                reason="Gemini Vision verifier disabled or unconfigured",
                bbox=bbox,
                timestamp=now,
                track_id=track_id,
                verification_status="temporarily_unavailable",
            )

        logger.info("[GEMINI] Calculator analysis started")

        try:
            # Convert BGR CV2 crop to RGB PIL Image
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            pil_crop = Image.fromarray(crop_rgb)

            # Build multimodal prompt
            contents = []
            if self.reference_images:
                contents.append("Here is an example reference image of an approved scientific calculator:")
                contents.extend(self.reference_images)

            contents.extend([
                "Here is the live camera crop to evaluate:",
                pil_crop,
                self.prompt,
            ])

            # Non-blocking API call run in thread pool
            response = await asyncio.to_thread(
                self.model.generate_content,
                contents,
                generation_config={
                    "max_output_tokens": 300,
                    "temperature": 0.1,
                },
            )

            # Reset circuit breaker on successful API response
            self._consecutive_429 = 0
            self._circuit_breaker_until = 0.0

            parsed = self._parse_gemini_response(response.text)
            result = self._build_result(parsed, bbox=bbox, track_id=track_id, timestamp=now)
            logger.info("[GEMINI] Calculator result=%s", result.classification)
            return result

        except Exception as exc:
            err_msg = str(exc).lower()
            if "429" in err_msg or "resourceexhausted" in err_msg or "quota" in err_msg:
                self._consecutive_429 += 1
                cooldown = min(60.0, self.config.cooldown_duration * (2 ** min(self._consecutive_429 - 1, 3)))
                self._circuit_breaker_until = time.time() + cooldown
                logger.warning("[GEMINI] 429 temporarily unavailable")
                return CalculatorVerificationResult(
                    object_type=CalculatorObjectType.UNKNOWN.value,
                    classification=CalculatorClassification.UNCERTAIN.value,
                    confidence=0.0,
                    safe=False,
                    reason=f"Gemini API error (429 rate limit / quota exceeded): {exc}",
                    bbox=bbox,
                    timestamp=now,
                    track_id=track_id,
                    verification_status="temporarily_unavailable",
                )
            elif "timeout" in err_msg or "deadline" in err_msg:
                logger.warning("[GEMINI] Timeout")
                return CalculatorVerificationResult(
                    object_type=CalculatorObjectType.UNKNOWN.value,
                    classification=CalculatorClassification.UNCERTAIN.value,
                    confidence=0.0,
                    safe=False,
                    reason=f"Gemini API error (timeout): {exc}",
                    bbox=bbox,
                    timestamp=now,
                    track_id=track_id,
                    verification_status="temporarily_unavailable",
                )
            elif "500" in err_msg or "503" in err_msg or "unavailable" in err_msg or "connection" in err_msg:
                logger.warning("[CALCULATOR] Gemini service temporarily unavailable: %s", exc)
                return CalculatorVerificationResult(
                    object_type=CalculatorObjectType.UNKNOWN.value,
                    classification=CalculatorClassification.UNCERTAIN.value,
                    confidence=0.0,
                    safe=False,
                    reason=f"Gemini API error (temporarily unavailable): {exc}",
                    bbox=bbox,
                    timestamp=now,
                    track_id=track_id,
                    verification_status="temporarily_unavailable",
                )
            else:
                logger.warning("[CALCULATOR] Gemini API exception: %s", exc)
                return CalculatorVerificationResult(
                    object_type=CalculatorObjectType.UNKNOWN.value,
                    classification=CalculatorClassification.UNCERTAIN.value,
                    confidence=0.0,
                    safe=False,
                    reason=f"Gemini API error: {exc}",
                    bbox=bbox,
                    timestamp=now,
                    track_id=track_id,
                    verification_status="uncertain",
                )

    def trigger_async_verification(
        self,
        frame: np.ndarray,
        candidate: CalculatorCandidate,
        camera_id: str = "cam_0",
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Spawn a non-blocking background task to verify a candidate without blocking WebRTC."""
        cache_key = (camera_id, candidate.track_id or candidate.bbox)
        if cache_key in self._in_flight_tasks:
            return

        # Check existing cache
        cached = self.get_cached_result(camera_id, candidate.track_id, candidate.bbox)
        if cached is not None:
            return

        crop = self.crop_candidate_from_frame(frame, candidate.bbox)
        if crop is None:
            return

        self._in_flight_tasks.add(cache_key)

        async def _run():
            try:
                res = await self.verify_crop(crop, bbox=candidate.bbox, track_id=candidate.track_id)
                target_key = (camera_id, candidate.track_id) if candidate.track_id is not None else (camera_id, candidate.bbox)
                self.cache[target_key] = res
                logger.info(
                    "🧮 [CALCULATOR VERIFIED] Result: %s (safe=%s, conf=%.2f) Reason: %s",
                    res.classification,
                    res.safe,
                    res.confidence,
                    res.reason,
                )
            finally:
                self._in_flight_tasks.discard(cache_key)

        try:
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(_run(), loop)
            else:
                asyncio.create_task(_run())
        except Exception as err:
            self._in_flight_tasks.discard(cache_key)
            logger.debug("Could not schedule async calculator task: %s", err)

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Extract and parse structured JSON from Gemini's response."""
        try:
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            raw_json = match.group(0) if match else response_text
            data = json.loads(raw_json)

            classification = str(data.get("classification", "uncertain")).strip().lower()
            if "not_scientific_calculator" in classification or "not calculator" in classification or "not_calculator" in classification:
                final_class = CalculatorClassification.NOT_SCIENTIFIC_CALCULATOR.value
            elif "scientific_calculator" in classification or "scientific calculator" in classification:
                final_class = CalculatorClassification.SCIENTIFIC_CALCULATOR.value
            else:
                final_class = CalculatorClassification.UNCERTAIN.value

            confidence = float(data.get("confidence", 0.0))
            reason = str(data.get("reason", "No reason provided"))

            return {
                "classification": final_class,
                "confidence": max(0.0, min(1.0, confidence)),
                "reason": reason,
                "verification_status": "verified",
            }
        except Exception as e:
            logger.warning("[GEMINI] Invalid response: %s", e)
            return {
                "classification": CalculatorClassification.UNCERTAIN.value,
                "confidence": 0.0,
                "reason": f"Response parse error: {str(e)}",
                "verification_status": "uncertain",
            }

    def _build_result(
        self,
        parsed: Dict[str, Any],
        bbox: Tuple[int, int, int, int],
        track_id: Optional[int],
        timestamp: float,
    ) -> CalculatorVerificationResult:
        """Map Gemini classification output to standardized safety and object types."""
        classification = parsed.get("classification", CalculatorClassification.UNCERTAIN.value)
        confidence = float(parsed.get("confidence", 0.0))
        reason = parsed.get("reason", "")
        verification_status = parsed.get("verification_status", "verified")

        if classification == CalculatorClassification.SCIENTIFIC_CALCULATOR.value and confidence >= self.config.confidence_threshold:
            object_type = CalculatorObjectType.SCIENTIFIC_CALCULATOR.value
            safe = True
        elif classification == CalculatorClassification.NOT_SCIENTIFIC_CALCULATOR.value:
            object_type = CalculatorObjectType.NOT_CALCULATOR.value
            safe = False
        else:
            object_type = CalculatorObjectType.UNKNOWN.value
            safe = False

        return CalculatorVerificationResult(
            object_type=object_type,
            classification=classification,
            confidence=confidence,
            safe=safe,
            reason=reason,
            bbox=bbox,
            timestamp=timestamp,
            track_id=track_id,
            verification_status=verification_status,
        )

    def _parse_gemini_detection_response(self, response_text: str) -> Dict[str, Any]:
        """Extract and parse structured JSON from Gemini visual object detection response."""
        try:
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            raw_json = match.group(0) if match else response_text
            data = json.loads(raw_json)

            found = bool(data.get("found", False))
            label = str(data.get("label", "")).strip().lower()
            if "scientific_calculator" in label or "scientific calculator" in label:
                found = True
            elif "none" in label or "not" in label:
                found = False

            confidence = float(data.get("confidence", 0.0))
            box_2d = data.get("box_2d", [])
            reason = str(data.get("reason", "No reason provided"))

            return {
                "found": found,
                "label": "scientific_calculator" if found else "none",
                "confidence": max(0.0, min(1.0, confidence)),
                "box_2d": box_2d if isinstance(box_2d, list) else [],
                "reason": reason,
            }
        except Exception as e:
            logger.warning("Failed to parse Gemini calculator visual detection JSON: %s", e)
            return {
                "found": False,
                "label": "none",
                "confidence": 0.0,
                "box_2d": [],
                "reason": f"Parse error: {str(e)}",
            }

    async def detect_calculator_box(
        self,
        frame: np.ndarray,
        search_region: Optional[Tuple[int, int, int, int]] = None,
        camera_id: str = "cam_0",
        track_id: Optional[int] = None,
    ) -> Optional[CalculatorVerificationResult]:
        """
        Visual object detection option using Gemini Vision to identify a scientific calculator
        and return normalized bounding boxes in structured output converted to actual frame dimensions.
        """
        now = time.time()
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None

        h_f, w_f = frame.shape[:2]
        rx1, ry1, rx2, ry2 = search_region if search_region else (0, 0, w_f, h_f)
        rx1 = max(0, min(w_f - 1, int(rx1)))
        ry1 = max(0, min(h_f - 1, int(ry1)))
        rx2 = max(rx1 + 1, min(w_f, int(rx2)))
        ry2 = max(ry1 + 1, min(h_f, int(ry2)))

        search_crop = frame[ry1:ry2, rx1:rx2].copy()
        if search_crop.shape[0] < 16 or search_crop.shape[1] < 16:
            return None

        if not self.config.enabled or not self.model:
            return None

        detection_prompt = """
You are an expert visual analyzer detecting scientific calculators in an exam surveillance camera feed.
Your ONLY task is to locate any SCIENTIFIC CALCULATOR in the provided image.

Rules:
- Identify ONLY a scientific calculator (characterized by multi-line mathematical LCD display, numeric keypad, and scientific/trigonometric function keys).
- A mobile phone or smartphone is NOT a scientific calculator.
- A textbook, notebook, or answer sheet is NOT a scientific calculator.
- A smartwatch or wristwatch is NOT a scientific calculator.
- If a scientific calculator is visible, return its normalized 2D bounding box [ymin, xmin, ymax, xmax].
- If NO scientific calculator is visible, return found: false and empty box_2d: [].

Return ONLY structured JSON:
{
  "found": true | false,
  "label": "scientific_calculator" | "none",
  "confidence": 0.0 - 1.0,
  "box_2d": [ymin, xmin, ymax, xmax],
  "reason": "short description of visual features observed"
}
"""
        try:
            crop_rgb = cv2.cvtColor(search_crop, cv2.COLOR_BGR2RGB)
            pil_crop = Image.fromarray(crop_rgb)

            contents = [
                "Locate any scientific calculator in this image:",
                pil_crop,
                detection_prompt,
            ]

            response = await asyncio.to_thread(
                self.model.generate_content,
                contents,
                generation_config={
                    "max_output_tokens": 300,
                    "temperature": 0.1,
                },
            )

            parsed = self._parse_gemini_detection_response(response.text)
            if not parsed.get("found"):
                return None

            box_2d = parsed.get("box_2d")
            if not box_2d or len(box_2d) != 4:
                return None

            ymin_raw, xmin_raw, ymax_raw, xmax_raw = [float(v) for v in box_2d]
            # Normalize to 0.0 - 1.0 (handling 0-1000 scale if returned)
            if any(v > 1.5 for v in (ymin_raw, xmin_raw, ymax_raw, xmax_raw)):
                ymin_raw /= 1000.0
                xmin_raw /= 1000.0
                ymax_raw /= 1000.0
                xmax_raw /= 1000.0

            ymin_norm = max(0.0, min(1.0, ymin_raw))
            xmin_norm = max(0.0, min(1.0, xmin_raw))
            ymax_norm = max(0.0, min(1.0, ymax_raw))
            xmax_norm = max(0.0, min(1.0, xmax_raw))

            reg_w = rx2 - rx1
            reg_h = ry2 - ry1

            px_x1 = int(rx1 + xmin_norm * reg_w)
            px_y1 = int(ry1 + ymin_norm * reg_h)
            px_x2 = int(rx1 + xmax_norm * reg_w)
            px_y2 = int(ry1 + ymax_norm * reg_h)

            px_x1 = max(0, min(w_f - 1, px_x1))
            px_y1 = max(0, min(h_f - 1, px_y1))
            px_x2 = max(px_x1 + 1, min(w_f, px_x2))
            px_y2 = max(px_y1 + 1, min(h_f, px_y2))

            conf = float(parsed.get("confidence", 0.85))
            reason = str(parsed.get("reason", "Visual detection"))

            result = CalculatorVerificationResult(
                object_type=CalculatorObjectType.SCIENTIFIC_CALCULATOR.value,
                classification=CalculatorClassification.SCIENTIFIC_CALCULATOR.value,
                confidence=conf,
                safe=True,
                reason=reason,
                bbox=(px_x1, px_y1, px_x2, px_y2),
                timestamp=now,
                track_id=track_id,
            )

            # Store in cache
            target_key = (camera_id, track_id) if track_id is not None else (camera_id, (px_x1, px_y1, px_x2, px_y2))
            self.cache[target_key] = result
            return result

        except Exception as exc:
            logger.warning("Gemini visual object detection failed for calculator: %s", exc)
            return None

    @staticmethod
    def _compute_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        area1 = max(1, (x2_1 - x1_1) * (y2_1 - y1_1))
        area2 = max(1, (x2_2 - x1_2) * (y2_2 - y1_2))
        union_area = area1 + area2 - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

