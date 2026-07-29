# Existing UI and Backend Integration Report

## Existing structure analyzed
- `frontend/src` contains the active React application (`App.js`, `index.js`, `index.css`) plus legacy component modules for alerts, analytics, camera feed, header, insights, sidebar, statistics, and system status.
- `frontend/services`, `frontend/hooks`, `frontend/pages`, and top-level TSX component folders contain an alternate/legacy Next-style surface and service hooks that are not the active `react-scripts` entrypoint.
- `backend/main.py` mounts the FastAPI app, CORS, REST endpoints, WebRTC offer handling, and `/ws/alerts/{user_id}` WebSocket alerts.
- `backend/api` exposes the persisted backend APIs for alerts, evidence, risk, cameras, students, sessions, and reports.
- `backend/database/store.py` provides the in-process data store backing the API modules.

## API endpoints connected in the redesigned UI
- Health: `GET /health`.
- Students and student profiles: `GET /api/students`, `GET /api/students/{student_id}`.
- Cameras and live status: `GET /api/cameras`, `GET /api/webrtc/cameras/status`.
- Alerts, Gemini explanations, and alert metadata: `GET /api/alerts`.
- Evidence: `GET /api/alerts/evidence`.
- Reports: `GET /api/reports`, `POST /api/reports/generate`, `GET /api/reports/{report_id}/download`.
- Analytics: `GET /api/analytics/dashboard`.
- Realtime alerts: `WS /ws/alerts/{user_id}` with a `global` subscription.

## Findings
- The active UI was polling non-existent legacy routes such as `/api/dashboard`, `/api/camera/frame`, and `/api/analytics/timeline` for its primary dashboard state.
- Multiple components used static trend labels even when no backend data existed.
- The backend does not currently expose dedicated acknowledge/resolve/review mutation routes; the redesigned UI avoids inventing fake persistence and relies only on available backend routes.
- The backend exposes WebRTC signaling, but no persisted camera list may exist until cameras are registered; the UI now renders backend empty states instead of placeholder imagery.
- Environment variables used by the active UI are `REACT_APP_API_URL` and optional `REACT_APP_WS_URL`.

## Redesign summary
- Replaced the fragmented dashboard composition with an enterprise surveillance command center layout.
- Every metric is derived from REST/WebSocket responses, with explicit empty/error states when the backend returns no records.
- Added global backend-backed search across students, cameras, and alerts.
- Added responsive layouts for desktop, laptop, tablet, and small screens.
