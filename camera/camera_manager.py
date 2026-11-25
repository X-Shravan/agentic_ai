from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .camera_config import CameraManagerConfig, load_camera_config
from .camera_factory import build_candidate_sources
from .camera_recovery import RecoveryPolicy
from .camera_registry import CameraConnectionState, CameraFrame, CameraSource, CameraStatus, CameraType
from .camera_stream import CameraStream

logger = logging.getLogger(__name__)
_GLOBAL_CAMERA_MANAGER: "CameraManager | None" = None


class CameraManager:
    """Coordinates discovery, stream lifecycle, health, and recovery for many cameras."""

    def __init__(
        self,
        config: CameraManagerConfig | None = None,
        frame_sink=None,
        logger_: logging.Logger | None = None,
    ):
        self.config = config or load_camera_config()
        self.logger = logger_ or logger
        self.frame_sink = frame_sink
        self.recovery_policy = RecoveryPolicy()
        self.streams: Dict[str, CameraStream] = {}
        self.camera_sources: Dict[str, CameraSource] = {}
        self._lock = threading.RLock()
        self.refresh_sources()

    def set_frame_sink(self, frame_sink) -> None:
        """Update the one runtime frame sink for existing and future streams."""
        with self._lock:
            self.frame_sink = frame_sink
            streams = list(self.streams.values())
        for stream in streams:
            stream.frame_sink = frame_sink

    def refresh_sources(self) -> List[CameraSource]:
        """Refresh discovered/configured sources while retaining API-managed cameras."""
        sources = build_candidate_sources(self.config)
        with self._lock:
            api_sources = {
                camera_id: source
                for camera_id, source in self.camera_sources.items()
                if source.metadata.get("api_managed")
            }
            self.camera_sources = {source.camera_id: source for source in sources}
            self.camera_sources.update(api_sources)
            return list(self.camera_sources.values())

    def detected_cameras(self) -> List[dict]:
        with self._lock:
            sources = list(self.camera_sources.values())
        return [source.to_dict() for source in sources]

    def connect_all(self) -> Dict[str, bool]:
        with self._lock:
            camera_ids = list(self.camera_sources)
        results: Dict[str, bool] = {}
        for camera_id in camera_ids:
            try:
                results[camera_id] = self.connect(camera_id)
            except Exception:
                self.logger.exception("Camera %s failed during connect_all", camera_id)
                results[camera_id] = False
        return results

    @staticmethod
    def _camera_type(source: Any, declared_type: str | None = None) -> CameraType:
        aliases = {
            "webcam": CameraType.LAPTOP_WEBCAM,
            "laptop_webcam": CameraType.LAPTOP_WEBCAM,
            "usb": CameraType.USB_WEBCAM,
            "usb_webcam": CameraType.USB_WEBCAM,
            "droidcam": CameraType.DROIDCAM,
            "ip": CameraType.IP_CAMERA,
            "ip_camera": CameraType.IP_CAMERA,
            "rtsp": CameraType.RTSP,
            "rtmp": CameraType.RTMP,
            "file": CameraType.VIDEO_FILE,
            "video_file": CameraType.VIDEO_FILE,
            "synthetic": CameraType.SYNTHETIC,
        }
        normalized_type = str(declared_type or "").strip().lower()
        if normalized_type in aliases:
            return aliases[normalized_type]
        if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
            return CameraType.LAPTOP_WEBCAM
        value = str(source or "").lower()
        if value.startswith("rtsp://"):
            return CameraType.RTSP
        if value.startswith("rtmp://"):
            return CameraType.RTMP
        if value.startswith(("http://", "https://")):
            return CameraType.IP_CAMERA
        if value.startswith("synthetic://"):
            return CameraType.SYNTHETIC
        return CameraType.VIDEO_FILE

    def register_source(
        self,
        camera_id: str,
        source: Any = None,
        *,
        name: str | None = None,
        camera_type: str | None = None,
        enabled: bool = True,
        priority: int = 100,
        metadata: Dict[str, Any] | None = None,
    ) -> CameraSource:
        """Add or update an API-managed camera in this shared runtime manager."""
        normalized_source = source
        if isinstance(normalized_source, str) and normalized_source.isdigit():
            normalized_source = int(normalized_source)
        if normalized_source in (None, ""):
            normalized_source = f"synthetic://{camera_id}"

        source_metadata = dict(metadata or {})
        source_metadata["api_managed"] = True
        new_source = CameraSource(
            camera_id=camera_id,
            name=name or f"Camera {camera_id}",
            camera_type=self._camera_type(normalized_source, camera_type),
            source=normalized_source,
            priority=int(priority),
            enabled=bool(enabled),
            metadata=source_metadata,
        )

        with self._lock:
            existing_stream = self.streams.get(camera_id)
            was_running = bool(existing_stream and existing_stream.running)
        if existing_stream is not None and existing_stream.source != new_source:
            existing_stream.stop()
            with self._lock:
                self.streams.pop(camera_id, None)

        with self._lock:
            self.camera_sources[camera_id] = new_source
        if was_running and new_source.enabled:
            self.connect(camera_id)
        return new_source

    def unregister_source(self, camera_id: str) -> bool:
        """Disconnect and remove a camera from the shared runtime registry."""
        with self._lock:
            stream = self.streams.get(camera_id)
        if stream is not None:
            stream.stop()
        with self._lock:
            removed_stream = self.streams.pop(camera_id, None)
            removed_source = self.camera_sources.pop(camera_id, None)
        return removed_stream is not None or removed_source is not None

    def connect(self, camera_id: str) -> bool:
        with self._lock:
            source = self.camera_sources.get(camera_id)
            stream = self.streams.get(camera_id)
        if source is None or not source.enabled:
            return False
        if stream is None:
            stream = CameraStream(
                source=source,
                width=self.config.width,
                height=self.config.height,
                target_fps=self.config.target_fps,
                buffer_size=self.config.buffer_size,
                recovery_policy=self.recovery_policy,
                frame_sink=self.frame_sink,
                logger=self.logger,
            )
            with self._lock:
                self.streams[camera_id] = stream
        try:
            return stream.start()
        except Exception:
            self.logger.exception("Camera %s failed to start", camera_id)
            return False

    def disconnect(self, camera_id: str) -> bool:
        with self._lock:
            stream = self.streams.get(camera_id)
        if stream is None:
            return False
        stream.stop()
        return True

    def restart(self, camera_id: str) -> bool:
        with self._lock:
            stream = self.streams.get(camera_id)
        if stream is None:
            return self.connect(camera_id)
        return stream.restart()

    def connect_best_available(self) -> Optional[str]:
        with self._lock:
            ordered_sources = sorted(self.camera_sources.values(), key=lambda item: item.priority)
        for source in ordered_sources:
            if not source.enabled:
                continue
            try:
                if self.connect(source.camera_id):
                    return source.camera_id
            except Exception:
                self.logger.exception("Camera %s failed during discovery connect", source.camera_id)
        return None

    def get_latest_frame(self, camera_id: str) -> Optional[CameraFrame]:
        with self._lock:
            stream = self.streams.get(camera_id)
        return stream.get_latest_frame() if stream is not None else None

    def get_frames(self) -> Dict[str, CameraFrame]:
        with self._lock:
            streams = list(self.streams.items())
        frames: Dict[str, CameraFrame] = {}
        for camera_id, stream in streams:
            frame = stream.get_latest_frame()
            if frame is not None:
                frames[camera_id] = frame
        return frames

    def get_status(self, camera_id: str) -> dict:
        with self._lock:
            stream = self.streams.get(camera_id)
            source = self.camera_sources.get(camera_id)
        if stream is not None:
            return stream.to_status()
        if source is None:
            return {"camera_id": camera_id, "status": "not_found", "online": False}
        return CameraStatus(
            camera_id=source.camera_id,
            name=source.name,
            camera_type=source.camera_type,
            state=CameraConnectionState.OFFLINE,
            source=source.safe_source,
            metadata=source.metadata,
        ).to_dict()

    def get_all_status(self) -> Dict[str, dict]:
        with self._lock:
            camera_ids = list(self.camera_sources)
        return {camera_id: self.get_status(camera_id) for camera_id in camera_ids}

    def summary(self) -> dict:
        statuses = self.get_all_status()
        online = [status for status in statuses.values() if status.get("online")]
        with self._lock:
            stream_count = len(self.streams)
            camera_ids = list(self.camera_sources)
        return {
            "total_detected": len(camera_ids),
            "total_connected": stream_count,
            "online": len(online),
            "detected_cameras": camera_ids,
            "status": statuses,
        }

    def stop_all(self) -> None:
        with self._lock:
            streams = list(self.streams.values())
        for stream in streams:
            try:
                stream.stop()
            except Exception:
                self.logger.exception("Failed to stop camera %s", stream.source.camera_id)
        with self._lock:
            self.streams.clear()

    def auto_discover_and_connect(self) -> dict:
        self.refresh_sources()
        best = self.connect_best_available()
        if best is None and self.config.explicit_sources:
            self.logger.warning("Configured cameras failed; falling back to auto discovery")
            self.config.explicit_sources = []
            self.refresh_sources()
            best = self.connect_best_available()
        return {
            "connected": best is not None,
            "primary_camera_id": best,
            "summary": self.summary(),
        }


def init_global_camera_manager(config: CameraManagerConfig | None = None, frame_sink=None) -> CameraManager:
    """Initialize or configure the single process-wide CameraManager instance."""
    global _GLOBAL_CAMERA_MANAGER
    if _GLOBAL_CAMERA_MANAGER is None:
        _GLOBAL_CAMERA_MANAGER = CameraManager(config=config, frame_sink=frame_sink)
    else:
        if config is not None:
            _GLOBAL_CAMERA_MANAGER.config = config
            _GLOBAL_CAMERA_MANAGER.refresh_sources()
        if frame_sink is not None:
            _GLOBAL_CAMERA_MANAGER.set_frame_sink(frame_sink)
    return _GLOBAL_CAMERA_MANAGER


def get_global_camera_manager() -> CameraManager:
    """Return the single process-wide CameraManager instance."""
    global _GLOBAL_CAMERA_MANAGER
    if _GLOBAL_CAMERA_MANAGER is None:
        _GLOBAL_CAMERA_MANAGER = CameraManager()
    return _GLOBAL_CAMERA_MANAGER
