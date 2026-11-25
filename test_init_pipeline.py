import sys
import os
import traceback

sys.path.insert(0, os.getcwd())

config = {
    "webrtc": {
        "bitrate": 2500000,
        "fps": 30,
    },
    "alert_thresholds": {
        "low": 20,
        "medium": 40,
        "high": 60,
        "critical": 80,
    }
}

try:
    print("Initializing WebRTC server...")
    from backend.api import websocket as webrtc_module
    server = webrtc_module.init_webrtc_server(config)
    
    print("Trying to import IntegratedSurveillancePipeline...")
    from pipeline.integrated_pipeline import IntegratedSurveillancePipeline
    
    print("Trying to instantiate IntegratedSurveillancePipeline...")
    pipeline = IntegratedSurveillancePipeline(config, webrtc_server=server)
    print("✅ Pipeline instantiated successfully!")
    
    print("Pipeline health state:", pipeline.health())
except Exception as e:
    print("❌ Pipeline initialization failed:")
    traceback.print_exc()
