from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class CameraManagerConfig:
    preferred: str = "auto"
    source_order: List[str] = field(default_factory=lambda: ["webcam", "usb", "droidcam", "rtsp", "rtmp", "video_file"])
    fallback_order: List[str] = field(default_factory=lambda: ["webcam", "video_file", "synthetic"])
    probe_indices: List[int] = field(default_factory=lambda: [0, 1, 2])
    target_fps: int = 30
    width: int = 1280
    height: int = 720
    buffer_size: int = 1
    max_active_cameras: int = 4
    probe_network: bool = False
    enable_synthetic_fallback: bool = True
    explicit_sources: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _resolve_config_path(path: str | Path) -> Path:
    config_path = Path(path)
    if not config_path.exists() and str(path) == "camera_config.yaml":
        bundled_path = Path("camera") / "camera_config.yaml"
        if bundled_path.exists():
            return bundled_path
    return config_path


def load_camera_config(path: str | Path = "camera_config.yaml") -> CameraManagerConfig:
    config_path = _resolve_config_path(path)
    if not config_path.exists():
        return CameraManagerConfig(raw={})

    data = _expand_env(yaml.safe_load(config_path.read_text(encoding="utf-8")) or {})
    camera_section = data.get("camera", {})
    settings = data.get("settings", {})
    discovery = data.get("discovery", {})

    return CameraManagerConfig(
        preferred=camera_section.get("preferred", "auto"),
        source_order=list(data.get("sources", ["webcam", "usb", "droidcam", "rtsp", "rtmp", "video_file"])),
        fallback_order=list(data.get("fallback", ["webcam", "video_file", "synthetic"])),
        probe_indices=list(discovery.get("probe_indices", [0, 1, 2])),
        target_fps=int(settings.get("target_fps", 30)),
        width=int(settings.get("width", 1280)),
        height=int(settings.get("height", 720)),
        buffer_size=int(settings.get("buffer_size", 1)),
        max_active_cameras=int(settings.get("max_active_cameras", 4)),
        probe_network=bool(discovery.get("probe_network", False)),
        enable_synthetic_fallback=bool(settings.get("enable_synthetic_fallback", True)),
        explicit_sources=list(data.get("configured_sources", [])),
        raw=data,
    )


def save_camera_config(config: Dict[str, Any], path: str | Path = "camera_config.yaml") -> None:
    """Persist non-secret camera settings. Store secrets in .env and reference them as ${VAR}."""
    config_path = _resolve_config_path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
