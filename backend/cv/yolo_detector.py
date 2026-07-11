"""YOLO detector entry point using the trained exam surveillance model."""
from backend.agents.detection_agent import Detection, DetectionAgent

MODEL_PATH = "models/best_exam_model.pt"

__all__ = ["Detection", "DetectionAgent", "MODEL_PATH"]
