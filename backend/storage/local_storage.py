"""Local storage helpers."""
from pathlib import Path

def ensure_directory(path: str):
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
