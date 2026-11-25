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
    """Return the first path that exists on disk and is a valid model binary."""
    import logging
    reg_logger = logging.getLogger(__name__)

    for path in paths:
        p = Path(path)
        if p.exists():
            # Check for corrupt placeholder text files (e.g. 53-byte placeholder text)
            if p.suffix.lower() == ".pt" and p.stat().st_size < 1024 * 1024:
                reg_logger.warning("INVALID MODEL FILE: %s is too small (%d bytes), skipping placeholder.", path, p.stat().st_size)
                continue
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
    import logging
    reg_logger = logging.getLogger(__name__)

    env_path = os.getenv("EXAM_YOLO_MODEL_PATH")
    if env_path and Path(env_path).exists():
        p = Path(env_path)
        if p.suffix.lower() == ".pt" and p.stat().st_size < 1024 * 1024:
            reg_logger.warning("INVALID MODEL FILE: %s is too small (%d bytes), skipping placeholder.", env_path, p.stat().st_size)
        else:
            return env_path

    configured_path = (config or {}).get("model", {}).get("path")
    if configured_path and Path(configured_path).exists():
        p = Path(configured_path)
        if p.suffix.lower() == ".pt" and p.stat().st_size < 1024 * 1024:
            reg_logger.warning("INVALID MODEL FILE: %s is too small (%d bytes), skipping placeholder.", configured_path, p.stat().st_size)
        else:
            return configured_path

    return first_existing_path(MODEL_SEARCH_ORDER) or CUSTOM_YOLO_MODEL_PATH
