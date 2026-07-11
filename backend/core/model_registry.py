"""Model path registry for local YOLO and embedding artifacts.

The real `.pt` files are intentionally not committed because model binaries are
large and make pull-request diffs unsupported. Place the files from the
`version1` branch into `models/` using the names below.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

CUSTOM_YOLO_MODEL_PATH = "models/yolo11n.pt"
LEGACY_CUSTOM_YOLO_MODEL_PATH = "models/best_exam_model.pt"
BASE_YOLO_MODEL_PATH = "models/yolov8n.pt"
LEGACY_BASE_YOLO_MODEL_PATH = "models/yolov8n_base.pt"
FACE_EMBEDDINGS_PATH = "models/face_embeddings.pkl"

MODEL_SEARCH_ORDER = (
    CUSTOM_YOLO_MODEL_PATH,
    LEGACY_CUSTOM_YOLO_MODEL_PATH,
    BASE_YOLO_MODEL_PATH,
    LEGACY_BASE_YOLO_MODEL_PATH,
)


def first_existing_path(paths: Iterable[str]) -> str | None:
    """Return the first path that exists on disk."""
    for path in paths:
        if Path(path).exists():
            return path
    return None


def resolve_yolo_model_path(config: dict | None = None) -> str:
    """Resolve the YOLO model path, preferring the user's `version1` files.

    Priority:
    1. `EXAM_YOLO_MODEL_PATH` environment variable.
    2. `config["model"]["path"]` if provided.
    3. `models/yolo11n.pt` from the user's `version1` branch.
    4. Backward-compatible fallbacks.
    """
    env_path = os.getenv("EXAM_YOLO_MODEL_PATH")
    if env_path:
        return env_path

    configured_path = (config or {}).get("model", {}).get("path")
    if configured_path:
        return configured_path

    return first_existing_path(MODEL_SEARCH_ORDER) or CUSTOM_YOLO_MODEL_PATH
