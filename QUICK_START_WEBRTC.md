# ⚡ Quick Start - Camera/WebRTC Debug Fixes

## What Was Wrong
Your camera pipeline had **3 critical broken links**:

1. ❌ **Camera frames NEVER reached WebRTC** - CameraManager wasn't connected
2. ❌ **Frontend had NO WebRTC code** - Can't display video without it  
3. ❌ **No logging** - Couldn't see where pipeline broke

## What's Fixed
✅ Frames now flow: Camera → OpenCV → WebRTC → Browser  
✅ WebRTC React component created with full debugging  
✅ Comprehensive logging at every stage  
✅ Dashboard fetches and displays cameras with live video  

## Start Here

### 1️⃣ Backend
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Look for these logs**:
```
✅ Camera Manager initialized with WebRTC frame sink
✅ Auto-connected to camera: webcam_0
📹 webcam_0: frame #30 (shape: (720, 1280, 3))
📨 Frame pushed to WebRTC: webcam_0
```

### 2️⃣ Verify Connection
Open another terminal:
```bash
python verify_webrtc.py
```

**Expected output**:
```
✅ Backend is running
✅ Found 1 camera(s)
✅ Camera webcam_0 is ONLINE
✅ WebRTC server is running with 1 camera(s)
✅ Frame push successful
✅ CORS is enabled
```

### 3️⃣ Frontend
```bash
cd frontend
npm run dev
```

Navigate to: `http://localhost:3000/dashboard`

**Expected**:
- ✅ Live video streaming in camera grid
- ✅ 🟢 Live indicator and FPS counter
- ✅ Real-time video updates

### 4️⃣ Verify in Browser Console (F12)
```
🎥 Setting up WebRTC for camera: webcam_0
📡 Creating WebRTC offer for webcam_0
✅ Answer received for webcam_0
📹 Track received: video
✅ WebRTC connected for webcam_0
```

## If Video Still Doesn't Show

### Check 1: Is backend streaming?
```bash
# Backend logs should show:
📨 Frame pushed to WebRTC: webcam_0  # Every 30 frames minimum
```

### Check 2: Does browser see frames?
**Firefox/Chrome DevTools Console (F12)**:
- ❌ Red: `❌ Connection error` → Backend not running
- ❌ Red: `CORS error` → Browser can't reach backend
- ✅ Green: `✅ WebRTC connected` → Video should show

### Check 3: Video element rendering?
```javascript
// In browser console (F12 → Console)
document.querySelector('video')  // Should exist
document.querySelector('video').srcObject  // Should have MediaStream
```

### Check 4: Camera permissions?
- ✅ Browser should ask for camera access
- ✅ Click "Allow"
- If blocked, check browser settings: Settings → Privacy → Camera

## Files Changed

| File | Status | What |
|------|--------|------|
| `backend/main.py` | ✅ Updated | Frame sink → WebRTC |
| `backend/api/websocket.py` | ✅ Updated | Logging + camera_id |
| `camera/camera_stream.py` | ✅ Updated | Capture logging |
| `frontend/components/WebRTCVideo.tsx` | ✅ NEW | WebRTC client |
| `frontend/components/CameraGrid.tsx` | ✅ Updated | Use WebRTCVideo |
| `frontend/pages/dashboard.tsx` | ✅ Updated | Fetch + render |

## Test Different Camera Types

### Laptop Webcam (Default)
✅ Automatic - should work out of the box

### USB Webcam  
Edit `camera/camera_config.yaml`:
```yaml
explicit_sources:
  - source: 1  # USB camera
    name: "USB Webcam"
```

### DroidCam
```yaml
explicit_sources:
  - source: "http://192.168.1.100:4747/video"
    name: "DroidCam"
```

### RTSP Camera
```yaml
explicit_sources:
  - source: "rtsp://192.168.1.50:554/stream"
    name: "IP Camera"
```

Then restart backend.

## Performance Tips

### If Video is Choppy
1. Check FPS in browser (should show 30)
2. Reduce resolution in `camera/camera_config.yaml`:
   ```yaml
   width: 640   # Instead of 1280
   height: 480  # Instead of 720
   ```
3. Lower bitrate in `backend/main.py` WebRTC config

### If CPU Usage is High
1. Reduce FPS: `target_fps: 15` in camera config
2. Reduce resolution
3. Enable hardware acceleration (GPU encoding)

## Production Settings

```python
# backend/main.py startup_event
config = {
    "webrtc": {
        "bitrate": 1500000,      # 1.5 Mbps for better compression
        "fps": 15,               # Lower FPS for lower bandwidth
    }
}
```

## Success Criteria ✅

Your pipeline is working when:
1. ✅ Backend logs show: `📨 Frame pushed to WebRTC: {camera_id}`
2. ✅ Browser console shows: `✅ WebRTC connected for {camera_id}`
3. ✅ Dashboard displays video with FPS counter
4. ✅ Video is live and updating (not frozen)
5. ✅ Multiple cameras work simultaneously

## Debug Checklist

- [ ] Backend running on port 8000?
- [ ] Logs show "Frame pushed to WebRTC"?
- [ ] Frontend running on port 3000?
- [ ] Browser shows WebRTC video?
- [ ] No red errors in browser console?
- [ ] Camera permissions granted?
- [ ] FPS counter displaying?

## Next Steps

Once camera is streaming:
1. Integrate YOLO detection pipeline
2. Add face/skeleton analysis agents
3. Set up alert system
4. Add multi-camera synchronization
5. Deploy to production

All camera pipeline infrastructure is now in place! 🚀
