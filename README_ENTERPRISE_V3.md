# Enterprise Agentic AI Smart Exam Surveillance System V3.0

This repository now includes an enterprise V3 blueprint and implementation scaffold for a privacy-preserving AI exam surveillance platform.

## Key Capabilities

- Multi-camera RTSP/IP CCTV processing on a local Edge AI server.
- YOLOv8 detection, DeepSORT-style identity management, seat mapping, face/gaze/pose fusion, temporal behavior analysis, risk scoring, verified evidence, Gemini JSON reasoning, and professional reports.
- LangGraph-centered workflow with CrewAI single-responsibility agents.
- WebRTC-first video streaming and metadata-only WebSocket policy.
- Supabase PostgreSQL schema for classrooms, cameras, sessions, students, behaviors, risks, evidence, reasoning, reports, and audit logs.

## Important Paths

- `docs/enterprise_architecture_v3.md`
- `enterprise/core/schemas.py`
- `enterprise/agents/vision_agents.py`
- `enterprise/agents/evidence_reporting_agents.py`
- `enterprise/agents/gemini_agent.py`
- `enterprise/workflows/langgraph_workflow.py`
- `enterprise/crews/exam_surveillance_crew.py`
- `enterprise/streaming/webrtc_gateway.py`
- `enterprise/api/app.py`
- `enterprise/db/schema.sql`
- `enterprise/config/enterprise.yaml`

## Run Enterprise API

```bash
uvicorn enterprise.api.app:app --host 0.0.0.0 --port 8000
```

## Privacy Boundary

- WebRTC streams video.
- WebSocket sends only alerts, analytics, metadata, and notifications.
- Gemini receives structured JSON only.
- Raw CCTV/video/face images remain local to the Edge AI server.
