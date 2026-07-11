"""Camera stream API endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/cameras", tags=["cameras"])

@router.get("")
def list_cameras():
    return []
