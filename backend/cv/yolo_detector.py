"""YOLO detector entry point using the trained exam surveillance model."""
from backend.agents.detection_agent import Detection, DetectionAgent

from backend.core.model_registry import CUSTOM_YOLO_MODEL_PATH as MODEL_PATH

__all__ = ["Detection", "DetectionAgent", "MODEL_PATH"]
