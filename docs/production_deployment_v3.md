# Production Deployment Guide

## Services

- Frontend: Next.js dashboard deployed to Vercel.
- API backend: FastAPI deployed to Railway or Render for metadata, reports, and authentication callbacks.
- Edge AI server: Local GPU server inside the institution network for RTSP capture, CV inference, WebRTC, and evidence processing.
- Database: Supabase PostgreSQL with Auth, Storage, Realtime, and RLS.
- Queue/cache: Redis + Celery for Gemini reasoning, report generation, and evidence clip jobs.

## Privacy Rules

- Do not upload live CCTV streams, raw student videos, face images, or biometric frames to cloud services.
- Keep RTSP credentials on the local edge server or a local secret manager.
- Send Gemini only structured JSON metadata generated after risk thresholding.
- Store only verified evidence artifacts and reports in Supabase Storage according to retention policy.

## Edge Startup

```bash
uvicorn enterprise.api.app:app --host 0.0.0.0 --port 8000
```

## Production Checklist

- Configure HTTPS and WSS at the reverse proxy.
- Enable JWT validation and role-based access for invigilator, admin, auditor, and viewer roles.
- Enable Supabase RLS policies before production traffic.
- Configure GPU runtime for CUDA, TensorRT, or ONNX Runtime.
- Validate WebRTC SDP negotiation through `server/webrtc_server.py` or a TURN-enabled media gateway.
- Configure audit log retention and evidence retention windows.
- Run load tests with 3-6 cameras and synthetic 60+ student tracks.
