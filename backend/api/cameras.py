"""Camera stream API endpoints for multi-camera WebRTC monitoring."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.websocket import get_webrtc_server
from backend.database.store import store

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraCreate(BaseModel):
    camera_id: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    type: str = "webcam"
    device_index: Optional[int] = None
    url: Optional[str] = None
    rtsp_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    location: Optional[str] = None
    resolution: list[int] = [1280, 720]
    fps: int = 30
    enabled: bool = True


def _public_camera(payload: Dict[str, Any]) -> Dict[str, Any]:
    camera = dict(payload)
    if camera.get("password"):
        camera["password"] = "********"
    return camera


def _validate_camera(payload: Dict[str, Any]) -> None:
    camera_type = str(payload.get("type") or "webcam").lower()
    source_url = payload.get("url") or payload.get("rtsp_url")
    if camera_type in {"rtsp", "http", "mjpeg", "ip", "droidcam"} and not source_url and payload.get("device_index") is None:
        raise HTTPException(status_code=400, detail=f"{camera_type} camera requires url/rtsp_url or device_index")
    if camera_type == "file" and (not source_url or not Path(str(source_url)).exists()):
        raise HTTPException(status_code=400, detail="Video file source does not exist")
    if len(payload.get("resolution") or []) != 2:
        raise HTTPException(status_code=400, detail="resolution must be [width, height]")


@router.get("")
def list_cameras(session_id: Optional[str] = None):
    cameras = store.list("camera_streams", session_id=session_id)
    try:
        statuses = get_webrtc_server().get_all_cameras_status()
    except Exception:
        statuses = {}
    for camera in cameras:
        camera.update(statuses.get(camera["camera_id"], {}))
    return [_public_camera(camera) for camera in cameras]


@router.post("")
def register_camera(camera: CameraCreate):
    payload = camera.model_dump()
    payload["rtsp_url"] = payload.get("rtsp_url") or payload.get("url")
    _validate_camera(payload)
    payload.setdefault("status", "registered")
    item = store.upsert("camera_streams", "camera_id", payload)
    try:
        get_webrtc_server().register_camera(camera.camera_id)
    except Exception:
        pass
    return _public_camera(item)


@router.get("/{camera_id}")
def get_camera(camera_id: str):
    cameras = store.list("camera_streams")
    camera = next((item for item in cameras if item.get("camera_id") == camera_id), None)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        camera.update(get_webrtc_server().get_camera_status(camera_id))
    except Exception:
        pass
    return _public_camera(camera)


@router.put("/{camera_id}")
def update_camera(camera_id: str, payload: Dict[str, Any]):
    payload = {"camera_id": camera_id, **payload}
    payload["rtsp_url"] = payload.get("rtsp_url") or payload.get("url")
    _validate_camera(payload)
    item = store.upsert("camera_streams", "camera_id", payload)
    return _public_camera(item)


@router.delete("/{camera_id}")
def remove_camera(camera_id: str):
    if camera_id not in store.camera_streams:
        raise HTTPException(status_code=404, detail="Camera not found")
    del store.camera_streams[camera_id]
    return {"status": "removed", "camera_id": camera_id}


@router.post("/{camera_id}/heartbeat")
def camera_heartbeat(camera_id: str, payload: Dict[str, Any]):
    item = store.upsert("camera_streams", "camera_id", {"camera_id": camera_id, **payload, "status": "streaming"})
    return _public_camera(item)
