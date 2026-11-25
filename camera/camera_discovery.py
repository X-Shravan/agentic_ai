from __future__ import annotations

import os
import socket
from dataclasses import asdict
from pathlib import Path
from typing import List
from urllib.parse import urlparse

import cv2

from .camera_registry import CameraSource, CameraType


class CameraDiscovery:
    """Detect available camera sources automatically."""

    def __init__(self, probe_indices: List[int] | None = None, probe_network: bool = False):
        self.probe_indices = probe_indices or [0, 1, 2]
        self.probe_network = probe_network

    def discover(self) -> List[CameraSource]:
        cameras: List[CameraSource] = []
        cameras.extend(self._discover_webcams())
        cameras.extend(self._discover_droidcam())
        cameras.extend(self._discover_rtsp())
        cameras.extend(self._discover_video_files())
        cameras.extend(self._discover_env_sources())
        return self._dedupe(cameras)

    def _discover_webcams(self) -> List[CameraSource]:
        sources: List[CameraSource] = []
        for index in self.probe_indices:
            cap = cv2.VideoCapture(index)
            try:
                if cap.isOpened():
                    sources.append(CameraSource(
                        camera_id=f"webcam_{index}",
                        name=f"Laptop/USB Camera {index}",
                        camera_type=CameraType.LAPTOP_WEBCAM if index == 0 else CameraType.USB_WEBCAM,
                        source=index,
                        priority=index + 1,
                        metadata={"index": index},
                    ))
            finally:
                cap.release()
        return sources

    def _discover_droidcam(self) -> List[CameraSource]:
        sources: List[CameraSource] = []
        for port in (4747, 8080):
            for host in self._candidate_hosts():
                url = f"http://{host}:{port}/video"
                if self._probe_url(url):
                    sources.append(CameraSource(
                        camera_id=f"droidcam_{host}_{port}",
                        name=f"DroidCam {host}:{port}",
                        camera_type=CameraType.DROIDCAM,
                        source=url,
                        priority=10,
                        metadata={"host": host, "port": port},
                    ))
                    break
        return sources

    def _discover_rtsp(self) -> List[CameraSource]:
        env_url = os.getenv("DEFAULT_RTSP_URL")
        if env_url and env_url.startswith("rtsp://"):
            return [CameraSource(
                camera_id="rtsp_default",
                name="RTSP Camera",
                camera_type=CameraType.RTSP,
                source=env_url,
                priority=20,
                metadata={"from_env": True},
            )]
        return []

    def _discover_video_files(self) -> List[CameraSource]:
        candidates = []
        for filename in ("video.mp4", "video.avi", "sample.mp4", "sample.avi"):
            path = Path(filename)
            if path.exists():
                candidates.append(CameraSource(
                    camera_id=f"file_{path.stem}",
                    name=f"Video File {path.name}",
                    camera_type=CameraType.VIDEO_FILE,
                    source=str(path),
                    priority=90,
                    metadata={"path": str(path)},
                ))
        return candidates

    def _discover_env_sources(self) -> List[CameraSource]:
        sources: List[CameraSource] = []
        for key in ("CAMERA_SOURCE", "DROIDCAM_URL", "RTSP_URL", "RTMP_URL"):
            value = os.getenv(key)
            if not value:
                continue
            if value.startswith("rtsp://"):
                ctype = CameraType.RTSP
            elif value.startswith("rtmp://"):
                ctype = CameraType.RTMP
            elif value.startswith("http://") or value.startswith("https://"):
                ctype = CameraType.DROIDCAM
            else:
                ctype = CameraType.VIDEO_FILE if Path(value).exists() else CameraType.SYNTHETIC
            sources.append(CameraSource(
                camera_id=key.lower(),
                name=f"{key.replace('_', ' ').title()}",
                camera_type=ctype,
                source=value,
                priority=30,
                metadata={"env_var": key},
            ))
        return sources

    def _candidate_hosts(self) -> List[str]:
        hosts = ["127.0.0.1", "localhost"]
        if self.probe_network:
            hostname = socket.gethostname()
            try:
                hosts.append(socket.gethostbyname(hostname))
            except Exception:
                pass
        return hosts

    def _probe_url(self, url: str, timeout: float = 1.0) -> bool:
        cap = cv2.VideoCapture(url)
        try:
            if not cap.isOpened():
                return False
            ok, _ = cap.read()
            return ok
        finally:
            cap.release()

    def _dedupe(self, cameras: List[CameraSource]) -> List[CameraSource]:
        seen = set()
        result = []
        for camera in cameras:
            key = (camera.camera_type.value, str(camera.source))
            if key in seen:
                continue
            seen.add(key)
            result.append(camera)
        return result
