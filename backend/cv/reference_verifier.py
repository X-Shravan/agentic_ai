import os
import cv2
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ReferenceVerifier:
    def __init__(self, config=None):
        self.config = config or {}
        # Get threshold values
        ref_conf = self.config.get("reference_verify", {})
        self.enabled = ref_conf.get("enabled", True)
        self.sw_threshold = ref_conf.get("smartwatch_threshold", 0.20)
        self.aw_threshold = ref_conf.get("analog_watch_threshold", 0.55)
        self.ans_threshold = ref_conf.get("answer_sheet_threshold", 0.35)
        self.cache_duration = ref_conf.get("cache_duration", 10.0)
        
        # Load reference data (stores pre-computed grayscale and HSV reference templates)
        self.reference_images = {
            "smartwatch": [],
            "analog_watch": [],
            "answer_sheet": []
        }
        
        if self.enabled:
            self._load_reference_data()

    def _load_reference_data(self):
        # Resolve project root dynamically
        root_dir = Path(__file__).resolve().parent.parent.parent
        ref_dir = root_dir / "reference_data"
        
        if not ref_dir.exists():
            logger.warning(f"[REFERENCE VERIFY] reference_data directory not found at {ref_dir}. Verifier will run as pass-through.")
            return

        for category in ["smartwatch", "analog_watch", "answer_sheet"]:
            cat_dir = ref_dir / category
            if not cat_dir.exists():
                logger.warning(f"[REFERENCE VERIFY] Category directory not found: {cat_dir}")
                continue
                
            for fname in os.listdir(cat_dir):
                if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.jfif')):
                    fpath = cat_dir / fname
                    img = cv2.imread(str(fpath))
                    if img is not None:
                        # Resize reference images to a standard size to optimize comparisons
                        img_resized = cv2.resize(img, (128, 128))
                        img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                        img_hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
                        self.reference_images[category].append((img_gray, img_hsv))
                        
            logger.info(f"[REFERENCE VERIFY] Loaded {len(self.reference_images[category])} reference images for {category}")

    def compute_ssim(self, gray1, gray2):
        c1 = 6.5025
        c2 = 58.5225
        img1_f = gray1.astype(np.float32)
        img2_f = gray2.astype(np.float32)
        
        mu1 = cv2.GaussianBlur(img1_f, (11, 11), 1.5)
        mu2 = cv2.GaussianBlur(img2_f, (11, 11), 1.5)
        
        mu1_sq = mu1 * mu1
        mu2_sq = mu2 * mu2
        mu1_mu2 = mu1 * mu2
        
        sigma1_sq = cv2.GaussianBlur(img1_f * img1_f, (11, 11), 1.5) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2_f * img2_f, (11, 11), 1.5) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1_f * img2_f, (11, 11), 1.5) - mu1_mu2
        
        ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / ((mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2))
        return float(ssim_map.mean())

    def compute_hist_similarity(self, hsv1, hsv2):
        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
        return max(0.0, float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)))

    def evaluate_similarity(self, crop, category):
        ref_images = self.reference_images.get(category, [])
        if not ref_images or crop is None or crop.size == 0:
            return 0.0
            
        crop_resized = cv2.resize(crop, (128, 128))
        crop_gray = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2GRAY)
        crop_hsv = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2HSV)
        
        scores = []
        for ref_gray, ref_hsv in ref_images:
            ssim = self.compute_ssim(crop_gray, ref_gray)
            hist = self.compute_hist_similarity(crop_hsv, ref_hsv)
            
            # Combined score: weights are 0.4 for structure and 0.6 for color distribution
            combined = 0.4 * ssim + 0.6 * hist
            scores.append(combined)
            
        # Use np.max to find similarity against the closest matching template, rather than dilution via np.mean
        return float(np.max(scores)) if scores else 0.0

    def verify(self, crop, obj_class):
        """
        Verify cropped image against reference database.
        Returns: (verified_class_name, confidence_score)
        """
        if not self.enabled:
            return "unknown", 0.0
            
        if crop is None or crop.size == 0:
            return "unknown", 0.0

        try:
            # Normalize class names to standard keys
            normalized_class = obj_class.lower().replace(" ", "_").replace("-", "_")
            
            if normalized_class in {"smart_watch", "smartwatch", "analog_watch"}:
                # Compare watch crop with both smartwatch and analog watch reference datasets
                sw_sim = self.evaluate_similarity(crop, "smartwatch")
                aw_sim = self.evaluate_similarity(crop, "analog_watch")
                
                # Decision logic matching exact smartwatch vs analog watch rules:
                if sw_sim >= self.sw_threshold and sw_sim > aw_sim:
                    return "smartwatch", sw_sim
                elif aw_sim >= self.aw_threshold and aw_sim > sw_sim:
                    return "analog_watch", aw_sim
                else:
                    # Uncertain result -> fallback
                    return "unknown", max(sw_sim, aw_sim)
                    
            elif normalized_class in {"book", "book_paper", "answer_book", "notebook", "paper_sheet"}:
                # Compare book/paper crop with answer sheet references
                ans_sim = self.evaluate_similarity(crop, "answer_sheet")
                
                if ans_sim >= self.ans_threshold:
                    return "answer_sheet", ans_sim
                else:
                    return "book", ans_sim
                    
        except Exception as exc:
            logger.warning(f"[REFERENCE VERIFY] Exception during verification: {exc}")
            
        return "unknown", 0.0
