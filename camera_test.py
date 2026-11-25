from __future__ import annotations

import json
from pathlib import Path

from camera import load_camera_config
from camera.camera_diagnostics import run_diagnostics


if __name__ == "__main__":
    payload = run_diagnostics("camera/camera_config.yaml")
    Path("camera_test_result.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("Camera diagnostics complete")
