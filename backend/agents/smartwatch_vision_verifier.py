"""Gemini Vision verification agent for smartwatch detection validation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from PIL import Image
except Exception as exc:
    genai = None
    logger.warning("Generative AI or PIL dependencies missing: %s", exc)


class SmartwatchVisionVerifier:
    """Uses Gemini Vision API to verify if a cropped live frame contains a smartwatch."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        vision_conf = self.config.get("gemini_vision", {})
        self.enabled = vision_conf.get("enabled", True)
        self.model_name = vision_conf.get("model", "gemini-flash-latest")
        self.threshold = vision_conf.get("threshold", 0.80)
        self.cache_duration = vision_conf.get("cache_duration", 10.0)

        # Retrieve API Key
        self.api_key = (
            self.config.get("gemini_api_key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        self.model = None
        self.reference_image = None

        if self.enabled and self.api_key and genai is not None:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(
                    "Gemini Vision Verifier initialized using model %s",
                    self.model_name,
                )
                self._load_reference_image()
            except Exception as e:
                logger.error("Failed to initialize Gemini model: %s", e)

        self.prompt = """
You are verifying an object that the existing YOLO detector has already classified as SMARTWATCH.

Your ONLY task is to determine whether the cropped object is:
1. smartwatch
2. analog_watch
3. uncertain

Do NOT classify the object as a mobile phone.
Do NOT return mobile_phone, phone, cell_phone, tablet, book, calculator, laptop, person, or any other category.

Even if the object is an electronic device, your answer must remain within the three allowed smartwatch-verification classes.

Return ONLY JSON in this format:
{
  "classification": "smartwatch" | "analog_watch" | "uncertain",
  "confidence": 0.0-1.0,
  "reason": "short visual reason"
}
"""

    def _load_reference_image(self):
        """Proactively load a representative smartwatch reference image once."""
        try:
            root_dir = Path(__file__).resolve().parent.parent.parent
            ref_dir = root_dir / "reference_data" / "smartwatch"
            if ref_dir.exists():
                for fname in os.listdir(ref_dir):
                    if fname.lower().endswith(
                        (".png", ".jpg", ".jpeg", ".jfif")
                    ):
                        fpath = ref_dir / fname
                        img = Image.open(fpath)
                        # Keep standard small size context
                        self.reference_image = img.copy()
                        logger.info(
                            "Loaded smartwatch reference image: %s", fpath.name
                        )
                        break
            if not self.reference_image:
                logger.warning("No smartwatch reference image found in %s", ref_dir)
        except Exception as e:
            logger.warning("Error loading reference image: %s", e)

    async def verify_crop(self, crop: np.ndarray) -> Dict[str, Any]:
        """
        Verify cropped image against Gemini Vision model.
        Returns: {classification: str, confidence: float, reason: str}
        """
        if not self.enabled or not self.model or crop is None or crop.size == 0:
            return {
                "classification": "uncertain",
                "confidence": 0.0,
                "reason": "Verifier disabled, unconfigured, or crop is empty",
            }

        try:
            # Convert BGR CV2 crop to RGB PIL Image
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            pil_crop = Image.fromarray(crop_rgb)

            # Build query content
            contents = []
            if self.reference_image is not None:
                contents.extend(
                    [
                        "Here is a reference image of a smartwatch:",
                        self.reference_image,
                    ]
                )
            contents.extend(
                [
                    "Here is the live crop to verify:",
                    pil_crop,
                    self.prompt,
                ]
            )

            # Non-blocking API call run in executor thread
            response = await asyncio.to_thread(
                self.model.generate_content,
                contents,
                generation_config={
                    "max_output_tokens": 300,
                    "temperature": 0.1,
                },
            )

            response_text = response.text
            parsed = self._parse_gemini_response(response_text)
            return parsed

        except Exception as exc:
            logger.error("Gemini Vision Verification failed: %s", exc)
            return {
                "classification": "uncertain",
                "confidence": 0.0,
                "reason": f"API error: {str(exc)}",
            }

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Extract and parse structured JSON from text response."""
        try:
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            data = json.loads(match.group(0) if match else response_text)
            classification = data.get("classification", "uncertain")
            
            # Map potential variations to the three valid outputs: smartwatch, analog_watch, uncertain
            if classification in {"not_smartwatch", "analog watch", "analog_watch"}:
                classification = "analog_watch"
            elif classification in {"smart_watch", "smartwatch"}:
                classification = "smartwatch"
            else:
                classification = "uncertain"
                
            confidence = float(data.get("confidence", 0.0))
            reason = data.get("reason", "No reason provided")
            return {
                "classification": classification,
                "confidence": confidence,
                "reason": reason,
            }
        except Exception as e:
            logger.warning("Failed to parse Gemini response: %s", e)
            return {
                "classification": "uncertain",
                "confidence": 0.0,
                "reason": f"Parse error: {str(e)}",
            }
