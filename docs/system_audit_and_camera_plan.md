# System Audit, Root Cause Analysis, and Camera Layer Plan

## Dependency map
Browser → React (`frontend/src/App.js`) → component fetch calls (`REACT_APP_API_URL`, `REACT_APP_FASTAPI_URL`) → Simple API (`api_simple.py`, port 8080) for live dashboard polling and FastAPI (`backend/main.py`, port 8000) for persisted resources → camera routers / `CameraManager` → existing YOLO detection agents → existing tracking and behavior analysis agents → existing AI/risk/evidence/report agents → in-memory database store → frontend response.

## Root causes found before repair
1. `RUN_ALL.py` logged Simple API on `localhost:8080`, but `api_simple.py` actually bound `localhost:5000`, conflicting with the Flask dashboard and causing the Simple API process to exit with code 1.
2. The active React dashboard defaulted to `http://localhost:5000/api`, which is the Flask dashboard port, not the Simple API port advertised by `RUN_ALL.py`.
3. The active React components called Simple API routes (`/api/dashboard`, `/api/camera/frame`, `/api/analytics/timeline`) that are not provided by FastAPI, so switching the UI directly to port 8000 caused failed requests and zero metrics.
4. `api_simple.py` did not expose compatibility routes for cameras, students, alerts, evidence, reports, or agent status, so parts of the UI and verification checks could not load those resources from the Simple API surface.
5. Camera capture was scattered through direct `cv2.VideoCapture()` calls in surveillance, Flask dashboard, and simplified runner code, making webcam/USB/DroidCam/RTSP/MJPEG/file support inconsistent.
6. Existing FastAPI camera registration accepted only a small legacy RTSP shape and did not expose update/delete validation endpoints needed for runtime camera management.

## Camera architecture
React camera selector → FastAPI `/api/cameras` add/edit/remove/heartbeat → stored camera definitions → `CameraManager` → `CameraSource` implementations for webcam, USB, DroidCam, RTSP, HTTP/MJPEG, local file → frame reads/reconnect/health → existing surveillance agent frame objects → YOLO → tracking → behavior analysis → AI agents → evidence/report/database responses.

## Validation notes
- Code changes are limited to connectivity repair, camera API compatibility, and camera acquisition abstraction.
- Detection, tracking, behavior analysis, risk scoring, Gemini, CrewAI, and report-generation algorithms were not modified.
