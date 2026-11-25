"""Professional camera management subsystem for Agentic AI Exam Surveillance."""

from .camera_config import CameraManagerConfig, load_camera_config, save_camera_config
from .camera_manager import CameraManager, get_global_camera_manager, init_global_camera_manager
from .camera_registry import CameraFrame, CameraSource, CameraStatus, CameraType

__all__ = [
    "CameraFrame",
    "CameraManager",
    "CameraManagerConfig",
    "CameraSource",
    "CameraStatus",
    "CameraType",
    "get_global_camera_manager",
    "init_global_camera_manager",
    "load_camera_config",
    "save_camera_config",
]