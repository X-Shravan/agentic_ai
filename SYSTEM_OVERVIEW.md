# 🎯 Visual System Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXAM SURVEILLANCE SYSTEM                       │
└─────────────────────────────────────────────────────────────────┘

INPUT:
┌──────────────┐
│ Camera Feed  │
│   or Video   │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ DETECTION AGENT (YOLO)                                           │
│ ├─ Detects: person, cell phone                                   │
│ └─ Returns: bounding boxes + confidence                          │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ TRACKING AGENT                                                   │
│ ├─ Assigns IDs to students                                       │
│ ├─ Tracks across frames                                          │
│ └─ Associates objects (phones) to students                       │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ BEHAVIOR ANALYSIS AGENT ⭐ (IMPROVED)                            │
│ ├─ MediaPipe Head Pose Detection                                 │
│ │   ├─ Yaw (left-right head rotation)                            │
│ │   └─ Pitch (up-down head rotation)                             │
│ │                                                                 │
│ ├─ MediaPipe Shoulder Detection                                  │
│ │   └─ Tilt difference (leaning)                                 │
│ │                                                                 │
│ ├─ Detection Logic:                                              │
│ │   1. Mobile: conf >= 0.55 AND area > 5000 → 🚨 ALERT          │
│ │   2. Copy: pitch > 12° AND yaw > 8° (3x) → 🚨 ALERT           │
│ │   3. Looking: yaw > 18° (3x) → 👀 SUSPICIOUS                  │
│ │   4. Leaning: shoulder > 0.08 (15 frames) → ↘️ SUSPICIOUS      │
│ │   5. Normal: none of above                                     │
│ │                                                                 │
│ └─ Counter Decay: max(count - 1, 0) instead of instant reset     │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ RISK SCORING AGENT                                               │
│ ├─ Calculates risk score based on behavior                       │
│ └─ Returns priority + confidence                                 │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ DECISION AGENT                                                   │
│ ├─ Determines if alert should trigger                            │
│ └─ Triggers callback for evidence capture                        │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ EVIDENCE CAPTURE ✅ (IMPROVED)                                   │
│ ├─ Saves screenshot: ID_X_situation_TIMESTAMP.jpg                │
│ ├─ Only on status CHANGE (no duplicates)                         │
│ └─ Draws metadata on image                                       │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ DISPLAY ✅ (IMPROVED)                                            │
│ ├─ FPS in top-left                                               │
│ ├─ Per-student status: ID | Status | Confidence%                 │
│ ├─ Color-coded boxes: Red/Orange/Green                           │
│ ├─ Labels above boxes: [ ID X | Status ]                         │
│ └─ System info at bottom: Students: X | Alerts: Y                │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
OUTPUT:
┌──────────────────────────┐
│   Video Display          │
│   Console Logs           │
│   Evidence Folder        │
└──────────────────────────┘
```

---

## Detection Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                 INCOMING STUDENT FRAME                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         EXTRACT FACE & POSE (MediaPipe)                         │
│                                                                 │
│  Face Mesh         Pose Landmarks                               │
│  ├─ Get yaw        ├─ Shoulder L (11)                           │
│  └─ Get pitch      └─ Shoulder R (12)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐
│ Check Mobile     │  │ Check Behaviors  │  │ Track Counters
│                  │  │                  │  │
│ confidence       │  │ 1. yaw > 18°?    │  │ Per ID:
│ >= 0.55?         │  │    → look_count++│  │ - look_around
│                  │  │    elif count≥3  │  │ - look_copy
│ area             │  │    → Looking 👀  │  │ - lean_frames
│ > 5000?          │  │                  │  │
│                  │  │ 2. pitch>12°&    │  │ Decay:
│ If YES:          │  │    yaw>8°?       │  │ count = max(0,
│ Using Mobile 🚨  │  │    → copy_count++│  │   count - 1)
│ (instant)        │  │    elif count≥3  │  │
└──────────────────┘  │    → Looking to  │  └──────────────┘
                      │       Copy 🚨    │
                      │                  │
                      │ 3. shoulder_diff │
                      │    > 0.08?       │
                      │    → lean_count++│
                      │    elif frames≥15│
                      │    → Leaning ↘️   │
                      │                  │
                      │ 4. Else:         │
                      │    → Normal ✓    │
                      └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│           DETERMINE FINAL STATUS (Priority Order)               │
│                                                                 │
│  1. Using Mobile 🚨        ← HIGHEST (instant alert)            │
│  2. Looking to Copy 🚨     ← HIGH (alert)                       │
│  3. Looking Around 👀      ← MEDIUM (suspicious)                │
│  4. Leaning ↘️             ← MEDIUM (suspicious)                │
│  5. Normal                ← LOW (ok)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            DISPLAY & SAVE EVIDENCE                              │
│                                                                 │
│  If Alert:                                                      │
│  ├─ Draw RED box around student                                 │
│  ├─ Save: evidence/ID_X_situation_TIMESTAMP.jpg                 │
│  └─ Print: 🔴 ALERT DETECTED → ID X: Status                    │
│                                                                 │
│  If Suspicious:                                                 │
│  ├─ Draw ORANGE box around student                              │
│  └─ Print: ID X | Status | Confidence%                         │
│                                                                 │
│  If Normal:                                                     │
│  ├─ Draw GREEN box around student                               │
│  └─ Print: ID X | Normal | 5%                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Display Output Example

```
┌────────────────────────────────────────────────────────────────────┐
│                   EXAM SURVEILLANCE MONITOR                         │
├────────────────────────────────────────────────────────────────────┤
│  FPS: 15                                                            │
│                                                                    │
│  ID 1 | Using Mobile 🚨 | 95%                                    │
│  ID 2 | Looking Around 👀 | 70%                                   │
│  ID 3 | Looking to Copy 🚨 | 85%                                 │
│  ID 4 | Normal | 5%                                              │
│                                                                    │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │[ID 1|Using Mobile] │  │[ID 2|Looking Around]                 │
│  │                    │  │                    │                 │
│  │   Student 1        │  │   Student 2        │                 │
│  │                    │  │                    │                 │
│  │  (RED BOX)         │  │  (ORANGE BOX)      │                 │
│  │  ALERT!            │  │  SUSPICIOUS        │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                    │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │[ID 3|Looking Copy]  │  │[ID 4|Normal]       │                 │
│  │                    │  │                    │                 │
│  │   Student 3        │  │   Student 4        │                 │
│  │                    │  │                    │                 │
│  │  (RED BOX)         │  │  (GREEN BOX)       │                 │
│  │  ALERT!            │  │  OK                │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                    │
│  Students: 4 | Alerts: 2                                        │
└────────────────────────────────────────────────────────────────────┘
```

---

## Counter Mechanism (OLD vs NEW)

### ❌ OLD (BROKEN)
```
Looking Around Detection:

Frame 1: yaw = 22° > 18° ✓
         counter = 1

Frame 2: yaw = 25° > 18° ✓
         counter = 2

Frame 3: yaw = 20° > 18° ✓
         counter = 3 → ALERT!

Frame 4: yaw = 5° < 18° ✗
         counter = 0 ❌ INSTANT RESET

Frame 5: yaw = 8° < 18° ✗
         counter = 0 (stays reset)

PROBLEM: Any small head movement resets everything
         Rapid oscillations cause counter to bounce
         Many false negatives
```

### ✅ NEW (FIXED)
```
Looking Around Detection:

Frame 1: yaw = 22° > 18° ✓
         counter = 1

Frame 2: yaw = 25° > 18° ✓
         counter = 2

Frame 3: yaw = 20° > 18° ✓
         counter = 3 → ALERT!

Frame 4: yaw = 5° < 18° ✗
         counter = max(3-1, 0) = 2 ✓ DECAY

Frame 5: yaw = 8° < 18° ✗
         counter = max(2-1, 0) = 1 ✓ DECAY

Frame 6: yaw = 3° < 18° ✗
         counter = max(1-1, 0) = 0 ✓ DECAY

BENEFIT: Gradual fade prevents false resets
         Slight head movements don't break counter
         More realistic detection
```

---

## Threshold Comparison

### Mobile Detection
```
┌─────────────────────┬──────────┬──────────┐
│ Parameter           │ Before   │ After    │
├─────────────────────┼──────────┼──────────┤
│ Confidence          │ 0.65     │ 0.55 ✓   │
│ Min Area            │ None     │ 5000 ✓   │
│ Trigger             │ Complex  │ Instant  │
└─────────────────────┴──────────┴──────────┘
```

### Head Pose (Looking Around)
```
┌─────────────────────┬──────────┬──────────┐
│ Parameter           │ Before   │ After    │
├─────────────────────┼──────────┼──────────┤
│ Yaw Threshold       │ 25°      │ 18° ✓    │
│ Count Threshold     │ 5        │ 3 ✓      │
│ Counter Decay       │ Instant  │ Gradual ✓│
└─────────────────────┴──────────┴──────────┘
```

### Head Pose (Looking to Copy)
```
┌─────────────────────┬──────────┬──────────┐
│ Parameter           │ Before   │ After    │
├─────────────────────┼──────────┼──────────┤
│ Pitch Threshold     │ 20°      │ 12° ✓    │
│ Yaw Threshold       │ 10°      │ 8° ✓     │
│ Count Threshold     │ 5        │ 3 ✓      │
│ Logic               │ OR       │ AND ✓    │
└─────────────────────┴──────────┴──────────┘
```

### Leaning
```
┌─────────────────────┬──────────┬──────────┐
│ Parameter           │ Before   │ After    │
├─────────────────────┼──────────┼──────────┤
│ Shoulder Diff       │ 0.07     │ 0.08 ✓   │
│ Duration            │ 3 sec    │ 1 sec ✓  │
│ Frame Count         │ 45       │ 15 ✓     │
│ Logic               │ Time-based │ Frames │
└─────────────────────┴──────────┴──────────┘
```

---

## Evidence Saving Example

```
When alert detected:

Frame 120:
├─ Previous status: "Normal"
├─ Current status: "Using Mobile 🚨"
├─ Status CHANGED ✓
└─ SAVE: evidence/ID_1_mobile_20260418_143022.jpg

Frame 121-125:
├─ Previous status: "Using Mobile 🚨"
├─ Current status: "Using Mobile 🚨"
├─ Status UNCHANGED ✗
└─ NO SAVE (prevents duplicates)

Frame 126:
├─ Previous status: "Using Mobile 🚨"
├─ Current status: "Looking Around 👀"
├─ Status CHANGED ✓
└─ SAVE: evidence/ID_1_looking_20260418_143035.jpg
```

---

## Color Coding System

```
BOUNDING BOX COLORS:

🔴 RED = ALERT
   ├─ Using Mobile 🚨 (95% confidence)
   └─ Looking to Copy 🚨 (85% confidence)
   
🟠 ORANGE = SUSPICIOUS  
   ├─ Looking Around 👀 (70% confidence)
   └─ Leaning ↘️ (60% confidence)
   
🟢 GREEN = NORMAL
   └─ Normal (5% confidence)


TEXT DISPLAY FORMAT:
ID X | Status | Confidence%

Example:
ID 1 | Using Mobile 🚨 | 95%
ID 2 | Looking Around 👀 | 70%
ID 3 | Normal | 5%
```

---

## System Ready! 🚀

All components integrated and working:
- ✅ Proper detection thresholds
- ✅ Counter decay mechanism
- ✅ Real-time display
- ✅ Evidence saving
- ✅ Color coding
- ✅ Per-student tracking

**Start with**: `python main.py --demo`
