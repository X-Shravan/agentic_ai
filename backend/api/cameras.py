"""Camera stream API endpoints for multi-camera WebRTC monitoring."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.websocket import get_webrtc_server
from backend.database.store import store

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraCreate(BaseModel):
    camera_id: str
    session_id: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    resolution: list[int] = [1280, 720]
    fps: int = 30


@router.get("")
def list_cameras(session_id: Optional[str] = None):
    cameras = store.list("camera_streams", session_id=session_id)
    try:
        statuses = get_webrtc_server().get_all_cameras_status()
    except Exception:
        statuses = {}
    for camera in cameras:
        camera.update(statuses.get(camera["camera_id"], {}))
    return cameras


@router.post("")
def register_camera(camera: CameraCreate):
    payload = camera.model_dump()
    payload.setdefault("status", "registered")
    item = store.upsert("camera_streams", "camera_id", payload)
    try:
        get_webrtc_server().register_camera(camera.camera_id)
    except Exception:
        pass
    return item


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
    return camera


@router.post("/{camera_id}/heartbeat")
def camera_heartbeat(camera_id: str, payload: Dict[str, Any]):
    item = store.upsert("camera_streams", "camera_id", {"camera_id": camera_id, **payload, "status": "streaming"})
    return item
