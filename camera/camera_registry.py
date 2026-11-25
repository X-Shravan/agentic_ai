from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import numpy as np


class CameraType(str, Enum):
    LAPTOP_WEBCAM = "laptop_webcam"
    USB_WEBCAM = "usb_webcam"
    DROIDCAM = "droidcam"
    IP_CAMERA = "ip_camera"
    RTSP = "rtsp"
    RTMP = "rtmp"
    VIDEO_FILE = "video_file"
    SYNTHETIC = "synthetic"


class CameraConnectionState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    ERROR = "error"


def mask_camera_url(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    text = str(value or "")
    return re.sub(r"(://[^:/@]+:)([^@]+)(@)", r"\1****\3", text)


@dataclass
class CameraSource:
    camera_id: str
    name: str
    camera_type: CameraType
    source: Any
    priority: int = 100
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def safe_source(self) -> str:
        return mask_camera_url(self.source)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "type": self.camera_type.value,
            "source": self.safe_source,
            "priority": self.priority,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class CameraFrame:
    image: np.ndarray
    camera_id: str
    timestamp: float
    frame_number: int


@dataclass
class CameraMetrics:
    fps: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    latency_ms: float = 0.0
    frame_delay_ms: float = 0.0
    packet_loss_pct: float = 0.0
    frames_read: int = 0
    read_failures: int = 0
    dropped_frames: int = 0
    last_frame_timestamp: Optional[float] = None


@dataclass
class CameraStatus:
    camera_id: str
    name: str
    camera_type: CameraType
    state: CameraConnectionState
    source: str
    metrics: CameraMetrics = field(default_factory=CameraMetrics)
    last_error: str = ""
    retry_attempts: int = 0
    connected_at: Optional[float] = None
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        last_age = None
        if self.metrics.last_frame_timestamp:
            last_age = max(0.0, (time.time() - self.metrics.last_frame_timestamp) * 1000)
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "type": self.camera_type.value,
            "source": self.source,
            "status": self.state.value,
            "online": self.state == CameraConnectionState.ONLINE,
            "fps": round(self.metrics.fps, 2),
            "resolution": list(self.metrics.resolution),
            "latency_ms": round(self.metrics.latency_ms, 2),
            "frame_delay_ms": round(self.metrics.frame_delay_ms, 2),
            "packet_loss_pct": round(self.metrics.packet_loss_pct, 2),
            "frames_read": self.metrics.frames_read,
            "read_failures": self.metrics.read_failures,
            "dropped_frames": self.metrics.dropped_frames,
            "last_frame_age_ms": round(last_age, 2) if last_age is not None else None,
            "last_error": self.last_error,
            "retry_attempts": self.retry_attempts,
            "connected_at": self.connected_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
