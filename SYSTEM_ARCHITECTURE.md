# Enterprise AI Exam Surveillance System - Architecture

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    COLLEGE CCTV CAMERAS                          │
│                     (3-6 RTSP Streams)                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              EDGE AI SERVER (LOCAL DEPLOYMENT)                   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ CAPTURE & PREPROCESSING LAYER                            │   │
│  │  • OpenCV RTSP Capture (Thread 1)                        │   │
│  │  • Multi-camera synchronization                          │   │
│  │  • ROI cropping & frame buffering                        │   │
│  │  • Latest-frame-only Queue (maxsize=1)                   │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ DETECTION LAYER (Thread 2)                               │   │
│  │  • YOLOv8n (CUDA/TensorRT optimized)                     │   │
│  │  • Real-time inference                                   │   │
│  │  • Object detection: students, phones, books            │   │
│  │  • Confidence filtering & NMS                            │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ TRACKING LAYER (Thread 3)                                │   │
│  │  • DeepSORT Multi-person Tracking                        │   │
│  │  • Persistent track IDs                                  │   │
│  │  • 60+ simultaneous students                             │   │
│  │  • Kalman filtering & Hungarian matching                 │   │
│  │  • Occlusion handling                                    │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ FACE & SKELETON ANALYSIS (Thread 4)                      │   │
│  │  • MediaPipe Face Mesh (468 landmarks)                   │   │
│  │  • Head pose estimation (yaw, pitch, roll)               │   │
│  │  • MediaPipe Pose Lite (33 body keypoints)               │   │
│  │  • Skeleton posture analysis                             │   │
│  │  • Eye gaze tracking                                     │   │
│  │  • Iris detection                                        │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ BEHAVIOR ANALYSIS ENGINE                                 │   │
│  │  • Leaning detection                                     │   │
│  │  • Hidden phone detection                                │   │
│  │  • Excessive head turning                                │   │
│  │  • Wrist movement tracking                               │   │
│  │  • Paper/document sharing                                │   │
│  │  • Suspicious gestures                                   │   │
│  │  • Temporal logic filtering                              │   │
│  │  • Persistence windows (10/15 frame minimum)             │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ MULTI-MODAL FUSION ENGINE                                │   │
│  │  • Confidence fusion across 5 modalities:                │   │
│  │    - Face mesh (0.25 weight)                             │   │
│  │    - Gaze tracking (0.30 weight)                         │   │
│  │    - Body pose (0.25 weight)                             │   │
│  │    - Phone detection (0.15 weight)                       │   │
│  │    - Movement history (0.05 weight)                      │   │
│  │  • Risk score calculation                                │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ RISK SCORING ENGINE                                      │   │
│  │  • Dynamic risk matrix                                   │   │
│  │  • Behavior scoring (+5, +10, +12, +50, etc.)            │   │
│  │  • Risk levels: Low, Medium, High, Critical              │   │
│  │  • Temporal aggregation                                  │   │
│  │  • Alert thresholds                                      │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ GEMINI AGENTIC AI REASONING (Thread 7)                   │   │
│  │  • Intelligent analysis of structured metadata           │   │
│  │  • Multi-step reasoning                                  │   │
│  │  • Alert severity classification                         │   │
│  │  • Behavior pattern explanation                          │   │
│  │  • Context-aware suggestions                             │   │
│  │  • Non-real-time processing (batched)                    │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ WEBRTC STREAMING SERVER (Thread 5)                       │   │
│  │  • aiortc-based streaming                                │   │
│  │  • VP8/VP9 codec support                                 │   │
│  │  • Adaptive bitrate                                      │   │
│  │  • Multi-camera simultaneous streams                     │   │
│  │  • Low-latency delivery                                  │   │
│  │  • Browser-native rendering                              │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │ FASTAPI BACKEND                                          │   │
│  │  • Async HTTP endpoints                                  │   │
│  │  • WebRTC SDP offer/answer handling                      │   │
│  │  • REST APIs for metadata                                │   │
│  │  • Authentication & rate limiting                        │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────┴───────────────────────────────────────┐   │
│  │ WEBSOCKET ALERTS ONLY (Thread 6)                         │   │
│  │  • Real-time alert delivery                              │   │
│  │  • Metadata streaming (NOT video frames)                 │   │
│  │  • Tracking events                                       │   │
│  │  • Risk score updates                                    │   │
│  │  • Analytics data                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ LOCAL STORAGE                                            │   │
│  │  • Evidence snapshots                                    │   │
│  │  • Behavior logs                                         │   │
│  │  • Risk score history                                    │   │
│  │  • Performance metrics                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└───────────┬────────────────────────────────────────────────────┘
            │
            │ (Metadata only, NO video)
            │
┌───────────▼────────────────────────────────────────────────────┐
│                  CLOUD INFRASTRUCTURE                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ FastAPI Cloud Backend (Railway/Render)                  │  │
│  │  • Analytics APIs                                       │  │
│  │  • Auth & session management                            │  │
│  │  • Report generation                                    │  │
│  │  • Storage (S3)                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Supabase PostgreSQL Database                            │  │
│  │  • students table                                       │  │
│  │  • alerts table                                         │  │
│  │  • tracking_logs table                                  │  │
│  │  • risk_scores table                                    │  │
│  │  • behavior_history table                               │  │
│  │  • camera_streams table                                 │  │
│  │  • evidence_images table                                │  │
│  │  • reports table                                        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              FRONTEND DASHBOARD (Vercel)                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐    │
│  │ Next.js + React Frontend                              │    │
│  │  • Multi-camera live grid (WebRTC streams)            │    │
│  │  • Real-time alerts panel                             │    │
│  │  • Seat map with suspicious markers                   │    │
│  │  • Student risk ranking                               │    │
│  │  • Heatmap visualization                              │    │
│  │  • AI explanation cards                               │    │
│  │  • Evidence viewer                                    │    │
│  │  • Analytics charts                                   │    │
│  │  • Admin controls                                     │    │
│  │                                                       │    │
│  │ Tech Stack:                                           │    │
│  │  • React components                                   │    │
│  │  • Tailwind CSS styling                               │    │
│  │  • Shadcn UI components                               │    │
│  │  • Framer Motion animations                           │    │
│  │  • WebRTC stream rendering (native HTML <video>)      │    │
│  │  • TanStack Query for data fetching                   │    │
│  │  • Zustand for state management                       │    │
│  │  • Socket.io client for alerts                        │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Data Flow

### Real-Time Detection Pipeline
1. **Capture** → RTSP cameras capture frames
2. **Preprocess** → Latest frame only (Queue maxsize=1)
3. **Detect** → YOLOv8 inference
4. **Track** → DeepSORT tracking
5. **Analyze** → Face mesh + skeleton pose
6. **Fuse** → Multi-modal confidence fusion
7. **Score** → Risk calculation
8. **Reason** → Gemini API (batched)
9. **Alert** → WebSocket metadata delivery
10. **Stream** → WebRTC video to frontend

### WebRTC Streaming
```
Edge Server (VP8)
    ↓
WebRTC Peer Connection
    ↓
Browser (hw-accelerated rendering)
    ↓
<video> element (no React re-renders)
```

### Alert System
```
Risk Score > Threshold
    ↓
Alert triggered
    ↓
Evidence captured (local)
    ↓
WebSocket emit to frontend
    ↓
Database logged
    ↓
Gemini reasoning (async)
    ↓
Dashboard update
```

## 📊 Database Schema

### students
- student_id (PK)
- name
- roll_number
- camera_id
- seat_x, seat_y (pixel coordinates)
- created_at

### alerts
- alert_id (PK)
- student_id (FK)
- alert_type (leaning, phone, gaze, etc.)
- severity (low, medium, high, critical)
- timestamp
- evidence_path
- gemini_explanation
- created_at

### tracking_logs
- log_id (PK)
- student_id (FK)
- camera_id (FK)
- track_id (DeepSORT ID)
- bbox (JSON)
- timestamp
- created_at

### risk_scores
- risk_id (PK)
- student_id (FK)
- timestamp
- score (0-100)
- components (JSON: {gaze, pose, phone, etc.})
- risk_level (low, medium, high, critical)
- created_at

### behavior_history
- behavior_id (PK)
- student_id (FK)
- behavior_type
- duration_ms
- confidence
- timestamp
- created_at

### camera_streams
- stream_id (PK)
- camera_id
- rtsp_url
- resolution
- fps
- status
- last_seen
- created_at

### evidence_images
- evidence_id (PK)
- alert_id (FK)
- image_path
- timestamp
- created_at

### reports
- report_id (PK)
- exam_id
- generated_at
- pdf_path
- summary (JSON)
- total_alerts
- students_flagged
- created_at

## 🔧 Threading Architecture

| Thread | Task | Priority | Update Freq |
|--------|------|----------|-------------|
| 1 | Camera Capture | HIGH | Real-time |
| 2 | YOLO Inference | HIGH | Real-time |
| 3 | Tracking + Face Mesh | HIGH | Real-time |
| 4 | Skeleton Analysis | HIGH | Real-time |
| 5 | WebRTC Streaming | MEDIUM | 30 FPS |
| 6 | WebSocket Alerts | MEDIUM | Event-driven |
| 7 | Gemini Reasoning | LOW | Batched (1-2s) |

## 🚀 Performance Optimization

### Frame Processing
- **ROI Cropping**: Extract only student regions (80% speed improvement)
- **Frame Skipping**: YOLO every 2 frames
- **Latest-Frame Queue**: maxsize=1 (prevents backlog)
- **Async Processing**: Non-blocking threading

### GPU Acceleration
- **CUDA**: All detection/tracking ops
- **TensorRT**: YOLOv8 model optimization
- **ONNX**: Model export for faster inference

### Network Optimization
- **WebRTC Adaptive Bitrate**: Auto-scale based on bandwidth
- **VP8/VP9 Codecs**: Better compression than H.264
- **Metadata-Only WebSockets**: Reduce payload by 95%+

### Frontend Optimization
- **Native WebRTC**: Browser hw-acceleration
- **No React Re-renders**: Direct DOM updates via MediaStream
- **Minimal State Changes**: Zustand for efficient updates
- **Code Splitting**: Lazy load dashboard components

## 🔒 Privacy Architecture

✅ **DO NOT upload video to cloud**
✅ **Local processing only**
✅ **Metadata → Cloud (safe)**
✅ **Evidence stored locally OR encrypted S3**

## 📦 Deployment

### Local Edge Server
- **Hardware**: GPU-equipped machine (RTX 3060+)
- **OS**: Ubuntu 22.04 LTS
- **Docker**: Multi-stage build
- **Bandwidth**: ~10 Mbps per camera (WebRTC)

### Cloud Backend
- **Railway/Render**: FastAPI + Uvicorn
- **Database**: Supabase PostgreSQL
- **Storage**: Backblaze B2 or AWS S3
- **CDN**: CloudFlare

### Frontend
- **Vercel**: Next.js deployment
- **Auto-scaling**: Global edge nodes

## 🎯 Key Metrics

- **Latency**: <100ms (detection to alert)
- **Throughput**: 60+ students real-time
- **Accuracy**: >95% (with fusion)
- **FPS**: 30 FPS frontend (WebRTC adaptive)
- **GPU Memory**: <8GB (optimized)
- **Network**: ~1.5 Mbps (metadata + 1 stream)
