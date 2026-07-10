# Enterprise AI Surveillance System - Complete Deployment Guide

## 📋 Table of Contents
1. [System Requirements](#system-requirements)
2. [Architecture Overview](#architecture-overview)
3. [Local Development Setup](#local-development-setup)
4. [Production Deployment](#production-deployment)
5. [Configuration](#configuration)
6. [API Documentation](#api-documentation)
7. [Troubleshooting](#troubleshooting)

---

## 🖥️ System Requirements

### Hardware
- **GPU**: NVIDIA GPU with CUDA Compute Capability 7.0+
  - Recommended: RTX 3060 or higher
  - For 60+ students: RTX A6000 or A100
- **CPU**: 8+ cores (16+ for production)
- **RAM**: 32GB minimum (64GB for 100+ students)
- **Storage**: 500GB+ SSD (for logs, evidence)
- **Network**: Gigabit Ethernet

### Software
- **OS**: Ubuntu 22.04 LTS or Windows Server 2022
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.11+ (for development)
- **CUDA**: 12.3+
- **cuDNN**: 8.x

### Network Requirements
- **Bandwidth**: 
  - Per camera: ~5-10 Mbps (WebRTC)
  - Total: 30-60 Mbps for 6 cameras
- **Latency**: <100ms optimal
- **Firewall**: Ports 8000-8002, 443 (HTTPS)

---

## 🏗️ Architecture Overview

### System Components

```
┌─────────────────────────────────────────────┐
│      COLLEGE CCTV CAMERAS (RTSP)            │
└────────────┬────────────────────────────────┘
             │
┌────────────▼────────────────────────────────┐
│    EDGE AI SERVER (Docker Container)        │
│  ┌────────────────────────────────────────┐ │
│  │ YOLO Detection + MediaPipe + Tracking  │ │
│  │ Skeleton Analysis + Fusion Engine      │ │
│  │ WebRTC Streaming + Gemini Reasoning    │ │
│  └────────────────────────────────────────┘ │
└────────────┬────────────────────────────────┘
             │
     ┌───────┴───────┐
     │               │
┌────▼──────┐  ┌────▼──────┐
│  WebRTC   │  │ WebSocket │
│ Streaming │  │   Alerts  │
└────┬──────┘  └────┬──────┘
     │              │
     └──────┬───────┘
            │
     ┌──────▼──────────┐
     │ Frontend Dashboard
     │ (Vercel/Next.js)
     └─────────────────┘
```

### Data Flow

1. **Capture**: RTSP cameras → OpenCV capture thread
2. **Detection**: YOLOv8 real-time inference
3. **Tracking**: DeepSORT multi-person tracking
4. **Analysis**: Face mesh + skeleton pose simultaneously
5. **Fusion**: Multi-modal confidence aggregation
6. **Reasoning**: Gemini API for intelligent analysis
7. **Streaming**: WebRTC to frontend (low latency)
8. **Alerting**: WebSocket for metadata & alerts

---

## 🚀 Local Development Setup

### Step 1: Clone & Setup

```bash
# Clone repository
git clone <repo-url>
cd mini\ project

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-enterprise.txt
```

### Step 2: Environment Configuration

```bash
# Create .env file
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required environment variables:**
```env
# Gemini API
GEMINI_API_KEY=your_api_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/surveillance

# Server
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# WebRTC
WEBRTC_BITRATE=2500000
WEBRTC_FPS=30

# RTSP Cameras
CAMERA_0_RTSP=rtsp://camera-ip:554/stream
CAMERA_1_RTSP=rtsp://camera-ip:554/stream
# ... up to CAMERA_5

# Alert thresholds
ALERT_LOW_THRESHOLD=20
ALERT_MEDIUM_THRESHOLD=40
ALERT_HIGH_THRESHOLD=60
```

### Step 3: Database Setup

```bash
# Start PostgreSQL (Docker)
docker run -d \
  --name surveillance-db \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=surveillance \
  -p 5432:5432 \
  postgres:15-alpine

# Run migrations
python -m alembic upgrade head

# Or manually run SQL
psql -U postgres -d surveillance -f migrations/001_initial_schema.sql
```

### Step 4: Start Services

```bash
# Terminal 1: FastAPI Backend
python -m uvicorn server.api_fastapi:app --reload --port 8000

# Terminal 2: Camera Capture + Detection
python main.py --config config/config.yaml

# Terminal 3: WebRTC Server
python -m server.webrtc_server --port 8001

# Terminal 4: WebSocket Alerts
python -m server.websocket_alerts --port 8002
```

### Step 5: Test System

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs

# Frontend (if running separately)
npm run dev
```

---

## 🌍 Production Deployment

### Option 1: Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f edge-ai

# Stop all
docker-compose down
```

### Option 2: Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace surveillance

# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Scale replicas
kubectl scale deployment edge-ai --replicas=3 -n surveillance

# Monitor
kubectl logs -f deployment/edge-ai -n surveillance
```

### Option 3: Cloud Deployment (Railway/Render)

**For FastAPI Backend only** (keep edge AI local for privacy/performance):

```bash
# Railway.app
railway link
railway up

# Render
git push heroku main  # After setting Render git integration
```

---

## ⚙️ Configuration

### config/config.yaml

```yaml
# System Configuration
system:
  name: "Enterprise Exam Surveillance"
  version: "1.0.0"
  environment: "production"

# Cameras
cameras:
  - id: "camera_1"
    rtsp: "rtsp://192.168.1.100:554/stream"
    resolution: [1920, 1080]
    fps: 30
    enabled: true
  - id: "camera_2"
    rtsp: "rtsp://192.168.1.101:554/stream"
    resolution: [1920, 1080]
    fps: 30
    enabled: true
  # ... up to 6 cameras

# YOLO Detection
detection:
  model: "yolov8n"  # nano for speed
  confidence: 0.5
  nms_threshold: 0.45
  devices: ["student", "phone", "book"]
  frame_skip: 2  # Process every 2nd frame

# Tracking
tracking:
  algorithm: "deepsort"
  max_age: 30
  min_hits: 3
  max_dist: 0.5

# Face Mesh & Pose
analysis:
  face_mesh_enabled: true
  pose_enabled: true
  pose_model: "lite"  # lite, full
  min_detection_confidence: 0.5

# WebRTC
webrtc:
  codec: "vp8"
  bitrate: 2500000
  fps: 30
  adaptive: true

# Risk Scoring
risk:
  weights:
    gaze: 0.30
    pose: 0.25
    phone: 0.20
    leaning: 0.15
    movement: 0.10
  thresholds:
    low: 20
    medium: 40
    high: 60
    critical: 80

# Gemini AI
gemini:
  enabled: true
  model: "gemini-2.0-flash"
  batch_size: 5
  batch_interval: 2  # seconds

# Alerts
alerts:
  enabled: true
  websocket_enabled: true
  email_enabled: false
  database_logging: true
  evidence_capture: true
  evidence_dir: "evidence/"

# Performance
performance:
  max_threads: 8
  gpu_memory_limit: 0.8  # 80% of GPU
  frame_buffer_size: 1  # Latest frame only
  temporal_window: 15  # frames
```

---

## 📚 API Documentation

### WebRTC Endpoints

#### POST `/api/webrtc/{camera_id}/offer`
Exchange SDP offer/answer for WebRTC peer connection

**Request:**
```json
{
  "sdp": "v=0\r\no=- ...",
  "type": "offer"
}
```

**Response:**
```json
{
  "sdp": "v=0\r\no=- ...",
  "type": "answer"
}
```

#### GET `/api/webrtc/cameras/status`
Get status of all cameras

**Response:**
```json
{
  "cameras": {
    "camera_1": {
      "status": "streaming",
      "connected_peers": 2,
      "fps": 30,
      "codec": "vp8"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Alert Endpoints

#### POST `/api/alerts/publish`
Publish alert from detection pipeline

**Request:**
```json
{
  "alert_id": "uuid",
  "student_id": "123",
  "timestamp": "2024-01-15T10:30:00Z",
  "severity": "high",
  "reason": "Hidden phone usage detected",
  "behaviors": [...],
  "evidence_captured": true
}
```

#### GET `/api/alerts/history`
Get historical alerts

**Query Parameters:**
- `limit`: Max results (default: 50)
- `student_id`: Filter by student
- `severity`: Filter by severity

### WebSocket Alerts

#### Subscribe
```javascript
ws.send(JSON.stringify({
  type: "subscribe",
  camera_id: "camera_1"
}));
```

#### Alert Message
```json
{
  "type": "alert",
  "data": {
    "alert_id": "uuid",
    "severity": "high",
    "reason": "...",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

---

## 🔧 Troubleshooting

### GPU Memory Issues

```bash
# Check GPU usage
nvidia-smi

# Reduce batch size
export BATCH_SIZE=1

# Use GPU memory limit
export TF_FORCE_GPU_ALLOW_GROWTH=true
```

### WebRTC Connection Issues

```bash
# Check if port forwarding is working
nc -zv server-ip 8000

# Verify STUN/TURN servers
# Add to config.yaml:
# webrtc:
#   stun_servers:
#     - stun:stun.l.google.com:19302
#   turn_servers:
#     - urls: ["turn:turn.example.com"]
```

### Slow Detection

```bash
# Check if frames are backlogging
# Monitor frame_buffer queue size

# Solutions:
1. Increase FRAME_SKIP
2. Reduce detection confidence threshold
3. Use YOLO nano model
4. Enable GPU optimization
```

### Database Connection Errors

```bash
# Check PostgreSQL connection
psql -h localhost -U postgres -d surveillance

# Verify connection string
echo $DATABASE_URL

# Migrate database
alembic upgrade head
```

### WebSocket Disconnections

```yaml
# Increase timeouts in config.yaml
webrtc:
  ping_timeout: 60
  ping_interval: 25
  pong_timeout: 10
```

---

## 📊 Monitoring & Logging

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f edge-ai

# Real-time monitoring
docker stats
```

### Performance Metrics
```bash
# CPU/Memory usage
docker stats surveillance-edge-ai

# GPU usage
watch -n 1 nvidia-smi

# Network throughput
nethogs -t
```

### Health Checks
```bash
# API health
curl http://localhost:8000/health

# Database health
curl http://localhost:8000/api/database/health

# Camera health
curl http://localhost:8000/api/cameras/status
```

---

## 🔐 Security

### SSL/TLS Setup

```bash
# Generate self-signed cert (development)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Copy to nginx directory
cp cert.pem ssl/
cp key.pem ssl/
```

### Authentication

```env
# Add JWT authentication
JWT_SECRET=your_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600  # 1 hour
```

### Database Security

```env
# Use strong password
DB_PASSWORD=GenerateSecurePassword123!@#

# Restrict database access
# In docker-compose.yml, don't expose ports in production
```

---

## 📞 Support & Documentation

- **API Docs**: http://localhost:8000/docs
- **System Architecture**: See SYSTEM_ARCHITECTURE.md
- **GitHub Issues**: https://github.com/your-repo/issues
- **Email**: support@surveillance-system.local

---

## ✅ Deployment Checklist

- [ ] All system requirements met
- [ ] Environment variables configured
- [ ] Database initialized and migrated
- [ ] SSL/TLS certificates installed
- [ ] CCTV cameras accessible
- [ ] Gemini API key configured
- [ ] Docker images built successfully
- [ ] All services healthy
- [ ] WebRTC streaming tested
- [ ] Alerts functioning
- [ ] Frontend connected
- [ ] Monitoring setup
- [ ] Backups configured
- [ ] Security audit completed

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Maintained By**: AI Surveillance Team
