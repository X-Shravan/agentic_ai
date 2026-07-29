from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np

from backend.camera_manager import CameraManager

# ---------------------------------------------------
# Frame Structure
# ---------------------------------------------------
@dataclass
class Frame:
    image: np.ndarray
    camera_id: str
    timestamp: float
    frame_number: int

# ---------------------------------------------------
# Multi Camera Surveillance Agent
# ---------------------------------------------------
class SurveillanceAgent:

    def __init__(self, config: Dict[str, Any]):

        self.config = config
        self.camera_manager = CameraManager(config.get("cameras", []))
        self.frame_count = 0

    def _frame_from_image(self, camera_id: str, image: np.ndarray) -> Frame:
        self.frame_count += 1
        return Frame(
            image=image,
            camera_id=camera_id,
            timestamp=time.time(),
            frame_number=self.frame_count,
        )

    # ---------------------------------
    def start(self) -> bool:

        return self.camera_manager.start_all()

    # ---------------------------------
    def stop(self):

        self.camera_manager.stop_all()

    # ---------------------------------
    def get_frames(self) -> Dict[str, Frame]:

        return {
            camera_id: self._frame_from_image(camera_id, image)
            for camera_id, image in self.camera_manager.read_all().items()
        }


# ---------------------------------------------------
# Demo Camera (Optimized for YOLO)
# ---------------------------------------------------
class DemoSurveillanceAgent(SurveillanceAgent):

    def __init__(self, config: Dict[str, Any]):

        self.config = config
        self.camera_manager = CameraManager(self._camera_configs())

        self.running = False
        self.frame_count = 0

        self.target_size = (640, 640)  # 🔥 YOLO optimized

    # ---------------------------------
    def _find_camera(self):

        print("[INFO] Searching for webcam...")

        preferred = (
            os.getenv("DROIDCAM_CAMERA_INDEX")
            or os.getenv("CAMO_CAMERA_INDEX")
            or os.getenv("CAMERA_INDEX")
        )
        indices = [int(preferred)] if preferred and preferred.isdigit() else []
        indices.extend(i for i in range(10) if i not in indices)

        for i in indices:
            probe = CameraManager([{"id": "probe", "type": "webcam", "device_index": i}])
            if probe.start_all():
                probe.stop_all()
                print(f"[INFO] Using camera index: {i}")
                return i

        return None

    # ---------------------------------
    def _camera_configs(self):
        configured = self.config.get("cameras") or []
        if configured:
            return configured

        source = (
            os.getenv("DROIDCAM_URL")
            or os.getenv("RTSP_URL")
            or os.getenv("MJPEG_URL")
            or os.getenv("VIDEO_FILE")
            or os.getenv("DROIDCAM_CAMERA_INDEX")
            or os.getenv("CAMO_CAMERA_INDEX")
            or os.getenv("CAMERA_INDEX")
            or self.config.get("demo", {}).get("video_source")
        )
        if source is None:
            source = self._find_camera()
        camera_type = "webcam"
        config = {"id": "demo_cam", "name": "Demo Camera", "type": camera_type, "enabled": True}
        if isinstance(source, str) and not source.isdigit():
            config["url"] = source
            config["type"] = "file" if os.path.exists(source) else ("rtsp" if source.startswith("rtsp") else "mjpeg")
        else:
            config["device_index"] = int(source or 0)
        return [config]

    def start(self) -> bool:

        print("[INFO] Starting demo cameras through CameraManager")
        self.running = self.camera_manager.start_all()
        if not self.running:
            print("[ERROR] Could not open configured camera source")
        return self.running

    # ---------------------------------
    def stop(self):

        self.running = False
        self.camera_manager.stop_all()

        print("[INFO] Demo camera stopped")

    # ---------------------------------
    def get_frames(self) -> Dict[str, Frame]:

        if not self.running:
            return {}

        raw_frames = self.camera_manager.read_all()
        frames = {}
        for camera_id, frame in raw_frames.items():
            self.frame_count += 1
            frame = cv2.resize(frame, self.target_size)
            frames[camera_id] = Frame(frame, camera_id, time.time(), self.frame_count)
        return frames