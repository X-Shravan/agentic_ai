# AI Exam Surveillance

Production-oriented Agentic AI Smart Exam Surveillance System using an existing trained YOLO model, FastAPI backend, and React/Next.js-ready frontend.

## Project layout

- `frontend/` — dashboard UI assets and client application.
- `backend/` — FastAPI services, agents, LangGraph workflow, CrewAI configuration, CV modules, risk engine, evidence, and reports.
- `models/yolo11n.pt` — primary custom trained YOLO model from branch/version1; `models/yolov8n.pt` is supported as the base/fallback model. YOLO is not retrained by this project.
- `docs/architecture.md`, `docs/deployment.md`, `docs/api.md` — retained documentation.

## Model

The detection stack resolves the YOLO model in this order: `EXAM_YOLO_MODEL_PATH`, configured model path, `models/yolo11n.pt`, `models/best_exam_model.pt`, `models/yolov8n.pt`, then `models/yolov8n_base.pt`. Copy your branch/version1 files into `models/` locally:

```bash
mkdir -p models
cp /path/to/yolo11n.pt models/yolo11n.pt
cp /path/to/yolov8n.pt models/yolov8n.pt
```

## Project structure requirement

No folder should remain empty. Every folder must contain implementation files, `__init__.py`, or starter templates. Temporary verification scripts belong in `tests/`.
