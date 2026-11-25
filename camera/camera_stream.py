from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional, Tuple

import cv2
import numpy as np

from .camera_health import CameraHealthMonitor
from .camera_recovery import RecoveryPolicy
from .camera_registry import (
    CameraConnectionState,
    CameraFrame,
    CameraSource,
    CameraStatus,
    CameraType,
)

FrameSink = Callable[[str, np.ndarray, float], None]


class CameraStream:
    """Threaded camera capture stream with latest-frame buffering and auto recovery."""

    def __init__(
        self,
        source: CameraSource,
        width: int = 1280,
        height: int = 720,
        target_fps: int = 30,
        buffer_size: int = 1,
        recovery_policy: RecoveryPolicy | None = None,
        frame_sink: FrameSink | None = None,
        logger: logging.Logger | None = None,
    ):
        self.source = source
        self.width = width
        self.height = height
        self.target_fps = max(1, int(target_fps))
        self.frame_queue: queue.Queue[CameraFrame] = queue.Queue(maxsize=max(1, buffer_size))
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.frame_sink = frame_sink
        self.logger = logger or logging.getLogger(__name__)
        self.cap: Optional[cv2.VideoCapture] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.frame_number = 0
        self.retry_attempts = 0
        self.health = CameraHealthMonitor()
        self.status = CameraStatus(
            camera_id=source.camera_id,
            name=source.name,
            camera_type=source.camera_type,
            state=CameraConnectionState.STOPPED,
            source=source.safe_source,
            metadata=source.metadata,
        )

    @staticmethod
    def probe_source(source: CameraSource, width: int = 640, height: int = 480, timeout: float = 2.0) -> tuple[bool, str, Tuple[int, int]]:
        if source.camera_type == CameraType.SYNTHETIC:
            return True, "Synthetic camera available", (width, height)
        cap = cv2.VideoCapture(source.source)
        try:
            if not cap.isOpened():
                return False, "Unable to connect or camera not found", (0, 0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            deadline = time.time() + timeout
            while time.time() < deadline:
                ok, frame = cap.read()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    return True, "Camera opens and reads frames", (w, h)
                time.sleep(0.05)
            return False, "Unable to read frame", (0, 0)
        finally:
            cap.release()

    def start(self) -> bool:
        if self.running:
            return True
        self.status.state = CameraConnectionState.CONNECTING
        self.status.updated_at = time.time()
        if self.source.camera_type != CameraType.SYNTHETIC:
            try:
                self.cap = self._open_capture()
            except Exception as exc:
                self.logger.exception("Failed to open camera %s", self.source.camera_id)
                self.cap = None
                self.status.last_error = str(exc)
            if self.cap is None:
                self.status.state = CameraConnectionState.ERROR
                self.status.last_error = self.status.last_error or self._friendly_error()
                self.status.updated_at = time.time()
                return False
        self.running = True
        self.status.state = CameraConnectionState.ONLINE
        self.status.connected_at = time.time()
        self.status.last_error = ""
        self.thread = threading.Thread(target=self._capture_loop, name=f"CameraStream-{self.source.camera_id}", daemon=True)
        self.thread.start()
        self.logger.info("Camera started: %s (%s)", self.source.name, self.source.safe_source)
        return True

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.status.state = CameraConnectionState.STOPPED
        self.status.updated_at = time.time()
        self.logger.info("Camera stopped: %s", self.source.name)

    def restart(self) -> bool:
        self.stop()
        return self.start()

    def get_latest_frame(self) -> Optional[CameraFrame]:
        latest = None
        while not self.frame_queue.empty():
            latest = self.frame_queue.get_nowait()
        return latest

    def to_status(self) -> dict:
        self.status.retry_attempts = self.retry_attempts
        self.status.metrics = self.health.metrics
        self.status.updated_at = time.time()
        return self.status.to_dict()

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        cap = cv2.VideoCapture(self.source.source)
        if not cap.isOpened():
            cap.release()
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        return cap

    def _capture_loop(self) -> None:
        frame_interval = 1.0 / self.target_fps
        self.logger.info(f"🎥 Capture loop started for {self.source.camera_id} at {self.target_fps} FPS")
        frame_count = 0
        
        while self.running:
            start = time.time()
            try:
                if self.source.camera_type == CameraType.SYNTHETIC:
                    frame = self._generate_synthetic_frame()
                    ok = True
                    self.logger.debug(f"🔄 Generated synthetic frame for {self.source.camera_id}")
                else:
                    ok, frame = self._read_capture_frame()

                if not ok or frame is None:
                    self._handle_read_failure()
                    continue

                self.frame_number += 1
                frame_count += 1
                h, w = frame.shape[:2]
                self.health.record_frame((w, h), captured_at=start)
                self.status.state = CameraConnectionState.ONLINE
                self.status.last_error = ""
                self.retry_attempts = 0

                camera_frame = CameraFrame(frame, self.source.camera_id, time.time(), self.frame_number)
                self._queue_latest(camera_frame)

                # Keep high-frequency telemetry out of production INFO logs.
                if frame_count % max(1, self.target_fps * 30) == 0:
                    self.logger.debug(f"📹 {self.source.camera_id}: frame #{self.frame_number} (shape: {frame.shape})")

                if self.frame_sink:
                    try:
                        self.frame_sink(self.source.camera_id, frame, camera_frame.timestamp)
                        self.logger.debug(f"📨 Frame sink called for {self.source.camera_id}")
                    except Exception as exc:
                        self.logger.error(f"❌ Frame sink error for {self.source.camera_id}: {exc}")

                elapsed = time.time() - start
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
            except Exception as exc:
                self.logger.exception("Camera frame loop error for %s: %s", self.source.camera_id, exc)
                self._handle_read_failure()

    def _read_capture_frame(self) -> tuple[bool, Optional[np.ndarray]]:
        if self.cap is None:
            self.cap = self._open_capture()
            if self.cap is None:
                return False, None
        return self.cap.read()

    def _queue_latest(self, frame: CameraFrame) -> None:
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
                self.health.record_drop()
            except queue.Empty:
                pass
        self.frame_queue.put_nowait(frame)

    def _handle_read_failure(self) -> None:
        self.health.record_failure()
        self.retry_attempts += 1
        self.status.state = CameraConnectionState.RECONNECTING
        self.status.last_error = self._friendly_error()
        self.status.updated_at = time.time()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        delay = self.recovery_policy.delay_for_attempt(self.retry_attempts)
        self.logger.warning("Camera %s disconnected. Retrying in %.1fs", self.source.camera_id, delay)
        time.sleep(delay)

    def _friendly_error(self) -> str:
        source_text = str(self.source.source)
        if self.source.camera_type in {CameraType.RTSP, CameraType.IP_CAMERA} and "@" in source_text:
            return "Unable to connect. Check network, RTSP URL, username, and password."
        if self.source.camera_type in {CameraType.RTSP, CameraType.RTMP, CameraType.DROIDCAM, CameraType.IP_CAMERA}:
            return "Network timeout or invalid stream URL. Check IP address and port."
        if self.source.camera_type == CameraType.VIDEO_FILE:
            return "Video file not found or unsupported format."
        return "Camera not found or already used by another application."

    def _generate_synthetic_frame(self) -> np.ndarray:
        height, width = 640, 640
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        tick = self.frame_number
        for y in range(height):
            shade = int(24 + (y / height) * 36)
            frame[y, :] = (shade, shade, shade + 10)
        cv2.rectangle(frame, (28, 28), (width - 28, 112), (35, 70, 55), -1)
        cv2.rectangle(frame, (28, 28), (width - 28, 112), (90, 170, 135), 2)
        cv2.putText(frame, "AI Exam Surveillance - Camera Simulation", (52, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (220, 255, 230), 2)
        cv2.putText(frame, "Fallback active: no physical camera connected", (52, 96), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (190, 225, 255), 1)
        for row, desk_y in enumerate([230, 390, 540]):
            cv2.rectangle(frame, (60, desk_y), (width - 60, desk_y + 35), (75, 55, 40), -1)
            for col in range(4):
                base_x = 115 + col * 135
                wobble = int(8 * np.sin((tick / 12.0) + row + col))
                cv2.circle(frame, (base_x + wobble, desk_y - 42), 22, (80, 150, 210), -1)
                cv2.rectangle(frame, (base_x - 24 + wobble, desk_y - 20), (base_x + 24 + wobble, desk_y + 25), (70, 115, 185), -1)
                cv2.rectangle(frame, (base_x - 44 + wobble, desk_y - 75), (base_x + 44 + wobble, desk_y + 28), (0, 190, 80), 2)
                cv2.putText(frame, f"ID {row * 4 + col + 1}", (base_x - 31 + wobble, desk_y - 82), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 120), 1)
        cv2.putText(frame, "SIM LIVE", (width - 145, height - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        return frame
