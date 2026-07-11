# AI Exam Surveillance

Production-oriented Agentic AI Smart Exam Surveillance System using an existing trained YOLO model, FastAPI backend, and React/Next.js-ready frontend.

## Project layout

- `frontend/` — dashboard UI assets and client application.
- `backend/` — FastAPI services, agents, LangGraph workflow, CrewAI configuration, CV modules, risk engine, evidence, and reports.
- `models/best_exam_model.pt` — required trained custom YOLO model file. Place or rename the provided `best.pt` file here; YOLO is not retrained by this project.
- `docs/architecture.md`, `docs/deployment.md`, `docs/api.md` — retained documentation.

## Model

The detection stack loads `models/best_exam_model.pt` as the primary detection engine. If your local file is named `best.pt`, move it to:

```bash
mkdir -p models
mv best.pt models/best_exam_model.pt
```

## Project structure requirement

No folder should remain empty. Every folder must contain implementation files, `__init__.py`, or starter templates. Temporary verification scripts belong in `tests/`.
