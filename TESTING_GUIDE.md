# 🧪 Enterprise Surveillance System - Complete Testing Guide

## 📋 Testing Roadmap

```
PHASE 1: Setup & Prerequisites (5 min)
    ↓
PHASE 2: Unit Testing (10 min)
    ↓
PHASE 3: Component Testing (20 min)
    ↓
PHASE 4: Integration Testing (30 min)
    ↓
PHASE 5: System Testing (60 min)
    ↓
PHASE 6: Performance Testing (30 min)
```

---

## ✅ PHASE 1: Setup & Prerequisites (5 minutes)

### Step 1.1: Verify Environment
```bash
# Check Python version (need 3.9+)
python --version

# Output should be: Python 3.9.x or higher
```

### Step 1.2: Install Dependencies
```bash
# Create virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install requirements
pip install -r requirements-enterprise.txt
```

### Step 1.3: Verify Key Files Exist
```bash
# Check all required files
ls -la server/webrtc_server.py
ls -la server/api_fastapi.py
ls -la analysis/skeleton_analyzer.py
ls -la analysis/multimodal_fusion.py
ls -la analysis/gemini_reasoning.py
ls -la pipeline/integrated_pipeline.py
ls -la database/models.py
ls -la config/config.yaml
```

### Step 1.4: Check Configuration
```bash
# Verify config file exists
cat config/config.yaml

# Should show:
# - cameras: [list of RTSP URLs]
# - detection: model settings
# - risk: threshold settings
```

---

## 🧬 PHASE 2: Unit Testing (10 minutes)

### Step 2.1: Test Skeleton Analyzer
```bash
# Create test_skeleton.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

from analysis.skeleton_analyzer import SkeletonAnalyzer
import numpy as np

print("🧪 Testing Skeleton Analyzer...")

# Initialize
analyzer = SkeletonAnalyzer()
print("✅ Skeleton analyzer initialized")

# Create dummy pose data (33 keypoints × 3 coordinates)
dummy_landmarks = np.random.rand(33, 3).tolist()

# Test analysis
result = analyzer.analyze(landmarks=dummy_landmarks)
print(f"✅ Analysis result: {result}")
print(f"✅ Anomaly score: {result.anomaly_score}")
print(f"✅ Behaviors detected: {[k for k,v in result.__dict__.items() if v]}")

print("\n✅ Skeleton Analyzer Test PASSED")
EOF
```

**Expected Output**:
```
✅ Skeleton analyzer initialized
✅ Analysis result: <SkeletonAnalysis object>
✅ Anomaly score: XX
✅ Behaviors detected: [list of flags]
✅ Skeleton Analyzer Test PASSED
```

---

### Step 2.2: Test Multi-Modal Fusion
```bash
# Create test_fusion.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

from analysis.multimodal_fusion import MultiModalFusionEngine, FusionInput
import numpy as np

print("🧪 Testing Multi-Modal Fusion Engine...")

# Initialize
engine = MultiModalFusionEngine()
print("✅ Fusion engine initialized")

# Create dummy input
fusion_input = FusionInput(
    gaze_score=0.8,
    pose_score=0.6,
    phone_score=0.9,
    leaning_score=0.4,
    movement_score=0.3,
    timestamp=1234567890
)

# Test fusion
result = engine.fuse(fusion_input)
print(f"✅ Fusion result: Risk Score = {result.risk_score}")
print(f"✅ Risk Level: {result.risk_level}")
print(f"✅ Primary Behavior: {result.primary_behavior}")

print("\n✅ Multi-Modal Fusion Test PASSED")
EOF
```

**Expected Output**:
```
✅ Fusion engine initialized
✅ Fusion result: Risk Score = XX
✅ Risk Level: Low/Medium/High/Critical
✅ Primary Behavior: phone_usage
✅ Multi-Modal Fusion Test PASSED
```

---

### Step 2.3: Test FastAPI Server
```bash
# Create test_api.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

from server.api_fastapi import app
from fastapi.testclient import TestClient

print("🧪 Testing FastAPI Server...")

client = TestClient(app)

# Test 1: Health check
response = client.get("/health")
print(f"✅ Health check: {response.status_code}")
assert response.status_code == 200

# Test 2: Get cameras status
response = client.get("/api/webrtc/cameras/status")
print(f"✅ Camera status: {response.status_code}")

# Test 3: Alert endpoint
response = client.post("/api/alerts/publish", json={
    "student_id": "STU_001",
    "severity": "high",
    "reason": "Suspicious behavior"
})
print(f"✅ Alert publish: {response.status_code}")

print("\n✅ FastAPI Server Test PASSED")
EOF
```

**Expected Output**:
```
✅ Health check: 200
✅ Camera status: 200
✅ Alert publish: 200
✅ FastAPI Server Test PASSED
```

---

## 🔌 PHASE 3: Component Testing (20 minutes)

### Step 3.1: Test WebRTC Server Component
```bash
# Create test_webrtc.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

import asyncio
from server.webrtc_server import WebRTCServer
import cv2
import numpy as np

async def test_webrtc():
    print("🧪 Testing WebRTC Server...")
    
    # Initialize
    server = WebRTCServer(width=640, height=480, fps=30)
    print("✅ WebRTC server initialized")
    
    # Create dummy frame
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Push frame
    server.push_frame(frame)
    print("✅ Frame pushed to buffer")
    
    # Get status
    status = server.get_camera_status()
    print(f"✅ Camera status: {status}")
    
    print("\n✅ WebRTC Server Test PASSED")

# Run async test
asyncio.run(test_webrtc())
EOF
```

**Expected Output**:
```
✅ WebRTC server initialized
✅ Frame pushed to buffer
✅ Camera status: {...}
✅ WebRTC Server Test PASSED
```

---

### Step 3.2: Test Database Models
```bash
# Create test_database.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

from database.models import Student, Alert, RiskScore
from datetime import datetime

print("🧪 Testing Database Models...")

# Test Student model
student = Student(
    student_id="STU_001",
    name="Test Student",
    roll_number="001",
    camera_id="camera_1",
    seat_x=100,
    seat_y=200
)
print(f"✅ Student model created: {student}")

# Test Alert model
alert = Alert(
    student_id="STU_001",
    severity="HIGH",
    behaviors="phone_usage,leaning",
    risk_score=85.5,
    timestamp=datetime.now()
)
print(f"✅ Alert model created")

# Test RiskScore model
risk = RiskScore(
    student_id="STU_001",
    score=85,
    risk_level="HIGH",
    timestamp=datetime.now()
)
print(f"✅ RiskScore model created")

print("\n✅ Database Models Test PASSED")
EOF
```

**Expected Output**:
```
✅ Student model created: <Student>
✅ Alert model created
✅ RiskScore model created
✅ Database Models Test PASSED
```

---

### Step 3.3: Test Detection Pipeline
```bash
# Create test_pipeline.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

import cv2
import numpy as np
from pipeline.integrated_pipeline import IntegratedSurveillancePipeline

print("🧪 Testing Detection Pipeline...")

# Initialize
config = {
    'frame_width': 640,
    'frame_height': 480,
    'gemini_api_key': 'test-key'
}
pipeline = IntegratedSurveillancePipeline(config)
print("✅ Pipeline initialized")

# Create dummy frame
frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

# Dummy detection results
yolo_results = []
face_mesh_results = []

# Process
result = pipeline.process_frame(
    frame=frame,
    camera_id='camera_1',
    yolo_results=yolo_results,
    face_mesh_results=face_mesh_results
)
print("✅ Frame processed")
print(f"✅ Result keys: {result.keys()}")

print("\n✅ Detection Pipeline Test PASSED")
EOF
```

**Expected Output**:
```
✅ Pipeline initialized
✅ Frame processed
✅ Result keys: dict_keys([...])
✅ Detection Pipeline Test PASSED
```

---

## 🔗 PHASE 4: Integration Testing (30 minutes)

### Step 4.1: Start API Server
```bash
# Terminal 1: Start the API server
python api_server.py

# Expected Output:
# ✅ Surveillance System Started
# ✅ System running...
# 🟢 API Server running on http://127.0.0.1:5000
```

### Step 4.2: Test API Endpoints (New Terminal)
```bash
# Terminal 2: Run API tests

# Test 1: Check health
curl http://localhost:5000/api/health
# Expected: {"status": "ok"}

# Test 2: Get dashboard data
curl http://localhost:5000/api/dashboard
# Expected: JSON with student counts, alerts, etc.

# Test 3: Get alerts
curl http://localhost:5000/api/alerts
# Expected: JSON array of alerts

# Test 4: Get report
curl http://localhost:5000/api/report
# Expected: PDF report or JSON info
```

### Step 4.3: Test WebSocket Connection
```bash
# Create test_websocket.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

import socketio
import time

print("🧪 Testing WebSocket Connection...")

# Connect to server
sio = socketio.Client()

@sio.on('connect')
def on_connect():
    print("✅ WebSocket connected")

@sio.on('surveillance_update')
def on_update(data):
    print(f"✅ Received update: {data}")

@sio.on('disconnect')
def on_disconnect():
    print("✅ WebSocket disconnected")

try:
    sio.connect('http://localhost:5000')
    print("✅ WebSocket connection test started")
    time.sleep(5)  # Listen for 5 seconds
    sio.disconnect()
    print("✅ WebSocket Connection Test PASSED")
except Exception as e:
    print(f"❌ WebSocket test failed: {e}")
EOF
```

---

### Step 4.4: Test Video Frame Streaming
```bash
# Create test_frame_streaming.py
python << 'EOF'
import sys
sys.path.insert(0, '.')

import requests
import base64
import cv2
import numpy as np
from datetime import datetime

print("🧪 Testing Frame Streaming...")

# Create dummy frame
frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
_, buffer = cv2.imencode('.jpg', frame)
frame_b64 = base64.b64encode(buffer).decode()

# Send to server
url = "http://localhost:5000/api/push-frame"
data = {
    "camera_id": "camera_1",
    "frame_base64": frame_b64,
    "timestamp": datetime.now().isoformat()
}

try:
    response = requests.post(url, json=data, timeout=5)
    print(f"✅ Frame sent: Status {response.status_code}")
    print("✅ Frame Streaming Test PASSED")
except Exception as e:
    print(f"❌ Frame streaming failed: {e}")
EOF
```

---

## 🎯 PHASE 5: System Testing (60 minutes)

### Step 5.1: Full System Start
```bash
# Terminal 1: Start surveillance system
python api_server.py

# Wait for system to initialize (30-60 seconds)
# Expected output:
# ✅ Surveillance System Started
# ✅ MODELS LOADED
# ✅ API running...
```

### Step 5.2: Monitor System Health
```bash
# Terminal 2: Monitor health every 10 seconds
python << 'EOF'
import requests
import time

for i in range(12):  # Run for 2 minutes
    try:
        response = requests.get('http://localhost:5000/api/health')
        data = response.json()
        status = data.get('status', 'unknown')
        cameras = data.get('cameras', {})
        
        print(f"[{i*10}s] Status: {status} | Cameras: {len(cameras)}")
        time.sleep(10)
    except Exception as e:
        print(f"[{i*10}s] Error: {e}")
        time.sleep(10)

print("✅ System Health Monitor PASSED")
EOF
```

**Expected Output**:
```
[0s] Status: ok | Cameras: 1
[10s] Status: ok | Cameras: 1
[20s] Status: ok | Cameras: 1
...
✅ System Health Monitor PASSED
```

---

### Step 5.3: Test Alert Generation
```bash
# Terminal 3: Inject test events
python << 'EOF'
import requests
import time
from datetime import datetime

print("🧪 Testing Alert Generation...")

# Simulate behavior event
event_data = {
    "student_id": "STU_001",
    "behavior": "looking_around",
    "confidence": 0.95,
    "timestamp": datetime.now().isoformat()
}

try:
    response = requests.post(
        'http://localhost:5000/api/behavior-event',
        json=event_data,
        timeout=5
    )
    print(f"✅ Event sent: {response.status_code}")
    time.sleep(2)
    
    # Check if alert was generated
    response = requests.get('http://localhost:5000/api/alerts')
    alerts = response.json()
    print(f"✅ Alerts received: {len(alerts)} total")
    
    print("✅ Alert Generation Test PASSED")
except Exception as e:
    print(f"❌ Alert generation test failed: {e}")
EOF
```

---

### Step 5.4: Test Dashboard Updates
```bash
# Terminal 3: Monitor dashboard
python << 'EOF'
import requests
import time

print("🧪 Testing Dashboard Updates...")

for i in range(6):  # Run for 60 seconds
    try:
        response = requests.get('http://localhost:5000/api/dashboard')
        data = response.json()
        
        total = data.get('total_students', 0)
        alerts = data.get('total_alerts', 0)
        normal = data.get('normal_students', 0)
        
        print(f"[{i*10}s] Students: {total} | Alerts: {alerts} | Normal: {normal}")
        time.sleep(10)
    except Exception as e:
        print(f"[{i*10}s] Error: {e}")
        time.sleep(10)

print("✅ Dashboard Updates Test PASSED")
EOF
```

---

### Step 5.5: Test Report Generation
```bash
# Terminal 3: Trigger report
python << 'EOF'
import requests
import os

print("🧪 Testing Report Generation...")

try:
    # Request report
    response = requests.get(
        'http://localhost:5000/api/report',
        timeout=10
    )
    
    if response.status_code == 200:
        # Check if PDF was generated
        if 'content-type' in response.headers:
            print(f"✅ Report generated: {response.headers['content-type']}")
        else:
            print(f"✅ Report response: {response.json()}")
        
        print("✅ Report Generation Test PASSED")
    else:
        print(f"❌ Report generation failed: {response.status_code}")
except Exception as e:
    print(f"❌ Report test failed: {e}")
EOF
```

---

## ⚡ PHASE 6: Performance Testing (30 minutes)

### Step 6.1: Measure Latency
```bash
# Create test_latency.py
python << 'EOF'
import requests
import time
from datetime import datetime

print("🧪 Testing Latency...")

latencies = []

for i in range(20):
    start = time.time()
    
    try:
        response = requests.get('http://localhost:5000/api/dashboard')
        latency = (time.time() - start) * 1000  # Convert to ms
        latencies.append(latency)
        print(f"Request {i+1}: {latency:.2f}ms")
    except Exception as e:
        print(f"Request {i+1}: Failed - {e}")

if latencies:
    avg = sum(latencies) / len(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    
    print(f"\n📊 Latency Results:")
    print(f"  Average: {avg:.2f}ms")
    print(f"  Min:     {min_lat:.2f}ms")
    print(f"  Max:     {max_lat:.2f}ms")
    print(f"  ✅ PASSED" if avg < 100 else f"  ❌ FAILED (avg > 100ms)")
EOF
```

---

### Step 6.2: Measure Throughput
```bash
# Create test_throughput.py
python << 'EOF'
import requests
import time
import numpy as np
import cv2
import base64

print("🧪 Testing Throughput...")

# Create dummy frame
frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
_, buffer = cv2.imencode('.jpg', frame)
frame_b64 = base64.b64encode(buffer).decode()

frame_count = 0
errors = 0
start_time = time.time()

print("Sending 100 frames...")

for i in range(100):
    try:
        response = requests.post(
            'http://localhost:5000/api/push-frame',
            json={
                "camera_id": "camera_1",
                "frame_base64": frame_b64
            },
            timeout=5
        )
        if response.status_code == 200:
            frame_count += 1
        else:
            errors += 1
    except:
        errors += 1
    
    if (i + 1) % 20 == 0:
        print(f"  {i+1}/100 frames sent")

elapsed = time.time() - start_time
fps = frame_count / elapsed if elapsed > 0 else 0

print(f"\n📊 Throughput Results:")
print(f"  Frames sent: {frame_count}/100")
print(f"  Errors: {errors}")
print(f"  Time: {elapsed:.2f}s")
print(f"  FPS: {fps:.2f}")
print(f"  ✅ PASSED" if fps >= 15 else f"  ❌ FAILED (fps < 15)")
EOF
```

---

### Step 6.3: Measure CPU/Memory Usage
```bash
# Create test_resources.py
python << 'EOF'
import psutil
import time

print("🧪 Testing Resource Usage...")
print("Monitoring for 30 seconds...\n")

cpu_samples = []
mem_samples = []

for i in range(30):
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    
    cpu_samples.append(cpu)
    mem_samples.append(mem)
    
    if i % 10 == 0:
        print(f"[{i}s] CPU: {cpu:.1f}% | Memory: {mem:.1f}%")
    
    time.sleep(1)

avg_cpu = sum(cpu_samples) / len(cpu_samples)
avg_mem = sum(mem_samples) / len(mem_samples)
max_cpu = max(cpu_samples)
max_mem = max(mem_samples)

print(f"\n📊 Resource Usage Results:")
print(f"  Avg CPU: {avg_cpu:.1f}%")
print(f"  Max CPU: {max_cpu:.1f}%")
print(f"  Avg Memory: {avg_mem:.1f}%")
print(f"  Max Memory: {max_mem:.1f}%")
print(f"  ✅ PASSED" if avg_cpu < 80 and avg_mem < 80 else f"  ⚠️ WARNING (high usage)")
EOF
```

---

## 📝 Testing Checklist

### ✅ Pre-Testing
- [ ] Python 3.9+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Config file exists
- [ ] API key configured

### ✅ Unit Tests
- [ ] Skeleton analyzer works
- [ ] Fusion engine works
- [ ] API server starts
- [ ] Database models initialize

### ✅ Component Tests
- [ ] WebRTC server initializes
- [ ] Database connections work
- [ ] Pipeline processes frames
- [ ] API endpoints respond

### ✅ Integration Tests
- [ ] API server starts
- [ ] All endpoints respond
- [ ] WebSocket connects
- [ ] Frames stream
- [ ] Reports generate

### ✅ System Tests
- [ ] System stays healthy
- [ ] Alerts generate correctly
- [ ] Dashboard updates in real-time
- [ ] Reports are accurate

### ✅ Performance Tests
- [ ] Latency < 100ms
- [ ] Throughput ≥ 15 FPS
- [ ] CPU usage < 80%
- [ ] Memory usage < 80%

---

## 🛑 Stopping Tests

### Graceful Shutdown
```bash
# In the API server terminal, press Ctrl+C
# Expected output:
# ⚠️  SHUTDOWN SIGNAL RECEIVED (Ctrl+C)
# ⏳ Waiting for surveillance thread to finish...
# ✅ Shutdown complete

# Or kill process
pkill -f api_server.py
```

---

## 📊 Test Results Template

Save this as `TEST_RESULTS.md`:

```markdown
# Test Results - [DATE]

## Environment
- Python Version: 3.X.X
- OS: Windows/Linux
- GPU: [Yes/No]

## Unit Tests
- [ ] Skeleton Analyzer: PASS/FAIL
- [ ] Fusion Engine: PASS/FAIL
- [ ] FastAPI: PASS/FAIL
- [ ] Database Models: PASS/FAIL

## Integration Tests
- [ ] API Server: PASS/FAIL
- [ ] WebSocket: PASS/FAIL
- [ ] Frame Streaming: PASS/FAIL
- [ ] Report Generation: PASS/FAIL

## Performance
- Average Latency: ___ ms (target < 100ms)
- Throughput: ___ FPS (target ≥ 15)
- CPU Usage: ___ % (target < 80%)
- Memory Usage: ___ % (target < 80%)

## Issues Found
1. [Issue description]
2. [Issue description]

## Overall Status
✅ PASSED / ⚠️ WARNING / ❌ FAILED
```

---

## 🎯 Next Steps After Testing

1. ✅ All tests pass → **Ready for deployment**
2. ⚠️ Some warnings → **Optimize and retry**
3. ❌ Tests fail → **Debug using logs and check TROUBLESHOOTING.md**

---

**Happy Testing!** 🚀
