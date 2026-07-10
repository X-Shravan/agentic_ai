# 🚨 TROUBLESHOOTING GUIDE

## Issue: Bounding Boxes Not Visible

### Problem Symptoms:
- Boxes appear for a frame then disappear
- Only labels visible, no rectangles
- Frame looks like original without drawings

### Causes & Fixes:

**1. Wrong Frame Used for Display**
```python
# ❌ WRONG:
img = draw_detections(data["frame"], detections)
cv2.imshow("Window", data["frame"])  # Shows original!

# ✅ CORRECT:
display_frame = data["frame"].copy()
display_frame = draw_detections(display_frame, detections)
cv2.imshow("Window", display_frame)
```

**2. Frame Not Updated in Loop**
```python
# ❌ WRONG:
img = detection_agent.draw_detections(img, data["detections"])
# ... then using 'img' from previous iteration

# ✅ CORRECT:
display_frame = data["frame"].copy()  # Fresh copy each iteration
display_frame = detection_agent.draw_detections(display_frame, data["detections"])
```

**3. Multiple Frames in Pipeline**
```python
# ✅ FIX: Use single frame throughout
frame = cap.read()          # 1 frame
results = model(frame)      # same frame
draw_boxes(frame, results)  # same frame
cv2.imshow("Window", frame) # same frame
```

**Verification:**
```bash
python verify_system_fixes.py
# Look for: ✅ Frame Pipeline
```

---

## Issue: Labels Show "Alert ????"

### Problem Symptoms:
- Labels display "Alert ????" instead of behavior type
- Severity always shows "MEDIUM"
- No emoji indicators

### Causes & Fixes:

**1. BehaviorEvent Missing Situation Field**
```python
# ❌ WRONG:
event = BehaviorEvent(
    event_type="Alert 🚨",
    confidence=0.85,
    timestamp=time.time()
)

# ✅ CORRECT:
event = BehaviorEvent(
    event_type="Alert 🚨",
    confidence=0.85,
    timestamp=time.time(),
    situation="Using Mobile 🚨"  # ← ADD THIS
)
```

**2. Risk Scoring Missing Situation**
```python
# ❌ WRONG:
results[tid] = {
    "score": score,
    "label": label,
    "events": [event_type]
}

# ✅ CORRECT:
results[tid] = {
    "score": score,
    "label": label,
    "events": [event_type],
    "situation": events[0].situation  # ← ADD THIS
}
```

**3. Status Not Set in determine_status()**
```python
# ❌ WRONG:
return ("Alert ????", 0.85, True)  # Status not set

# ✅ CORRECT:
return ("Using Mobile 🚨", 0.85, True)  # Clear status with emoji
```

**Debug Check:**
```python
# Add to behavior_analysis_agent.py
print(f"Status for ID {tid}: {status}")
print(f"Event situation: {event.situation}")
```

---

## Issue: Evidence Images Not Saving

### Problem Symptoms:
- `evidence/` folder empty after alerts
- No image files created
- Events logged but no evidence

### Causes & Fixes:

**1. Saving Every Frame (Too Many Files)**
```python
# ❌ WRONG:
if "Alert" in label:
    save_screenshot(frame, tid, score)  # Saves every frame!

# ✅ CORRECT:
if tid in prev_status and prev_status[tid] != current_status:
    if ("🚨" in current_status) and (prev_status[tid] == "Normal"):
        save_screenshot(frame, tid, score)  # Saves on transition only
```

**2. Saving Original Frame (Without Drawings)**
```python
# ❌ WRONG:
cv2.imwrite("evidence/..." , original_frame)

# ✅ CORRECT:
cv2.imwrite("evidence/..." , display_frame)  # With boxes/labels
```

**3. No Transition Detection**
```python
# ❌ WRONG:
if status != "Normal":
    save_screenshot(frame, tid, score)

# ✅ CORRECT:
if tid not in prev_status:
    prev_status[tid] = "Normal"

current_status = situation
if prev_status[tid] != current_status:
    if "🚨" in current_status:
        save_screenshot(frame, tid, score)

prev_status[tid] = current_status
```

**Ensure Directory Exists:**
```python
import os
os.makedirs("evidence", exist_ok=True)
```

**Debug Check:**
```bash
# Verify directory is writable
python -c "import cv2, numpy as np; cv2.imwrite('evidence/test.jpg', np.zeros((100,100,3), dtype=np.uint8))"
# If works: ✅
# If error: Check permissions
```

---

## Issue: Detection Works but UI Not Updating

### Problem Symptoms:
- Scores print correctly but not displayed
- Boxes drawn off-screen or invisible
- Dashboard shows old data

### Causes & Fixes:

**1. Wrong Object Passed to Display**
```python
# ❌ WRONG:
for cam_id, data in results.items():
    img = detection_agent.draw_detections(data["frame"], data["detections"])
    cv2.imshow("Window", data["frame"])  # Shows ORIGINAL, not IMG!

# ✅ CORRECT:
for cam_id, data in results.items():
    display_frame = data["frame"].copy()
    display_frame = detection_agent.draw_detections(display_frame, data["detections"])
    cv2.imshow("Window", display_frame)  # Shows MODIFIED frame
```

**2. Results Not Updated with Processed Frame**
```python
# ❌ WRONG:
cv2.imshow("...", display_frame)
# Process frame is displayed but not returned

# ✅ CORRECT:
cv2.imshow("...", display_frame)
results[cam_id]["frame"] = display_frame  # ← RETURN IT
```

**3. API Server Using Old Frame**
```python
# In surveillance_loop():
# ❌ WRONG:
frame = results[cam_id]["frame"]  # Original
socketio.emit('frame': base64_encode(frame))

# ✅ CORRECT:
frame = results[cam_id]["frame"]  # Processed (contains boxes)
socketio.emit('frame': base64_encode(frame))
```

---

## Issue: Sharing Detection Not Working

### Problem Symptoms:
- Multiple people never marked as "Sharing Answers 🤝"
- Sharing counter never increments
- Works for other behaviors but not sharing

### Causes & Fixes:

**1. Head Positions Not Tracked**
```python
# ✅ ADD to analyze() method:
self.head_positions.clear()  # Clear old data

for track in tracks:
    tid = track.track_id
    x1, y1, x2, y2 = map(int, track.bbox)
    
    # Calculate head center
    head_x = (x1 + x2) // 2
    head_y = y1 + (y2 - y1) // 4
    
    # ✅ STORE for sharing detection
    self.head_positions[tid] = (head_x, head_y, yaw)
```

**2. Sharing Detection Not Called**
```python
# ✅ ADD to analyze() method (second pass):
sharing_flags = self.detect_sharing(tracks)

for tid in results:
    if sharing_flags.get(tid, False):
        status = "Sharing Answers 🤝"
        # Update event
```

**3. Distance Threshold Too Small**
```python
# Current: 150 pixels (adjust if needed)
self.SHARING_DISTANCE_THRESHOLD = 150

# For different camera angles:
# Top-down: 200
# Side: 150
# Front: 100
```

**4. Yaw Threshold Too Strict**
```python
# Current: 25 degrees (opposite direction)
self.SHARING_YAW_THRESHOLD = 25

# Stricter: 35 (must face completely opposite)
# Looser: 15 (closer facing needed)
```

**Debug Check:**
```python
# Add to detect_sharing():
print(f"Distance ID{tid1}-{tid2}: {distance}")
print(f"Yaw diff: {yaw_diff}")
print(f"Sharing: {sharing_flags}")
```

---

## Issue: Frame Rate (FPS) Very Low

### Problem Symptoms:
- FPS < 5 (should be 20-30)
- System lag or jerky display
- High CPU/GPU usage

### Causes & Fixes:

**1. YOLO Running Every Frame**
```python
# ✅ Already in code:
if self.frame_count % self.YOLO_INTERVAL == 0:
    detections = self.detection_agent.detect(frame)
else:
    detections = self.last_detections.get(cam_id, [])
```

**2. MediaPipe Processing Too Much**
```python
# Optimize ROI size
roi_resized = cv2.resize(roi, (320, 240))  # Smaller = faster
# Try (224, 224) or (160, 120) if too slow
```

**3. Too Many Display Operations**
```python
# ✅ Minimize cv2.putText calls
# ✅ Use cv2.rectangle (fast)
# ⚠️ Avoid cv2.polylines (slow)
```

**4. GPU Not Being Used**
```bash
# Check if using GPU
python -c "import torch; print(torch.cuda.is_available())"
# If False: Install CUDA version of PyTorch
```

**Profiling:**
```python
import time
start = time.time()
# ... code ...
elapsed = time.time() - start
print(f"Time: {elapsed*1000:.2f}ms")
```

---

## Issue: Dashboard Not Receiving Data

### Problem Symptoms:
- Dashboard blank or no updates
- API returns empty arrays
- WebSocket connection but no data

### Causes & Fixes:

**1. Processed Frame Not in Results**
```python
# ✅ In main.py run() method:
results[cam_id]["frame"] = display_frame  # Must return this

# In api_server.py:
frame = data.get("frame")  # Will be processed frame with boxes
```

**2. Scores Dictionary Empty**
```python
# Check that scores are populated:
# ✅ In process_frame():
scores = risk_agent.calculate_scores(detections, behavior, associations)
# results[cam_id]["scores"] = scores

# Debug:
print(f"Scores: {scores}")  # Should have data
```

**3. Socket Emit Not Sending**
```python
# ✅ Must be inside app context:
with app.app_context():
    socketio.emit('surveillance_update', {...})

# ✅ Check namespace:
@socketio.on('surveillance_update')
def handle_update(data):
    print(f"Received: {data}")
```

**4. CORS Issues**
```python
# ✅ In api_server.py:
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")
```

---

## Quick Debug Commands

```bash
# Run verification
python verify_system_fixes.py

# Test frame pipeline
python -c "
import cv2
import numpy as np

frame = np.zeros((480, 640, 3), dtype=np.uint8)
display = frame.copy()
cv2.rectangle(display, (100, 100), (200, 200), (0, 0, 255), 3)

print('Original frame modified:', np.array_equal(frame, display))
print('✅ Frames are separate' if not np.array_equal(frame, display) else '❌ Frames are same')
"

# Check evidence directory
ls -la evidence/

# Monitor system
python -c "
import psutil
print(f'CPU: {psutil.cpu_percent()}%')
print(f'Memory: {psutil.virtual_memory().percent}%')
print(f'GPU available: {False}')  # Check with torch.cuda.is_available()
"

# Test API server
curl http://localhost:5000/api/health
```

---

## Contact Support

If issues persist:

1. Run: `python verify_system_fixes.py`
2. Share output
3. Check: `SYSTEM_FIXES_COMPLETE.md`
4. Review console output for errors
5. Check evidence/ folder for saved images

---

**Last Updated:** April 2026
**Version:** 2.0 (Complete Fixes)
**Status:** ✅ Production Ready
