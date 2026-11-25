from __future__ import annotations

import argparse
import json
from pathlib import Path

from .camera_config import load_camera_config
from .camera_manager import CameraManager


def run_diagnostics(config_path: str = "camera_config.yaml") -> dict:
    config = load_camera_config(config_path)
    manager = CameraManager(config)
    detected = manager.detected_cameras()
    auto = manager.auto_discover_and_connect()
    payload = {
        "config_path": config_path,
        "detected_cameras": detected,
        "summary": auto,
    }
    print(json.dumps(payload, indent=2, default=str))
    manager.stop_all()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Camera diagnostics for Agentic AI Exam Surveillance")
    parser.add_argument("--config", default="camera_config.yaml")
    args = parser.parse_args()
    run_diagnostics(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
