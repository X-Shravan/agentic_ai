import sys
import os
import traceback

print("Python version:", sys.version)
print("Current Working Directory:", os.getcwd())

# Add workspace to path just in case
sys.path.insert(0, os.getcwd())

try:
    print("Resolving YOLO model path...")
    from backend.core.model_registry import resolve_yolo_model_path
    path = resolve_yolo_model_path()
    print("Resolved path:", path)
    print("Resolved path exists:", os.path.exists(path))
except Exception as e:
    print("Failed to resolve YOLO model path:")
    traceback.print_exc()

agents = [
    ("DetectionAgent", "from backend.agents.detection_agent import DetectionAgent"),
    ("TrackingAgent", "from backend.agents.tracking_agent import TrackingAgent"),
    ("SkeletonAnalyzer", "from backend.agents.skeleton_agent import SkeletonAnalyzer"),
    ("FaceAnalysisAgent", "from backend.agents.face_agent import FaceAnalysisAgent"),
    ("GazeAgent", "from backend.agents.gaze_agent import GazeAgent"),
    ("MultiModalFusionEngine", "from backend.agents.behavior_agent import MultiModalFusionEngine"),
    ("GeminiReasoningEngine", "from backend.agents.gemini_agent import GeminiReasoningEngine"),
    ("IntegratedSurveillancePipeline", "from pipeline.integrated_pipeline import IntegratedSurveillancePipeline")
]

for name, imp in agents:
    try:
        print(f"Testing import for {name}: '{imp}'")
        exec(imp)
        print(f"✅ {name} imported successfully")
        # Try initializing if simple
        if name == "DetectionAgent":
            from backend.agents.detection_agent import DetectionAgent
            config = {"model": {"path": "models/yolo11n.pt"}}
            agent = DetectionAgent(config)
            print(f"✅ {name} initialized successfully")
        elif name == "TrackingAgent":
            from backend.agents.tracking_agent import TrackingAgent
            agent = TrackingAgent({})
            print(f"✅ {name} initialized successfully")
    except Exception as e:
        print(f"❌ Failed to import/initialize {name}:")
        traceback.print_exc()
