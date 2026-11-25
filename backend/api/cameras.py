"""Camera management API endpoints for discovery, health, and WebRTC monitoring."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from backend.api.websocket import get_webrtc_server
from backend.database.store import store
from camera import get_global_camera_manager
from camera.camera_config import load_camera_config, save_camera_config

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraCreate(BaseModel):
    camera_id: str
    session_id: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    resolution: list[int] = [1280, 720]
    fps: int = 30
    name: Optional[str] = None
    camera_type: Optional[str] = None
    source: Optional[Any] = None
    enabled: bool = True


class CameraUpdate(BaseModel):
    session_id: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    resolution: Optional[list[int]] = None
    fps: Optional[int] = None
    name: Optional[str] = None
    camera_type: Optional[str] = None
    source: Optional[Any] = None
    enabled: Optional[bool] = None


class CameraConfigPayload(BaseModel):
    config: Dict[str, Any]


def _webrtc_statuses() -> Dict[str, Any]:
    try:
        return get_webrtc_server().get_all_cameras_status()
    except Exception:
        return {}


def _sync_runtime_camera(payload: Dict[str, Any]) -> dict:
    manager = get_global_camera_manager()
    existing = manager.camera_sources.get(payload["camera_id"])
    requested_source = payload.get("source") or payload.get("rtsp_url")
    runtime_source = requested_source if requested_source not in (None, "") else (existing.source if existing else None)
    runtime_type = payload.get("camera_type") or (existing.camera_type.value if existing else None)
    runtime_name = payload.get("name") or payload.get("location") or (existing.name if existing else None)
    runtime_enabled = payload.get("enabled", existing.enabled if existing else True)
    try:
        source = manager.register_source(
            payload["camera_id"],
            runtime_source,
            name=runtime_name,
            camera_type=runtime_type,
            enabled=runtime_enabled,
            metadata={
                "session_id": payload.get("session_id"),
                "location": payload.get("location"),
                "resolution": payload.get("resolution"),
                "fps": payload.get("fps"),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Camera manager synchronization failed: {exc}") from exc
    get_webrtc_server().register_camera(payload["camera_id"])
    return source.to_dict()


@router.get("/discover")
def discover_cameras():
    manager = get_global_camera_manager()
    manager.refresh_sources()
    return {
        "detected_cameras": manager.detected_cameras(),
        "summary": manager.summary(),
    }


@router.get("/status")
def camera_manager_status():
    manager = get_global_camera_manager()
    payload = manager.summary()
    payload["webrtc"] = _webrtc_statuses()
    return payload


@router.post("/auto-connect")
def auto_connect_cameras():
    return get_global_camera_manager().auto_discover_and_connect()


@router.post("/config")
def save_camera_settings(payload: CameraConfigPayload):
    save_camera_config(payload.config, "camera/camera_config.yaml")
    manager = get_global_camera_manager()
    manager.stop_all()
    manager.config = load_camera_config("camera/camera_config.yaml")
    manager.refresh_sources()
    return {"saved": True, "summary": manager.summary()}


@router.get("")
def list_cameras(session_id: Optional[str] = None):
    cameras = store.list("camera_streams", session_id=session_id)
    statuses = get_global_camera_manager().get_all_status()
    webrtc_statuses = _webrtc_statuses()
    if not cameras:
        cameras = get_global_camera_manager().detected_cameras()
    for camera in cameras:
        camera_id = camera.get("camera_id")
        camera.update(statuses.get(camera_id, {}))
        camera["webrtc"] = webrtc_statuses.get(camera_id, {})
    return cameras


@router.post("", status_code=status.HTTP_201_CREATED)
def register_camera(camera: CameraCreate):
    payload = camera.model_dump()
    payload["status"] = "registered"
    item = store.upsert("camera_streams", "camera_id", payload)
    try:
        item["runtime"] = _sync_runtime_camera(item)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime synchronization failed: {exc}") from exc
    return item


@router.put("/{camera_id}")
def update_camera(camera_id: str, camera: CameraUpdate):
    existing = next((item for item in store.list("camera_streams") if item.get("camera_id") == camera_id), None)
    if existing is None and get_global_camera_manager().get_status(camera_id).get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Camera not found")
    item = store.upsert("camera_streams", "camera_id", {
        "camera_id": camera_id,
        **camera.model_dump(exclude_none=True),
    })
    item["runtime"] = _sync_runtime_camera(item)
    return item


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: str):
    manager_removed = get_global_camera_manager().unregister_source(camera_id)
    store_removed = store.delete("camera_streams", "camera_id", camera_id)
    try:
        webrtc_removed = await get_webrtc_server().unregister_camera(camera_id)
    except Exception:
        webrtc_removed = False
    if not (manager_removed or store_removed or webrtc_removed):
        raise HTTPException(status_code=404, detail="Camera not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{camera_id}/connect")
def connect_camera(camera_id: str):
    manager = get_global_camera_manager()
    if not manager.connect(camera_id):
        raise HTTPException(status_code=400, detail="Camera Not Found or Unable to Connect")
    return manager.get_status(camera_id)


@router.post("/{camera_id}/disconnect")
def disconnect_camera(camera_id: str):
    manager = get_global_camera_manager()
    if not manager.disconnect(camera_id):
        raise HTTPException(status_code=404, detail="Camera not connected")
    return manager.get_status(camera_id)


@router.post("/{camera_id}/restart")
def restart_camera(camera_id: str):
    manager = get_global_camera_manager()
    if not manager.restart(camera_id):
        raise HTTPException(status_code=400, detail="Unable to restart camera")
    return manager.get_status(camera_id)


@router.get("/{camera_id}")
def get_camera(camera_id: str):
    cameras = store.list("camera_streams")
    camera = next((item for item in cameras if item.get("camera_id") == camera_id), None)
    status = get_global_camera_manager().get_status(camera_id)
    if not camera and status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Camera not found")
    camera = camera or {"camera_id": camera_id}
    camera.update(status)
    try:
        camera["webrtc"] = get_webrtc_server().get_camera_status(camera_id)
    except Exception:
        pass
    return camera


@router.post("/{camera_id}/heartbeat")
def camera_heartbeat(camera_id: str, payload: Dict[str, Any]):
    existing = next((item for item in store.list("camera_streams") if item.get("camera_id") == camera_id), None)
    if existing is None and get_global_camera_manager().get_status(camera_id).get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Camera not found")
    item = store.upsert("camera_streams", "camera_id", {
        "camera_id": camera_id,
        **payload,
        "status": "streaming",
        "last_seen": datetime.now(timezone.utc).isoformat(),
    })
    _sync_runtime_camera(item)
    return item
