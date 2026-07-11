from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np


# ---------------------------------------------------
# Camera Configuration
# ---------------------------------------------------
@dataclass
class CameraConfig:
    id: str
    rtsp_url: str
    name: str
    enabled: bool = True


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
# Camera Stream (Multi-camera support)
# ---------------------------------------------------
class CameraStream:

    def __init__(self, config: CameraConfig, buffer_size: int = 5):

        self.config = config
        self.frame_buffer: queue.Queue[Frame] = queue.Queue(maxsize=buffer_size)

        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.frame_count = 0

    # ---------------------------------
    def start(self) -> bool:

        print(f"[INFO] Starting camera: {self.config.name}")

        self.cap = cv2.VideoCapture(self.config.rtsp_url)

        if not self.cap.isOpened():
            print(f"[ERROR] Cannot open camera {self.config.name}")
            return False

        # Reduce latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.running = True

        self.thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )

        self.thread.start()

        return True

    # ---------------------------------
    def _capture_loop(self):

        while self.running and self.cap is not None:

            ok, frame = self.cap.read()

            if not ok:
                print("[WARN] Camera disconnected. Reconnecting...")
                time.sleep(1)

                self.cap.release()
                self.cap = cv2.VideoCapture(self.config.rtsp_url)
                continue

            self.frame_count += 1

            frame_data = Frame(
                image=frame,
                camera_id=self.config.id,
                timestamp=time.time(),
                frame_number=self.frame_count
            )

            # Drop old frames if buffer full
            if self.frame_buffer.full():
                try:
                    self.frame_buffer.get_nowait()
                except queue.Empty:
                    pass

            self.frame_buffer.put_nowait(frame_data)

    # ---------------------------------
    def get_latest_frame(self) -> Optional[Frame]:

        latest = None

        while not self.frame_buffer.empty():
            latest = self.frame_buffer.get_nowait()

        return latest

    # ---------------------------------
    def stop(self):

        self.running = False

        if self.thread:
            self.thread.join(timeout=1)

        if self.cap:
            self.cap.release()

        print(f"[INFO] Camera stopped: {self.config.name}")


# ---------------------------------------------------
# Multi Camera Surveillance Agent
# ---------------------------------------------------
class SurveillanceAgent:

    def __init__(self, config: Dict[str, Any]):

        self.config = config
        self.cameras: Dict[str, CameraStream] = {}

        self._init_cameras()

    def _init_cameras(self):

        for cam in self.config.get("cameras", []):

            if cam.get("enabled", True):

                cfg = CameraConfig(
                    id=cam["id"],
                    rtsp_url=cam["rtsp_url"],
                    name=cam.get("name", cam["id"])
                )

                self.cameras[cfg.id] = CameraStream(cfg)

    # ---------------------------------
    def start(self) -> bool:

        results = []

        for cam in self.cameras.values():
            results.append(cam.start())

        return all(results)

    # ---------------------------------
    def stop(self):

        for cam in self.cameras.values():
            cam.stop()

    # ---------------------------------
    def get_frames(self) -> Dict[str, Frame]:

        frames: Dict[str, Frame] = {}

        for cam_id, stream in self.cameras.items():

            frame = stream.get_latest_frame()

            if frame is not None:
                frames[cam_id] = frame

        return frames


# ---------------------------------------------------
# Demo Camera (Optimized for YOLO)
# ---------------------------------------------------
class DemoSurveillanceAgent(SurveillanceAgent):

    def __init__(self, config: Dict[str, Any]):

        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None

        self.running = False
        self.frame_count = 0

        self.target_size = (640, 640)  # 🔥 YOLO optimized

    # ---------------------------------
    def _find_camera(self):

        print("[INFO] Searching for webcam...")

        for i in range(5):

            cap = cv2.VideoCapture(i)

            if cap.isOpened():
                print(f"[INFO] Using camera index: {i}")
                cap.release()
                return i

        return None

    # ---------------------------------
    def start(self) -> bool:

        source = self.config.get("demo", {}).get("video_source")

        if source is None:
            source = self._find_camera()

        if source is None:
            print("[ERROR] No camera found")
            return False

        print("[INFO] Starting demo camera...")

        self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():
            print("[ERROR] Could not open camera")
            return False

        # 🔥 Higher resolution for better detection
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Reduce latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.running = True

        return True

    # ---------------------------------
    def stop(self):

        self.running = False

        if self.cap:
            self.cap.release()

        print("[INFO] Demo camera stopped")

    # ---------------------------------
    def get_frames(self) -> Dict[str, Frame]:

        if not self.running or self.cap is None:
            return {}

        ok, frame = self.cap.read()

        if not ok:
            return {}

        self.frame_count += 1

        # 🔥 Resize for YOLO
        frame = cv2.resize(frame, self.target_size)

        return {
            "demo_cam": Frame(
                frame,
                "demo_cam",
                time.time(),
                self.frame_count
            )
        }