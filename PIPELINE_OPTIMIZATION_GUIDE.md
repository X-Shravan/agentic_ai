# Pipeline Optimization & Behavior Detection Fix

## ✅ FIXES APPLIED

### 1. Simplified Behavior Analysis
- Removed overly complex time-based checks
- Removed stability checks that were blocking detections
- Used exact thresholds from specification
- Direct counter logic with gradual decay

**File**: `agents/behavior_analysis_agent.py`

Thresholds (SPECIFICATION):
```
Looking Around: if abs(yaw) > 20 and count >= 3
Looking to Copy: if pitch > 15 AND abs(yaw) > 10 and count >= 3
Leaning: if shoulder_tilt > 10 and frames >= 15
Mobile: confidence > 0.6, area > 7000, aspect 1.4-2.5
```

### 2. Fixed Counter Decay Logic
- All counters now use gradual decay: `count = max(count - 1, 0)`
- NO instant resets
- Counters decrease by 1 each frame when condition not met

### 3. Priority System (EXACT SPEC)
```
if mobile: Using Mobile 🚨
elif sharing: Sharing Answers 🤝
elif copy_count >= 3: Looking to Copy 🚨
elif look_count >= 3: Looking Around 👀
elif lean_frames >= 15: Leaning ↘️
else: Normal
```

### 4. Fixed Detections Passing
**File**: `main.py`

Changed:
```python
# BEFORE
behavior = behavior_agent.analyze(frame, student_tracks)

# AFTER
behavior = behavior_agent.analyze(frame, student_tracks, detections)
```

Now behavior analysis receives YOLO detections to check for mobile/book.

### 5. Fixed Shoulder Tilt Scale
Changed from raw value (0-1) to normalized scale (0-100):
```python
return abs(left_shoulder_y - right_shoulder_y) * 100
```

---

## 🧪 TESTING PROCEDURE

### Test 1: Demo Mode with Debug Output
```bash
cd d:\mini project\mini project
python main.py --demo
```

Expected output:
```
[YOLO] Frame 0: X detections
[TRACKING] X total tracks, Y students
ID 1 | Looking Around 👀 | 45%
ID 2 | Using Mobile 🚨 | 92%
ID 3 | Leaning ↘️ | 35%
ID 4 | Normal | 0%
```

### Test 2: Simple Behavior Analysis Only
```bash
python -c "
from agents.simple_behavior_analysis import SimpleBehaviorAnalysis
ba = SimpleBehaviorAnalysis()
print('✅ Simple behavior analysis initialized successfully')
"
```

### Test 3: Dashboard with Processed Frames
```bash
# Terminal 1
python api_server.py

# Terminal 2
cd dashboard/react-dashboard
npm start
```

Expected:
- Live camera feed with bounding boxes
- Colors: Red 🚨 (alerts), Orange 👀↘️ (suspicious), Green (normal)
- ID labels visible
- Smooth 30+ FPS

### Test 4: Evidence Image Verification
1. Trigger alert (point phone at camera)
2. Check `evidence/` folder
3. Open image - should show:
   - Bounding box with ID
   - Status text (e.g., "Using Mobile 🚨")
   - Metadata overlay (ID, score, time)

---

## 🔍 DEBUGGING TIPS

### If No Behavior Detection:
1. Check console for `[YOLO]` and `[TRACKING]` lines
2. Verify: `python -c "import mediapipe; print('✅ MediaPipe OK')"`
3. Check thresholds in `behavior_analysis_agent.py` line 33-50
4. Print debug: Add `print(f"Yaw: {yaw}, Pitch: {pitch}, Shoulder: {shoulder_tilt}")`

### If Counters Not Increasing:
1. Check if conditions are being met:
   - `abs(yaw) > 20` (not 25!)
   - `abs(pitch) > 15 AND abs(yaw) > 10`
   - `shoulder_tilt > 10` (0-100 scale)
2. Verify decay is working: `max(count - 1, 0)`

### If Dashboard Lagging:
1. Check FPS: Should be 30+
2. Reduce YOLO_INTERVAL from 2 to 3
3. Check video resolution: 640x480 is good
4. Monitor CPU usage

### If Evidence Not Saving:
1. Check `evidence/` folder exists
2. Check permissions: `ls -la evidence/`
3. Verify frame is not None before save
4. Check cv2.imwrite() doesn't fail

---

## 📊 PERFORMANCE METRICS

Target performance:
- **FPS**: 30+ (with frame skip = 2)
- **Latency**: <100ms per frame
- **Memory**: <500MB
- **GPU**: Optional (works on CPU)

Optimization applied:
- Frame resizing: 640x480
- YOLO skip: Every 2nd frame
- JPEG compression: 70%
- Stream frequency: Every 5 frames

---

## 🎯 EXPECTED OUTPUT

### OpenCV Demo Window:
```
┌────────────────────────────────┐
│ [Red box] ID 1 | Using Mobile 🚨│  92%
│                                 │
│ [Orange box] ID 3 | Looking 👀 │  65%
│                                 │
│ [Green box] ID 2 | Normal      │  0%
│                                 │
│ FPS: 42 | Students: 3          │
└────────────────────────────────┘
```

### Evidence Image:
```
┌─────────────────────────────────┐
│ ALERT: Student ID 1             │
│ Behavior: Using Mobile 🚨        │
│ Score: 92% | Time: 14:35:22    │
├─────────────────────────────────┤
│ [Red box around phone]          │
└─────────────────────────────────┘
```

### Dashboard Browser:
```
LIVE FEED
┌─────────────────────┐
│ [Red: ID 1]         │
│ [Orange: ID 3]      │  ●●● LIVE
│ [Green: ID 2]       │
└─────────────────────┘

Alerts: 2
- ID 1: Using Mobile 🚨
- ID 3: Looking Around 👀

Cheating Types:
  Using Mobile: 1
  Looking Around: 1
```

---

## ✅ VERIFICATION CHECKLIST

- [ ] `python main.py --demo` shows behavior labels
- [ ] Looking around triggers when yaw > 20°
- [ ] Looking to copy triggers when pitch > 15° AND yaw > 10°
- [ ] Leaning triggers at 15+ frames
- [ ] Mobile detection works at 0.6+ confidence
- [ ] Evidence images have labels
- [ ] Dashboard shows live feed with boxes
- [ ] FPS >= 30
- [ ] No false positives
- [ ] Demo and dashboard outputs match

---

## 📁 FILES MODIFIED

| File | Change | Status |
|------|--------|--------|
| `agents/behavior_analysis_agent.py` | Thresholds + logic simplified | ✅ |
| `main.py` | Pass detections to analyze() | ✅ |
| `api_server.py` | Processes detections correctly | ✅ |
| `agents/simple_behavior_analysis.py` | NEW - alternate implementation | ✅ |
| `simple_main.py` | NEW - alternative demo | ✅ |

---

## 🚀 NEXT STEPS

1. Run tests above
2. If working: Document in production
3. If not: Check debug output and threshold values
4. Adjust thresholds if needed (in spec lines 33-50 of behavior_analysis_agent.py)
5. Deploy to dashboard

All fixes follow the exact specification provided. System should now work as expected!

