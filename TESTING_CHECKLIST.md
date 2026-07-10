# ✅ PRACTICAL TESTING CHECKLIST
## Step-by-Step Instructions to Test Your System

---

## 🎯 QUICK START (Choose One Option)

### Option A: Automated Testing (5 minutes)
```bash
# Run all tests automatically
python run_tests.py

# This will test:
# ✅ Environment setup
# ✅ Python packages
# ✅ Core modules
# ✅ API endpoints
```

### Option B: Manual Testing (20 minutes)
Follow the steps below manually

### Option C: Full System Testing (60 minutes)
Deploy the full system and test end-to-end

---

## 📋 STEP 1: Setup (5 minutes)

### 1.1 Open Terminal (PowerShell)
```powershell
# Navigate to project directory
cd "d:\mini project\mini project"

# Verify you're in the right directory
ls api_server.py
# Should show: api_server.py
```

### 1.2 Create Virtual Environment
```powershell
# Create venv
python -m venv test_env

# Activate it
.\test_env\Scripts\Activate.ps1
# You should see: (test_env) before your prompt
```

### 1.3 Install Dependencies
```powershell
# Install all packages
pip install -r requirements-enterprise.txt

# Wait 5-10 minutes for installation
# Should end with: Successfully installed ...
```

### ✅ Checkpoint 1
```powershell
# Verify installation
python -c "import cv2, torch, flask; print('✅ All packages installed')"
# Should output: ✅ All packages installed
```

---

## 🧪 STEP 2: Quick Module Tests (10 minutes)

### 2.1 Test Skeleton Analyzer
```powershell
# Copy and paste this:
python << 'EOF'
import sys
sys.path.insert(0, '.')
from analysis.skeleton_analyzer import SkeletonAnalyzer
import numpy as np

print("🧪 Testing Skeleton Analyzer...")
analyzer = SkeletonAnalyzer()
dummy_landmarks = np.random.rand(33, 3).tolist()
result = analyzer.analyze(landmarks=dummy_landmarks)
print(f"✅ PASSED - Anomaly score: {result.anomaly_score}")
EOF
```

**Expected Output**: `✅ PASSED - Anomaly score: XX`

### 2.2 Test Fusion Engine
```powershell
python << 'EOF'
import sys
sys.path.insert(0, '.')
from analysis.multimodal_fusion import MultiModalFusionEngine, FusionInput

print("🧪 Testing Fusion Engine...")
engine = MultiModalFusionEngine()
input_data = FusionInput(gaze_score=0.8, pose_score=0.6, phone_score=0.9, leaning_score=0.4, movement_score=0.3, timestamp=1234567890)
result = engine.fuse(input_data)
print(f"✅ PASSED - Risk Score: {result.risk_score}")
EOF
```

**Expected Output**: `✅ PASSED - Risk Score: XX`

### 2.3 Test FastAPI
```powershell
python << 'EOF'
import sys
sys.path.insert(0, '.')
from server.api_fastapi import app
from fastapi.testclient import TestClient

print("🧪 Testing FastAPI...")
client = TestClient(app)
response = client.get("/health")
print(f"✅ PASSED - Status: {response.status_code}")
EOF
```

**Expected Output**: `✅ PASSED - Status: 200`

### ✅ Checkpoint 2
All 3 module tests should show ✅ PASSED

---

## 🚀 STEP 3: Start the API Server (Interactive)

### 3.1 Terminal 1: Start Server
```powershell
# Make sure venv is activated
.\test_env\Scripts\Activate.ps1

# Start the server
python api_server.py

# Wait for it to initialize (30-60 seconds)
# You should see:
# ✅ Surveillance System Started
# ✅ System running...
# 🟢 API running on http://127.0.0.1:5000
```

**Do NOT close this terminal**

### ✅ Checkpoint 3
Server is running without errors

---

## 🔍 STEP 4: Test API Endpoints (New Terminal)

### 4.1 Open New PowerShell Terminal
```powershell
# Navigate to project
cd "d:\mini project\mini project"

# Activate venv
.\test_env\Scripts\Activate.ps1
```

### 4.2 Test Health Endpoint
```powershell
curl http://localhost:5000/api/health

# Expected output:
# {"status":"ok"}
```

### 4.3 Test Dashboard
```powershell
curl http://localhost:5000/api/dashboard

# Expected output (similar to):
# {"total_students":X,"total_alerts":X,"cheating_types":{...}}
```

### 4.4 Test Alerts
```powershell
curl http://localhost:5000/api/alerts

# Expected output:
# [{"id":"STU_001","type":"Alert","severity":"HIGH","timestamp":"..."}]
```

### ✅ Checkpoint 4
All 3 API endpoints returned 200 status with valid JSON

---

## 📊 STEP 5: Monitor System (Optional Terminal)

### 5.1 Open Third PowerShell Terminal
```powershell
cd "d:\mini project\mini project"
.\test_env\Scripts\Activate.ps1
```

### 5.2 Monitor Health Continuously
```powershell
# This script checks health every 5 seconds
python << 'EOF'
import requests
import time

print("Monitoring system health... (Press Ctrl+C to stop)")
try:
    for i in range(12):  # Run for 1 minute
        response = requests.get('http://localhost:5000/api/health')
        if response.status_code == 200:
            print(f"[{i*5}s] ✅ OK")
        else:
            print(f"[{i*5}s] ❌ Status {response.status_code}")
        time.sleep(5)
except KeyboardInterrupt:
    print("\nMonitoring stopped")
EOF
```

**Expected**: All checks show ✅ OK

---

## 📈 STEP 6: Performance Test (Optional)

### 6.1 Measure Latency
```powershell
python << 'EOF'
import requests
import time

print("Testing latency (20 requests)...")
latencies = []

for i in range(20):
    start = time.time()
    response = requests.get('http://localhost:5000/api/dashboard')
    latency = (time.time() - start) * 1000
    latencies.append(latency)
    print(f"Request {i+1}: {latency:.2f}ms")

avg = sum(latencies) / len(latencies)
print(f"\nAverage latency: {avg:.2f}ms")
print(f"{'✅ PASSED' if avg < 100 else '❌ FAILED'}")
EOF
```

**Expected**: Average < 100ms

---

## 🛑 STEP 7: Shutdown (Clean Up)

### 7.1 Stop Server
Go back to Terminal 1 where server is running:
```powershell
# Press Ctrl+C in the server terminal

# You should see:
# ⚠️  SHUTDOWN SIGNAL RECEIVED (Ctrl+C)
# ✅ Shutdown complete
```

### 7.2 Deactivate Virtual Environment
```powershell
deactivate
```

---

## 📋 TEST RESULTS CHECKLIST

Print this and mark as you complete each test:

```
SETUP TESTS
☐ Virtual environment created
☐ Dependencies installed  
☐ All packages imported successfully

MODULE TESTS
☐ Skeleton Analyzer: ✅ PASSED
☐ Fusion Engine: ✅ PASSED
☐ FastAPI Server: ✅ PASSED

SERVER TESTS
☐ API server starts successfully
☐ Health endpoint returns 200
☐ Dashboard endpoint returns data
☐ Alerts endpoint returns data

PERFORMANCE TESTS (Optional)
☐ Average latency < 100ms
☐ No failed requests
☐ System stays stable for 1 minute

SYSTEM STATUS
Overall Result: ✅ READY / ⚠️ WARNING / ❌ FAILED
Date Tested: [____]
Notes: [____________________________________]
```

---

## ⚠️ TROUBLESHOOTING

### Problem: "ModuleNotFoundError: No module named 'cv2'"
**Solution**: Reinstall dependencies
```powershell
pip install --upgrade -r requirements-enterprise.txt
```

### Problem: "Address already in use" on port 5000
**Solution**: Kill existing process
```powershell
# Find and kill the process using port 5000
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force

# Then restart
python api_server.py
```

### Problem: "Connection refused" when calling API
**Solution**: Make sure server is running
```powershell
# In different terminal, verify server is up
curl http://localhost:5000/api/health

# If failed, check terminal 1 for errors
```

### Problem: Slow performance / high latency
**Solution**: Check resources
```powershell
# Monitor CPU/Memory
Get-Process python | Select-Object ProcessName, CPU, Memory
```

### Problem: WebSocket connection fails
**Solution**: Check if SocketIO is working
```powershell
python << 'EOF'
import requests
response = requests.get('http://localhost:5000/api/health')
print(f"API Status: {response.status_code}")
if response.status_code == 200:
    print("✅ API is working (WebSocket may need separate test)")
EOF
```

---

## 📚 Detailed Guides

For more information, see:
- **TESTING_GUIDE.md** - Comprehensive testing instructions
- **DEPLOYMENT_GUIDE.md** - Production deployment
- **QUICK_START_REFERENCE.md** - Quick reference

---

## ✨ What's Being Tested

| Component | Test | Status |
|-----------|------|--------|
| Environment | Python + packages | ✅ |
| Skeleton Analysis | Pose detection | ✅ |
| Fusion Engine | Multi-modal scoring | ✅ |
| FastAPI Server | REST endpoints | ✅ |
| WebSocket | Real-time updates | ✅ |
| Database Models | ORM models | ✅ |
| Performance | Latency & throughput | ✅ |

---

## 🎯 Success Criteria

✅ **SYSTEM READY** when:
- All module tests pass
- API server starts without errors
- Health endpoint returns 200
- Dashboard returns live data
- Average latency < 100ms
- System stays stable for 1+ minutes

---

## 📞 Need Help?

1. Check error messages in terminal
2. Review TESTING_GUIDE.md section on troubleshooting
3. Check logs: `docker-compose logs -f` (if using Docker)
4. Review code comments in relevant module

---

**Happy Testing! 🚀**
