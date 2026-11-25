from __future__ import annotations

from typing import Any, Iterable, List

from .camera_discovery import CameraDiscovery
from .camera_registry import CameraSource, CameraType

_TYPE_ALIASES = {
    "webcam": CameraType.LAPTOP_WEBCAM,
    "laptop": CameraType.LAPTOP_WEBCAM,
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


def _coerce_source_value(value: Any) -> Any:
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def _source_from_config(item: dict, index: int) -> CameraSource:
    raw_type = str(item.get("type", "webcam")).lower()
    camera_type = _TYPE_ALIASES.get(raw_type, CameraType.LAPTOP_WEBCAM)
    source = _coerce_source_value(item.get("source", index if camera_type in {CameraType.LAPTOP_WEBCAM, CameraType.USB_WEBCAM} else ""))
    return CameraSource(
        camera_id=item.get("camera_id") or item.get("id") or f"configured_{index}",
        name=item.get("name") or f"Configured Camera {index}",
        camera_type=camera_type,
        source=source,
        priority=int(item.get("priority", index + 1)),
        enabled=bool(item.get("enabled", True)),
        metadata={key: value for key, value in item.items() if key not in {"camera_id", "id", "name", "type", "source", "priority", "enabled"}},
    )


def build_candidate_sources(config, explicit_sources: Iterable[CameraSource] | None = None) -> List[CameraSource]:
    if explicit_sources:
        return sorted([source for source in explicit_sources if source.enabled], key=lambda item: item.priority)

    configured = [
        _source_from_config(item, index)
        for index, item in enumerate(getattr(config, "explicit_sources", []) or [])
        if item.get("enabled", True)
    ]
    if configured:
        return sorted(configured, key=lambda item: item.priority)[: config.max_active_cameras]

    discovery = CameraDiscovery(
        probe_indices=config.probe_indices,
        probe_network=config.probe_network,
    )
    discovered = discovery.discover()
    if discovered:
        return sorted(discovered, key=lambda item: item.priority)[: config.max_active_cameras]

    if config.enable_synthetic_fallback:
        return [CameraSource(
            camera_id="synthetic_0",
            name="Synthetic Simulation Camera",
            camera_type=CameraType.SYNTHETIC,
            source="synthetic://simulation",
            priority=999,
            metadata={"fallback": True},
        )]
    return []
