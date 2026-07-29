"""Camera input abstraction for webcam, USB, DroidCam, RTSP, MJPEG, and files.

This module deliberately owns only frame acquisition. Detection, tracking,
behavior analysis, and AI agents consume frames exactly as before.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional
import time

try:
    import cv2
except Exception:  # pragma: no cover - OpenCV is optional for non-camera API tests
    cv2 = None


@dataclass
class CameraSourceConfig:
    id: str
    name: str = "Camera"
    type: str = "webcam"
    device_index: Optional[int] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    resolution: tuple[int, int] = (1280, 720)
    fps: int = 30
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraSourceConfig":
        source_type = str(data.get("type") or data.get("source_type") or "").lower()
        legacy_url = data.get("rtsp_url") or data.get("url")
        if not source_type:
            source_type = "rtsp" if legacy_url else "webcam"
        resolution = data.get("resolution") or (1280, 720)
        if isinstance(resolution, list):
            resolution = tuple(resolution[:2])
        return cls(
            id=str(data.get("id") or data.get("camera_id") or data.get("name") or "camera"),
            name=str(data.get("name") or data.get("camera_id") or data.get("id") or "Camera"),
            type=source_type,
            device_index=data.get("device_index"),
            url=legacy_url,
            username=data.get("username"),
            password=data.get("password"),
            resolution=(int(resolution[0]), int(resolution[1])),
            fps=int(data.get("fps") or 30),
            enabled=bool(data.get("enabled", True)),
        )

    def public_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if payload.get("password"):
            payload["password"] = "********"
        payload["resolution"] = list(self.resolution)
        return payload


class CameraSource:
    def __init__(self, config: CameraSourceConfig):
        self.config = config
        self.capture = None
        self.status = "disconnected"
        self.error: Optional[str] = None
        self.last_frame_time: Optional[float] = None
        self.last_reconnect = 0.0
        self.lock = Lock()

    def _target(self):
        if self.config.type in {"webcam", "usb", "droidcam"} and self.config.device_index is not None:
            return int(self.config.device_index)
        if self.config.url:
            return self._credentialed_url(self.config.url)
        return int(self.config.device_index or 0)

    def _credentialed_url(self, url: str) -> str:
        if not self.config.username or not self.config.password or "://" not in url or "@" in url:
            return url
        scheme, rest = url.split("://", 1)
        return f"{scheme}://{self.config.username}:{self.config.password}@{rest}"

    def connect(self) -> bool:
        if not self.config.enabled:
            self.status = "disabled"
            return False
        if cv2 is None:
            self.status = "error"
            self.error = "OpenCV is not installed"
            return False
        self.status = "connecting"
        self.error = None
        self.capture = cv2.VideoCapture(self._target())
        if not self.capture.isOpened():
            self.status = "error"
            self.error = f"Unable to open {self.config.type} source"
            return False
        width, height = self.config.resolution
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.status = "connected"
        return True

    def start(self) -> bool:
        return self.connect()

    def read(self):
        with self.lock:
            if self.capture is None or not self.capture.isOpened():
                self.reconnect()
            if self.capture is None:
                return False, None
            ok, frame = self.capture.read()
            if ok:
                self.status = "connected"
                self.last_frame_time = time.time()
                return True, frame
            self.status = "disconnected"
            self.reconnect()
            return False, None

    def reconnect(self) -> bool:
        now = time.time()
        if now - self.last_reconnect < 1.0:
            return False
        self.last_reconnect = now
        self.stop()
        return self.connect()

    def stop(self):
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        if self.status != "disabled":
            self.status = "disconnected"

    def health(self) -> Dict[str, Any]:
        return {**self.config.public_dict(), "status": self.status, "error": self.error, "last_frame_time": self.last_frame_time}


class CameraManager:
    def __init__(self, configs: Optional[list[Dict[str, Any]]] = None):
        self.sources: Dict[str, CameraSource] = {}
        for config in configs or []:
            self.add_camera(config, validate=False)

    def add_camera(self, config: Dict[str, Any], validate: bool = True) -> Dict[str, Any]:
        cfg = CameraSourceConfig.from_dict(config)
        if cfg.type in {"rtsp", "http", "mjpeg", "file", "droidcam"} and not cfg.url and cfg.device_index is None:
            raise ValueError(f"{cfg.type} cameras require a url or device_index")
        if cfg.type == "file" and cfg.url and not Path(cfg.url).exists():
            raise ValueError(f"Video file does not exist: {cfg.url}")
        source = CameraSource(cfg)
        if validate and cfg.enabled:
            source.connect()
            if source.status == "error":
                raise ValueError(source.error or "Camera validation failed")
        self.sources[cfg.id] = source
        return source.health()

    def update_camera(self, camera_id: str, config: Dict[str, Any], validate: bool = True) -> Dict[str, Any]:
        self.remove_camera(camera_id)
        config = {**config, "id": config.get("id") or config.get("camera_id") or camera_id}
        return self.add_camera(config, validate=validate)

    def remove_camera(self, camera_id: str) -> bool:
        source = self.sources.pop(camera_id, None)
        if source:
            source.stop()
            return True
        return False

    def start_all(self) -> bool:
        results = [source.start() for source in self.sources.values() if source.config.enabled]
        return all(results) if results else False

    def stop_all(self):
        for source in self.sources.values():
            source.stop()

    def read_all(self) -> Dict[str, Any]:
        frames = {}
        for camera_id, source in self.sources.items():
            if not source.config.enabled:
                continue
            ok, frame = source.read()
            if ok:
                frames[camera_id] = frame
        return frames

    def health(self) -> Dict[str, Dict[str, Any]]:
        return {camera_id: source.health() for camera_id, source in self.sources.items()}

    def get(self, camera_id: str) -> Optional[CameraSource]:
        return self.sources.get(camera_id)
