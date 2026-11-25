"""Gemini Vision and OpenCV verification agent for examination answer sheet validation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from PIL import Image
except Exception as exc:
    genai = None
    logger.warning("Generative AI or PIL dependencies missing: %s", exc)


class AnswerSheetVisionVerifier:
    """Uses Gemini Vision API and local CV checks to verify if a cropped live frame contains the college answer sheet."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # Centralized configurations under book_verification or answer_sheet_verify
        b_cfg = (
            self.config.get("book_verification")
            or self.config.get("answer_sheet_verify")
            or self.config.get("white_page_verify")
            or {}
        )
        self.enabled = b_cfg.get("enabled", True)
        self.threshold = float(b_cfg.get("threshold", 0.80))
        self.cache_duration = float(b_cfg.get("cache_duration", 10.0))

        # Centralized thresholds (supporting both snake_case and UPPER_CASE)
        self.white_min_value = int(
            b_cfg.get("white_min_value")
            or b_cfg.get("WHITE_MIN_VALUE", 95)
        )
        self.white_max_saturation = int(
            b_cfg.get("white_max_saturation")
            or b_cfg.get("WHITE_MAX_SATURATION", 55)
        )
        self.answer_sheet_white_ratio = float(
            b_cfg.get("answer_sheet_white_ratio")
            or b_cfg.get("white_area_threshold")
            or b_cfg.get("ANSWER_SHEET_WHITE_RATIO", 0.95)
        )
        self.white_area_threshold = self.answer_sheet_white_ratio

        self.colorful_area_ratio = float(
            b_cfg.get("colorful_area_ratio")
            or b_cfg.get("COLORFUL_AREA_RATIO", 0.20)
        )
        self.page_geometry_threshold = float(
            b_cfg.get("page_geometry_threshold")
            or b_cfg.get("PAGE_GEOMETRY_THRESHOLD", 0.60)
        )
        self.ruled_line_threshold = float(
            b_cfg.get("ruled_line_threshold")
            or b_cfg.get("RULED_LINE_THRESHOLD", 0.20)
        )
        self.analysis_margin_ratio = float(
            b_cfg.get("analysis_margin_ratio")
            or b_cfg.get("ANALYSIS_MARGIN_RATIO", 0.08)
        )
        self.temporal_confirmation_frames = int(
            b_cfg.get("temporal_confirmation_frames")
            or b_cfg.get("TEMPORAL_CONFIRMATION_FRAMES", 3)
        )

        self.min_page_width = int(
            b_cfg.get("min_page_width")
            or b_cfg.get("candidate_min_width")
            or self.config.get("MIN_PAGE_WIDTH", 25)
        )
        self.min_page_height = int(
            b_cfg.get("min_page_height")
            or b_cfg.get("candidate_min_height")
            or self.config.get("MIN_PAGE_HEIGHT", 25)
        )
        self.max_page_aspect_ratio = float(
            b_cfg.get("max_page_aspect_ratio")
            or b_cfg.get("candidate_aspect_ratio_max")
            or self.config.get("MAX_PAGE_ASPECT_RATIO", 3.5)
        )
        self.min_dim = int(b_cfg.get("min_dimension", 30))
        self.white_ratio_min = self.answer_sheet_white_ratio

        # Gemini settings
        try:
            from dotenv import load_dotenv
            root_env = Path(__file__).resolve().parent.parent.parent / ".env"
            if root_env.exists():
                load_dotenv(dotenv_path=root_env, override=False)
            else:
                load_dotenv(override=False)
        except Exception:
            pass

        vision_conf = self.config.get("gemini_vision", {})
        self.model_name = vision_conf.get("model", "gemini-flash-latest")
        self.api_key = (
            self.config.get("gemini_api_key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        self.model = None
        self.reference_images = []

        if self.enabled and self.api_key and genai is not None:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(
                    "Gemini Vision Answer Sheet Verifier initialized using model %s",
                    self.model_name,
                )
                self._load_reference_images()
            except Exception as e:
                logger.error("Failed to initialize Gemini model for answer sheet: %s", e)

        self.prompt = """You are verifying whether the TARGET image is the examination answer sheet used by this college.

The target may appear in:
- portrait orientation
- landscape orientation
- rotated orientation
- tilted perspective
- different distances
- different lighting
- partially covered by a hand

Do NOT reject the target because of portrait or landscape orientation.
Do not reject an answer sheet because of orientation.
Compare visual structure rather than orientation.
A white textbook is still a textbook.

Compare the TARGET with the reference answer-sheet examples based on visual structure.

Look for:
- white examination paper
- rectangular page
- printed border
- horizontal ruled lines
- margins
- college-specific layout
- logo/branding when visible
- page structure
- overall visual appearance

Do NOT classify something as an answer sheet only because it is white.

A textbook or book must remain NOT_ANSWER_SHEET.

Return ONLY JSON:

{
  "classification": "answer_sheet | not_answer_sheet | uncertain",
  "confidence": 0.0,
  "reason": "short explanation"
}
"""

    def _load_reference_images(self):
        """Proactively load representative answer sheet reference images once and cache in memory."""
        try:
            root_dir = Path(__file__).resolve().parent.parent.parent
            ref_dir = root_dir / "reference_data" / "answer_sheet"
            if ref_dir.exists():
                # Load representative set: portrait (e.g. ans1.jpeg) and landscape (ans10.jpeg)
                fnames = sorted(os.listdir(ref_dir))
                count = 0
                for fname in fnames:
                    if fname.lower().endswith((".png", ".jpg", ".jpeg", ".jfif")):
                        fpath = ref_dir / fname
                        try:
                            with Image.open(fpath) as img:
                                # Ensure RGB and compact size for fast API transmission
                                img_copy = img.convert("RGB")
                                img_copy.thumbnail((512, 512))
                                self.reference_images.append(img_copy)
                            logger.info("Loaded answer sheet reference image: %s", fname)
                            count += 1
                            if count >= 3:
                                break
                        except Exception as e:
                            logger.warning("Failed to open reference image %s: %s", fname, e)
            if not self.reference_images:
                logger.warning("No answer sheet reference images found in %s", ref_dir)
        except Exception as e:
            logger.warning("Error loading reference images: %s", e)

    def verify_candidate_semantics(self, crop: np.ndarray, yolo_conf: float = 0.30) -> Tuple[str, float, Dict[str, Any]]:
        """
        Lightweight multi-signal OpenCV semantic verifier for BOOK vs ANSWER_SHEET decision.
        Evaluates:
        - Inner analysis region (ANALYSIS_MARGIN_RATIO) to strip desk/wall contamination.
        - Signal 1: Near-white area ratio in HSV.
        - Signal 2: Color diversity / colorful cover check (saturation & colorfulness metric).
        - Signal 3: Page-like geometry (orientation-agnostic: portrait, landscape, tilted).
        - Signal 4: Horizontal / parallel ruled-line structure.
        
        Returns:
            (classification: "answer_sheet" | "book", confidence: float, details: dict)
        """
        if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
            return "book", 0.80, {"error": "empty_crop", "result": "book"}

        try:
            h, w = crop.shape[:2]
            
            # Dimensions check
            if w < self.min_page_width or h < self.min_page_height:
                return "book", 0.80, {
                    "error": f"Crop dimensions {w}x{h} below minimum",
                    "white_ratio": 0.0,
                    "color_ratio": 0.0,
                    "geometry_score": 0.0,
                    "line_score": 0.0,
                    "result": "book"
                }

            # Aspect ratio (orientation agnostic: long_side / short_side >= 1.0)
            short_side = float(max(1, min(w, h)))
            long_side = float(max(w, h))
            aspect_ratio = long_side / short_side
            orientation = "portrait" if h >= w else "landscape"

            # Geometry score: reasonable aspect ratio [1.0, 3.5]
            geom_ok = (1.0 <= aspect_ratio <= self.max_page_aspect_ratio)
            geom_score = 1.0 if (geom_ok and aspect_ratio <= 2.5) else (0.75 if geom_ok else 0.30)

            # Inner analysis region (strip outer margin to reduce desk/wall background contamination)
            mx = int(w * self.analysis_margin_ratio)
            my = int(h * self.analysis_margin_ratio)
            if (w - 2 * mx) >= 16 and (h - 2 * my) >= 16:
                inner_crop = crop[my:h - my, mx:w - mx]
            else:
                inner_crop = crop

            # Convert inner crop to HSV
            hsv = cv2.cvtColor(inner_crop, cv2.COLOR_BGR2HSV)
            total_inner_pixels = float(hsv.shape[0] * hsv.shape[1])

            # Signal 1: Near-white area ratio (low saturation, moderate-to-high brightness)
            lower_white = np.array([0, 0, self.white_min_value], dtype=np.uint8)
            upper_white = np.array([180, self.white_max_saturation, 255], dtype=np.uint8)
            white_mask = cv2.inRange(hsv, lower_white, upper_white)
            white_pixels = float(np.count_nonzero(white_mask))
            white_ratio = (white_pixels / total_inner_pixels) if total_inner_pixels > 0 else 0.0

            # Signal 2: Color diversity / colorful cover check
            # Saturated chromatic pixels (excluding dark shadows)
            lower_color = np.array([0, self.white_max_saturation + 1, 40], dtype=np.uint8)
            upper_color = np.array([180, 255, 255], dtype=np.uint8)
            color_mask = cv2.inRange(hsv, lower_color, upper_color)
            color_pixels = float(np.count_nonzero(color_mask))
            color_ratio = (color_pixels / total_inner_pixels) if total_inner_pixels > 0 else 0.0

            # Hasler-Suesstrunk colorfulness metric (downsampled for ultra-fast <0.5ms computation)
            small_sample = cv2.resize(inner_crop, (64, 64), interpolation=cv2.INTER_NEAREST)
            b_ch = small_sample[:, :, 0].astype(np.float32)
            g_ch = small_sample[:, :, 1].astype(np.float32)
            r_ch = small_sample[:, :, 2].astype(np.float32)
            rg = np.abs(r_ch - g_ch)
            yb = np.abs(0.5 * (r_ch + g_ch) - b_ch)
            hasler_color = float(np.sqrt(rg.std()**2 + yb.std()**2) + 0.3 * np.sqrt(rg.mean()**2 + yb.mean()**2))

            # Signal 4: Horizontal / parallel ruled-line structure (fast downsampled edge & line detection)
            scale = 200.0 / max(w, h)
            nw = max(16, int(w * scale))
            nh = max(16, int(h * scale))
            small_gray = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (nw, nh), interpolation=cv2.INTER_NEAREST)
            edges = cv2.Canny(small_gray, 30, 100)
            min_len = max(10, int(min(nw, nh) * 0.12))
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=20, minLineLength=min_len, maxLineGap=8)

            horizontal_count = 0
            parallel_count = 0
            if lines is not None:
                angles = []
                for l in lines:
                    x1_l, y1_l, x2_l, y2_l = l[0]
                    dx = abs(x2_l - x1_l)
                    dy = abs(y2_l - y1_l)
                    if dx > 0 and (dy / dx) < 0.25:
                        horizontal_count += 1
                    elif dy > 0 and (dx / dy) < 0.25:
                        horizontal_count += 1
                    angle = np.degrees(np.arctan2(dy, max(1, dx)))
                    angles.append(angle)
                if len(angles) >= 3:
                    hist, _ = np.histogram(angles, bins=6, range=(0, 90))
                    parallel_count = int(np.max(hist))

            line_score = min(1.0, max(horizontal_count, parallel_count) / 5.0)
            has_ruled_lines = (line_score >= self.ruled_line_threshold or horizontal_count >= 2)

            details = {
                "white_ratio": round(white_ratio, 3),
                "color_ratio": round(color_ratio, 3),
                "hasler_color": round(hasler_color, 1),
                "geometry_score": round(geom_score, 2),
                "geometry_pass": bool(geom_ok),
                "line_score": round(line_score, 2),
                "horizontal_count": horizontal_count,
                "orientation": orientation,
                "aspect_ratio": round(aspect_ratio, 2),
            }

            # -------------------------------------------------------------
            # STRICT TWO-STAGE DECISION: BOOK vs ANSWER_SHEET
            # -------------------------------------------------------------

            # Primary seminar rule:
            # An object can become ANSWER_SHEET ONLY when the analyzed book/page
            # surface is approximately >= 95% near-white.
            # IF near_white_ratio >= 0.95:
            #     semantic_class = ANSWER_SHEET
            # ELSE:
            #     semantic_class = BOOK
            # DO NOT classify 90% white -> ANSWER_SHEET
            # DO NOT classify 85% white -> ANSWER_SHEET
            # DO NOT classify 70% white -> ANSWER_SHEET

            is_high_white = (white_ratio >= self.answer_sheet_white_ratio)
            not_colorful = (hasler_color <= 35.0 and color_ratio < 0.05)

            if is_high_white and geom_ok and not_colorful:
                conf = min(0.99, max(0.85, 0.75 + 0.20 * white_ratio + 0.05 * line_score))
                details["result"] = "answer_sheet"
                return "answer_sheet", conf, details

            # Otherwise, strictly BOOK (colorful covers, dark covers, notebooks below 95%, etc.)
            conf = min(0.99, max(0.80, 0.75 + color_ratio * 0.25 if color_ratio > 0.20 else 0.85))
            details["result"] = "book"
            return "book", conf, details

        except Exception as exc:
            logger.error("Error in verify_candidate_semantics: %s", exc)
            return "book", 0.80, {"error": str(exc), "result": "book"}

    def verify_white_page(self, crop: np.ndarray) -> Tuple[bool, float, bool, str]:
        """
        Lightweight OpenCV near-white page verification for demo answer sheet validation.
        Maintains backward compatibility with test suites while using the multi-signal semantics.
        """
        if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
            return False, 0.0, False, "Invalid or empty crop"

        result, conf, details = self.verify_candidate_semantics(crop)
        is_answer_sheet = (result == "answer_sheet")
        white_ratio = details.get("white_ratio", 0.0)
        geom_ok = details.get("geometry_score", 0.0) >= self.page_geometry_threshold
        msg = "PASS" if is_answer_sheet else f"Classified as {result} (white={white_ratio:.2f}, color={details.get('color_ratio', 0.0):.2f})"
        return is_answer_sheet, white_ratio, geom_ok, msg

    def verify_geometry(self, crop: np.ndarray) -> Tuple[bool, float, str]:
        """
        Verify the page geometry in an orientation-independent manner.
        Used strictly as a weak supporting signal; never rejects solely on aspect ratio.
        """
        if crop is None or crop.size == 0:
            return False, 0.0, "Empty crop"
        h, w = crop.shape[:2]
        if h < self.min_dim or w < self.min_dim:
            return False, 0.0, f"Dimensions too small: {w}x{h} (min {self.min_dim})"
        
        short_side = float(min(w, h))
        long_side = float(max(w, h))
        aspect_ratio = long_side / short_side if short_side > 0 else 1.0
        
        orientation = "portrait" if h >= w else "landscape"
        
        # Geometry is a supporting signal. A wide range is permissible due to perspective/partial views.
        is_reasonable = 1.0 <= aspect_ratio <= 3.5
        msg = f"Orientation={orientation} Ratio={aspect_ratio:.2f} (weak support: {is_reasonable})"
        return is_reasonable, aspect_ratio, msg

    def verify_whiteness(self, crop: np.ndarray) -> Tuple[bool, float, str]:
        """
        Evaluate paper-like color/whiteness as a supporting feature.
        Note: High whiteness alone is NEVER sufficient to classify an answer sheet.
        """
        if crop is None or crop.size == 0:
            return False, 0.0, "Empty crop"
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        # Classroom lighting can vary; allow broad saturation and value ranges
        lower_white = np.array([0, 0, 100])
        upper_white = np.array([180, 80, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        white_ratio = float(np.sum(mask > 0) / mask.size)
        
        is_supporting = white_ratio >= self.white_ratio_min
        return is_supporting, white_ratio, f"Whiteness ratio: {white_ratio:.2f} (supporting: {is_supporting})"

    def verify_ruled_lines(self, crop: np.ndarray) -> Tuple[bool, int, str]:
        """
        Detect ruled lines / page ruling across any orientation (horizontal, vertical, or tilted/rotated).
        Supports portrait, landscape, and rotated (30°, 45°, 90°) pages.
        """
        if crop is None or crop.size == 0:
            return False, 0, "Empty crop"
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        h, w = crop.shape[:2]
        min_dim = min(h, w)
        
        edges = cv2.Canny(gray, 30, 100)
        min_len = max(15, int(min_dim * 0.15))
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=25, minLineLength=min_len, maxLineGap=15)
        
        line_count = 0
        if lines is not None:
            # Count detected lines regardless of angle (horizontal, vertical, diagonal)
            line_count = len(lines)
            
        has_lines = line_count >= 2
        return has_lines, line_count, f"Ruled/structural lines detected: {line_count}"

    def verify_crop_sync(self, crop: np.ndarray) -> Dict[str, Any]:
        """
        Synchronously verify cropped image against Gemini Vision model.
        Safe for execution in background worker threads without asyncio loop dependencies.
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
            if self.reference_images:
                contents.append("Here are reference images of the normal examination answer sheet:")
                contents.extend(self.reference_images)
                
            contents.extend(
                [
                    "Here is the target live crop to verify:",
                    pil_crop,
                    self.prompt,
                ]
            )

            # Synchronous direct Gemini call
            logger.info("[GEMINI] Answer sheet analysis started")
            response = self.model.generate_content(
                contents,
                generation_config={
                    "max_output_tokens": 300,
                    "temperature": 0.1,
                },
            )

            response_text = response.text
            parsed = self._parse_gemini_response(response_text)
            logger.info("[GEMINI] Answer sheet result=%s", parsed.get("classification"))
            return parsed

        except Exception as exc:
            err_msg = str(exc).lower()
            if "429" in err_msg or "resourceexhausted" in err_msg or "quota" in err_msg:
                logger.warning("[GEMINI] 429 temporarily unavailable")
            elif "timeout" in err_msg or "deadline" in err_msg:
                logger.warning("[GEMINI] Timeout")
            else:
                logger.warning("[GEMINI] Answer sheet verification failed: %s", exc)
            return {
                "classification": "uncertain",
                "confidence": 0.0,
                "reason": f"API error: {str(exc)}",
            }

    async def verify_crop(self, crop: np.ndarray) -> Dict[str, Any]:
        """
        Asynchronously verify cropped image against Gemini Vision model.
        Delegates to verify_crop_sync in thread pool executor.
        Returns: {classification: str, confidence: float, reason: str}
        """
        return await asyncio.to_thread(self.verify_crop_sync, crop)

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Extract and parse structured JSON from text response."""
        try:
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            data = json.loads(match.group(0) if match else response_text)
            classification = data.get("classification", "uncertain")
            
            # Map potential variations to allowed classifications
            if classification in {"answer_sheet", "answer book", "answer_book", "paper"}:
                classification = "answer_sheet"
            elif classification in {"not_answer_sheet", "not_answerbook"}:
                classification = "not_answer_sheet"
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
