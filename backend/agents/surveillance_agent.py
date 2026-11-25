from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np

from camera import CameraManager
from camera.camera_config import load_camera_config


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


def _camera_type_for_source(source):
    text = str(source).lower()
    if text.startswith("rtsp://"):
        return "rtsp"
    if text.startswith("rtmp://"):
        return "rtmp"
    if text.startswith("http://") or text.startswith("https://"):
        return "droidcam"
    if text.endswith((".mp4", ".avi", ".mov", ".mkv")):
        return "video_file"
    return "webcam"


def _manager_config_with_sources(config: Dict[str, Any], configured_sources: list[dict] | None = None):
    manager_config = load_camera_config("camera/camera_config.yaml")
    if configured_sources:
        manager_config.explicit_sources = configured_sources
    manager_config.enable_synthetic_fallback = True
    manager_config.probe_indices = config.get("camera_manager", {}).get("probe_indices", manager_config.probe_indices)
    return manager_config


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
        configured_sources = []
        for priority, cam in enumerate(self.config.get("cameras", []), start=1):
            if cam.get("enabled", True):
                source = cam.get("rtsp_url") or cam.get("source")
                if source:
                    configured_sources.append({
                        "camera_id": cam.get("id", f"cam_{priority}"),
                        "name": cam.get("name", f"Camera {priority}"),
                        "type": _camera_type_for_source(source),
                        "source": source,
                        "priority": priority,
                        "enabled": True,
                    })
        self.manager = CameraManager(config=_manager_config_with_sources(config, configured_sources))

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
        results = self.manager.connect_all()
        if any(results.values()):
            return True

        # If configured CCTV/RTSP cameras fail, fall back to discovered webcam/video/synthetic.
        self.manager.config.explicit_sources = []
        self.manager.refresh_sources()
        return self.manager.connect_best_available() is not None

    # ---------------------------------
    def stop(self):
        self.manager.stop_all()

    # ---------------------------------
    def get_frames(self) -> Dict[str, Frame]:
        return self.manager.get_frames()


# ---------------------------------------------------
# Demo Camera (Optimized for YOLO)
# ---------------------------------------------------
class DemoSurveillanceAgent(SurveillanceAgent):

    def __init__(self, config: Dict[str, Any]):

        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None

        self.running = False
        self.frame_count = 0
        self.synthetic_mode = False
        self.source_label = "Not started"
        self.last_error = ""

        self.target_size = (640, 640)  # 🔥 YOLO optimized
        source = (
            os.getenv("DROIDCAM_CAMERA_INDEX")
            or os.getenv("CAMO_CAMERA_INDEX")
            or os.getenv("CAMERA_INDEX")
            or self.config.get("demo", {}).get("video_source")
        )
        configured_sources = []
        if source not in (None, ""):
            configured_sources.append({
                "camera_id": "demo_cam",
                "name": "Demo Camera",
                "type": _camera_type_for_source(source),
                "source": source,
                "priority": 1,
                "enabled": True,
            })
        self.manager = CameraManager(config=_manager_config_with_sources(config, configured_sources))

    # ---------------------------------
    @staticmethod
    def _coerce_source(source):
        """Convert numeric camera index strings to ints while preserving file/URL sources."""

        if isinstance(source, str) and source.isdigit():
            return int(source)
        return source

    # ---------------------------------
    def _candidate_sources(self):
        """Return camera/video sources in preference order without duplicates."""

        configured_source = self.config.get("demo", {}).get("video_source")
        preferred_sources = [
            os.getenv("DROIDCAM_CAMERA_INDEX"),
            os.getenv("CAMO_CAMERA_INDEX"),
            os.getenv("CAMERA_INDEX"),
            configured_source,
        ]

        candidates = []
        seen = set()

        def add_candidate(value):
            if value in (None, ""):
                return
            value = self._coerce_source(value)
            key = repr(value)
            if key not in seen:
                seen.add(key)
                candidates.append(value)

        for source in preferred_sources:
            add_candidate(source)

        # If the configured/default camera fails, still try common webcam indices.
        for index in range(10):
            add_candidate(index)

        return candidates

    # ---------------------------------
    def _find_camera(self):

        print("[INFO] Searching for webcam...")

        for i in self._candidate_sources():

            cap = cv2.VideoCapture(i)

            if cap.isOpened():
                print(f"[INFO] Using camera/video source: {i}")
                cap.release()
                return i

            cap.release()

        return None

    # ---------------------------------
    def start(self) -> bool:
        self.synthetic_mode = False
        self.source_label = "Starting"
        self.last_error = ""

        best = self.manager.connect_best_available()
        if best is None:
            self.manager.config.explicit_sources = []
            self.manager.refresh_sources()
            best = self.manager.connect_best_available()

        self.running = best is not None
        self._sync_manager_status()
        return self.running

    # ---------------------------------
    def _sync_manager_status(self):
        statuses = self.manager.get_all_status()
        primary = next((status for status in statuses.values() if status.get("online")), None)
        primary = primary or next(iter(statuses.values()), None)
        if not primary:
            self.synthetic_mode = True
            self.source_label = "No camera source"
            self.last_error = "No camera source could be discovered"
            return
        self.synthetic_mode = primary.get("type") == "synthetic"
        self.source_label = primary.get("name") or primary.get("source") or "Camera source"
        self.last_error = primary.get("last_error") or (
            "No physical webcam/video source opened; using synthetic simulation feed"
            if self.synthetic_mode else ""
        )

    # ---------------------------------
    def _generate_synthetic_frame(self):
        """Generate a live-looking classroom simulation frame when no camera exists."""

        height, width = self.target_size
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Background gradient
        for y in range(height):
            shade = int(25 + (y / max(1, height)) * 35)
            frame[y, :] = (shade, shade, shade + 8)

        tick = self.frame_count

        # Classroom board/header
        cv2.rectangle(frame, (30, 30), (width - 30, 115), (35, 70, 55), -1)
        cv2.rectangle(frame, (30, 30), (width - 30, 115), (90, 170, 135), 2)
        cv2.putText(
            frame,
            "AI Exam Surveillance - Simulation Camera",
            (55, 68),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (220, 255, 230),
            2,
        )
        cv2.putText(
            frame,
            "No webcam detected: synthetic feed is running",
            (55, 98),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (180, 220, 255),
            1,
        )

        # Desks and moving student silhouettes
        desk_y_positions = [230, 390, 540]
        for row, desk_y in enumerate(desk_y_positions):
            cv2.rectangle(frame, (60, desk_y), (width - 60, desk_y + 35), (75, 55, 40), -1)
            cv2.line(frame, (60, desk_y), (width - 60, desk_y), (120, 90, 70), 2)

            for col in range(4):
                base_x = 115 + col * 135
                wobble = int(8 * np.sin((tick / 12.0) + row + col))
                head_center = (base_x + wobble, desk_y - 42)
                body_top = (base_x - 24 + wobble, desk_y - 20)
                body_bottom = (base_x + 24 + wobble, desk_y + 25)

                cv2.circle(frame, head_center, 22, (80, 150, 210), -1)
                cv2.rectangle(frame, body_top, body_bottom, (70, 115, 185), -1)
                cv2.rectangle(
                    frame,
                    (base_x - 44 + wobble, desk_y - 75),
                    (base_x + 44 + wobble, desk_y + 28),
                    (0, 190, 80),
                    2,
                )
                cv2.putText(
                    frame,
                    f"ID {row * 4 + col + 1}",
                    (base_x - 31 + wobble, desk_y - 82),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 230, 120),
                    1,
                )

        # Add one moving suspicious object to prove the feed is alive.
        phone_x = 95 + int((tick * 4) % (width - 190))
        cv2.rectangle(frame, (phone_x, 160), (phone_x + 24, 205), (40, 40, 230), -1)
        cv2.rectangle(frame, (phone_x, 160), (phone_x + 24, 205), (255, 255, 255), 1)
        cv2.putText(
            frame,
            "SIM LIVE",
            (width - 145, height - 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )

        return frame

    # ---------------------------------
    def stop(self):
        self.running = False
        self.manager.stop_all()
        print("[INFO] Demo camera stopped")

    # ---------------------------------
    def get_frames(self) -> Dict[str, Frame]:
        if not self.running:
            return {}
        frames = self.manager.get_frames()
        self._sync_manager_status()
        return frames