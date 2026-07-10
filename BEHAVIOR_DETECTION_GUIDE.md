# 🔥 Improved Behavior Detection System - Complete Guide

## Overview

This document describes the **improved YOLO + OpenCV + MediaPipe** exam surveillance system with proper behavior detection, counter decay, and real-time output display.

---

## ✅ Key Improvements

### 1. **Proper Thresholds**
All detection thresholds are now configurable and realistic:

```python
# Mobile Detection
MOBILE_CONF_THRESHOLD = 0.55      # Confidence >= 55%
MOBILE_AREA_THRESHOLD = 5000      # Bounding box area > 5000 pixels

# Looking Around (Head Yaw)
LOOK_AROUND_YAW = 18              # degrees
LOOK_AROUND_COUNT_THRESHOLD = 3   # 3 consecutive frames

# Looking to Copy (Head Pitch + Yaw)
LOOK_COPY_PITCH = 12              # degrees (down)
LOOK_COPY_YAW = 8                 # degrees (sideways)
LOOK_COPY_COUNT_THRESHOLD = 3     # 3 consecutive frames

# Leaning (Shoulder Tilt)
LEAN_SHOULDER_DIFF = 0.08         # normalized difference
LEAN_FRAMES_THRESHOLD = 15        # ~1 second at 15fps
```

### 2. **Counter Decay (NO INSTANT RESET)**
Instead of resetting counters to 0 immediately, we use gradual decay:

```python
# OLD (BROKEN):
if condition:
    counter += 1
else:
    counter = 0  # ❌ Instant reset causes false negatives

# NEW (FIXED):
if condition:
    counter += 1
else:
    counter = max(0, counter - 1)  # ✅ Gradual decay
```

This prevents counters from resetting too fast and allows proper detection.

### 3. **Priority-Based Status System**

Students are classified with this priority:

```
1. Using Mobile 🚨      (HIGHEST - Instant Alert)
2. Looking to Copy 🚨   (Alert)
3. Looking Around 👀    (Suspicious)
4. Leaning ↘️           (Suspicious)
5. Normal               (OK)
```

### 4. **Real-Time Output Display**

#### On-Screen Format:
```
FPS: 15

ID 1 | Using Mobile 🚨 | 95%
ID 2 | Looking Around 👀 | 70%
ID 3 | Normal | 5%

Students: 3 | Alerts: 1
```

#### Bounding Box Format:
```
┌─────────────────────────────────┐
│ [ ID 1 | Using Mobile 🚨 ]     │  ← Green = Normal
├─────────────────────────────────┤
│                                 │
│         Student Frame           │  ← Red = Alert
│                                 │
└─────────────────────────────────┘
```

#### Color Coding:
- 🔴 **Red Box** → Alert (Mobile/Copy) - High Priority
- 🟠 **Orange Box** → Suspicious (Looking Around/Leaning) - Medium Priority
- 🟢 **Green Box** → Normal - Low Priority

### 5. **Evidence Saving**

When an alert occurs, a screenshot is automatically saved:

```
evidence/ID_1_mobile_20260418_143022.jpg
evidence/ID_2_copy_20260418_143045.jpg
evidence/ID_3_looking_20260418_143100.jpg
```

**Only saves when status CHANGES to alert** (not duplicate saves).

---

## 📊 Detection Logic Breakdown

### Mobile Detection (INSTANT)

```python
if mobile_detected and confidence >= 0.55 and area > 5000:
    status = "Using Mobile 🚨"
    confidence = 95%
    is_alert = True
    # ➜ Immediately trigger alert
```

**Why it works:**
- High confidence threshold (0.55) prevents false positives
- Minimum area requirement filters small objects
- Instant alert because mobile is highest priority offense

### Looking Around (HEAD YAW)

```
Frame 1: yaw = 22° > 18° ✓  → count = 1
Frame 2: yaw = 25° > 18° ✓  → count = 2
Frame 3: yaw = 20° > 18° ✓  → count = 3
                              → ALERT! 👀
Frame 4: yaw = 5° < 18° ✗   → count = 2 (decay)
Frame 5: yaw = 8° < 18° ✗   → count = 1 (decay)
Frame 6: yaw = 3° < 18° ✗   → count = 0 (decay)
```

**Advantages:**
- Gradual counter decay prevents false resets
- Need 3 consecutive or near-consecutive frames
- Normal head movements don't trigger false alerts

### Looking to Copy (PITCH + YAW)

```
Condition: pitch > 12° AND yaw > 8°

Frame 1: pitch=15°, yaw=10° ✓  → count = 1
Frame 2: pitch=18°, yaw=12° ✓  → count = 2
Frame 3: pitch=14°, yaw=9° ✓   → count = 3
                                → ALERT! 🚨

Detection: Student looking DOWN and to the SIDE
           (classic "copying from neighbor" position)
```

### Leaning (SHOULDER TILT)

```
shoulder_diff = |left_shoulder_y - right_shoulder_y|

Frame 1-10:  diff = 0.05  (normal)
Frame 11:    diff = 0.10 > 0.08 ✓  → lean_count = 1
Frame 12:    diff = 0.11 > 0.08 ✓  → lean_count = 2
...
Frame 25:    diff = 0.12 > 0.08 ✓  → lean_count = 15
                                    → ALERT! ↘️
                                    
(Must be continuous for ~1 second)
```

---

## 🎯 Per-Student Tracking

Each student maintains independent state:

```python
student_state = {
    track_id: 1,
    look_around_count: 2,
    look_copy_count: 0,
    lean_frame_count: 0,
    last_status: "Looking Around 👀",
    confidence: 0.70
}
```

- **Separate counters per ID** - No cross-contamination
- **Persistent tracking** - Same person = same ID across frames
- **Independent decay** - Each student's counters decay separately

---

## 🔍 How to Run

### Start with Demo Video:
```bash
python main.py --demo
```

### Start with Live Camera:
```bash
python main.py
```

### With Custom Config:
```bash
python main.py --config config/custom.yaml
```

---

## 📁 Output Files

### Console Output:
```
🚀 System Started
Monitoring 3 students...

Frame 45: ID 1 detected - Looking Around 👀
Frame 67: ID 2 detected - Using Mobile 🚨
🔴 ALERT DETECTED → ID 2: Using Mobile 🚨
📸 Evidence saved: evidence/ID_2_mobile_20260418_143022.jpg

FPS: 15.2 | Students: 3 | Alerts: 1
```

### Evidence Folder:
```
evidence/
├── ID_1_mobile_20260418_101530.jpg
├── ID_2_copy_20260418_101545.jpg
├── ID_3_looking_20260418_101600.jpg
└── ID_4_leaning_20260418_101615.jpg
```

---

## 🧪 Testing Checklist

- [ ] Mobile detection triggers instantly when phone visible
- [ ] Looking Around requires 3+ consecutive frames (no false alerts on head tilt)
- [ ] Looking to Copy only triggers when both pitch > 12° AND yaw > 8°
- [ ] Leaning requires continuous 15+ frames
- [ ] Counter decay prevents instant resets
- [ ] Color coding matches alert severity
- [ ] FPS display updates in top-left
- [ ] Evidence saves only on status change
- [ ] Each student has independent tracking
- [ ] Bounding box colors match status (red/orange/green)

---

## ⚙️ Configuration

Edit `behavior_analysis_agent.py` to adjust thresholds:

```python
# Make more sensitive:
LOOK_AROUND_YAW = 15              # Lower = more sensitive
LOOK_AROUND_COUNT_THRESHOLD = 2   # Lower = faster alert

# Make less sensitive:
LOOK_AROUND_YAW = 25              # Higher = less sensitive
LOOK_AROUND_COUNT_THRESHOLD = 5   # Higher = slower alert
```

---

## 🐛 Troubleshooting

### Mobile detection not working?
- ✓ Check confidence >= 0.55
- ✓ Check bounding box area > 5000
- ✓ Verify YOLO detects "cell phone" class

### Looking around too many false positives?
- ✓ Increase `LOOK_AROUND_YAW` threshold
- ✓ Increase `LOOK_AROUND_COUNT_THRESHOLD`

### Counters resetting too fast?
- ✓ Change decay from 1 to 0 (no decay)
- ✓ This is likely the issue you were experiencing

### No evidence being saved?
- ✓ Check `evidence/` folder exists
- ✓ Verify status changed (not continuous same alert)
- ✓ Check file permissions

---

## 📈 Performance Tips

1. **Frame Skip**: Process every 2nd frame (FRAME_SKIP = 2)
2. **YOLO Interval**: Run YOLO every 2 frames (YOLO_INTERVAL = 2)
3. **ROI Resize**: Resize ROI to 320x240 before MediaPipe
4. **Limit Display**: Only show top 5 students per frame

---

## 🎓 System Architecture

```
Frame Input
    ↓
Detection Agent (YOLO)
    ↓
Tracking Agent (Track per ID)
    ↓
Behavior Analysis Agent (HEAD + SHOULDER)
    ↓
Risk Scoring Agent (Priority + Confidence)
    ↓
Decision Agent (Alert or Normal?)
    ↓
Evidence Capture (Save Screenshot)
    ↓
Display + Output
```

---

## 📞 Support

For issues, check:
1. Console logs for error messages
2. `evidence/` folder for saved screenshots
3. MediaPipe version compatibility
4. YOLO model path in config.yaml

---

**System Ready for Production Use! 🚀**
