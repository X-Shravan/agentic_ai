# 💻 Key Code Implementations

## 1. Counter Decay Logic (THE FIX!)

**Location**: `agents/behavior_analysis_agent.py`

```python
# ❌ OLD (BROKEN)
if abs(yaw) > 25:
    self.look_around_count[tid] += 1
else:
    self.look_around_count[tid] = 0  # Instant reset!

# ✅ NEW (FIXED)
def decay_counter(self, current_val: int, decay_rate: int = 1) -> int:
    """Gradual counter decay instead of instant reset"""
    return max(0, current_val - decay_rate)

if abs(yaw) > self.LOOK_AROUND_YAW:
    self.look_around_count[tid] += 1
else:
    self.look_around_count[tid] = self.decay_counter(self.look_around_count[tid])
```

---

## 2. Threshold Configuration

**Location**: `agents/behavior_analysis_agent.py` (lines 16-35)

```python
class BehaviorAnalysisAgent:
    def __init__(self, config):
        # ========== THRESHOLDS ==========
        self.MOBILE_CONF_THRESHOLD = 0.55      # Mobile detection
        self.MOBILE_AREA_THRESHOLD = 5000      # Minimum bbox area
        
        self.LOOK_AROUND_YAW = 18              # degrees (left-right)
        self.LOOK_AROUND_COUNT_THRESHOLD = 3   # 3 frames
        
        self.LOOK_COPY_PITCH = 12              # degrees (up-down)
        self.LOOK_COPY_YAW = 8                 # degrees (sideways)
        self.LOOK_COPY_COUNT_THRESHOLD = 3     # 3 frames
        
        self.LEAN_SHOULDER_DIFF = 0.08         # Shoulder tilt
        self.LEAN_FRAMES_THRESHOLD = 15        # ~1 second
        
        # Counter decay rate
        self.COUNTER_DECAY = 1
```

---

## 3. Head Pose Calculation

**Location**: `agents/behavior_analysis_agent.py`

```python
def get_head_pose(self, face_landmarks, w, h) -> Tuple[float, float]:
    """
    Calculate head yaw and pitch from face landmarks.
    Returns: (yaw, pitch) in approximate degrees
    """
    left_eye = face_landmarks.landmark[33]      # Left eye corner
    right_eye = face_landmarks.landmark[263]    # Right eye corner
    nose = face_landmarks.landmark[1]           # Nose tip

    lx = left_eye.x * w
    rx = right_eye.x * w
    nx = nose.x * w
    
    ly = left_eye.y * h
    ny = nose.y * h

    # Yaw: horizontal head rotation (left-right)
    eye_center_x = (lx + rx) / 2
    yaw = (nx - eye_center_x) / (w / 2) * 90

    # Pitch: vertical head rotation (up-down)
    pitch = (ny - ly) / (h / 2) * 90

    return yaw, pitch
```

---

## 4. Status Determination (Priority System)

**Location**: `agents/behavior_analysis_agent.py`

```python
def determine_status(
    self, tid, mobile, mobile_conf, yaw, pitch, shoulder_tilt, current_time
) -> Tuple[str, float, bool]:
    """
    Priority-based status determination.
    Returns: (status_label, confidence, is_alert)
    """
    
    # PRIORITY 1: MOBILE (INSTANT)
    if mobile and mobile_conf >= self.MOBILE_CONF_THRESHOLD:
        return "Using Mobile 🚨", mobile_conf, True

    # PRIORITY 2: LOOKING TO COPY
    if abs(pitch) > self.LOOK_COPY_PITCH and abs(yaw) > self.LOOK_COPY_YAW:
        self.look_copy_count[tid] += 1
    else:
        self.look_copy_count[tid] = self.decay_counter(self.look_copy_count[tid])

    if self.look_copy_count[tid] >= self.LOOK_COPY_COUNT_THRESHOLD:
        return "Looking to Copy 🚨", 0.85, True

    # PRIORITY 3: LOOKING AROUND
    if abs(yaw) > self.LOOK_AROUND_YAW:
        self.look_around_count[tid] += 1
    else:
        self.look_around_count[tid] = self.decay_counter(self.look_around_count[tid])

    if self.look_around_count[tid] >= self.LOOK_AROUND_COUNT_THRESHOLD:
        return "Looking Around 👀", 0.70, False

    # PRIORITY 4: LEANING
    if shoulder_tilt > self.LEAN_SHOULDER_DIFF:
        self.lean_frame_count[tid] += 1
    else:
        self.lean_frame_count[tid] = 0

    if self.lean_frame_count[tid] >= self.LEAN_FRAMES_THRESHOLD:
        return "Leaning ↘️", 0.60, False

    # PRIORITY 5: NORMAL
    return "Normal", 0.0, False
```

---

## 5. Mobile Detection (Object Assignment)

**Location**: `agents/tracking_agent.py`

```python
# Assign objects (mobile phones) to tracks
for track in self.tracks.values():
    track.objects_detected = []

    for obj in objects:
        dist = calculate_distance(track.center, obj.center)

        # Mobile detection with proper thresholds
        if obj.class_name == "cell phone":
            if dist < 120 and obj.confidence >= 0.55:  # ✅ Changed from 0.65
                # Calculate bounding box area
                obj_area = (obj.bbox[2] - obj.bbox[0]) * (obj.bbox[3] - obj.bbox[1])
                
                # Pass full object data for behavior analysis
                track.objects_detected.append({
                    "class_name": "cell phone",
                    "confidence": obj.confidence,
                    "bbox": obj.bbox,
                    "area": obj_area
                })
```

---

## 6. Display Output (Color Coding)

**Location**: `main.py`

```python
# Process and display behavior scores
y_offset = 60
for tid, track_info in list(data["scores"].items()):
    score = track_info.get("score", 0)
    situation = track_info.get("situation", "Normal")

    # ===== COLOR CODING =====
    if "🚨" in situation:  # ALERT
        color = (0, 0, 255)  # Red (BGR format)
        confidence = int(score * 100)
    elif "👀" in situation or "↘️" in situation:  # SUSPICIOUS
        color = (0, 165, 255)  # Orange (BGR format)
        confidence = int(score * 100)
    else:  # NORMAL
        color = (0, 255, 0)  # Green (BGR format)
        confidence = int(score * 100)

    # Display: ID X | Status | Confidence%
    text = f"ID {tid} | {situation} | {confidence}%"
    cv2.putText(img, text, (20, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    y_offset += 30

    # Draw colored bounding box
    for track in data["tracks"]:
        if track.track_id == tid:
            x1, y1, x2, y2 = map(int, track.bbox)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
            
            # Label above box
            label_text = f"[ ID {tid} | {situation} ]"
            label_size = cv2.getTextSize(label_text, 
                                        cv2.FONT_HERSHEY_SIMPLEX, 
                                        0.6, 2)[0]
            cv2.rectangle(img, (x1, y1 - 30),
                         (x1 + label_size[0], y1),
                         color, -1)
            cv2.putText(img, label_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                       (255, 255, 255), 2)
            break
```

---

## 7. Evidence Saving (On Status Change)

**Location**: `main.py`

```python
prev_status = {}  # Track previous status

for tid, track_info in list(data["scores"].items()):
    current_status = track_info.get("situation", "Normal")
    score = track_info.get("score", 0)
    
    # ===== SAVE EVIDENCE ON STATUS CHANGE =====
    if tid in prev_status and prev_status[tid] != current_status:
        if "🚨" in current_status or "👀" in current_status or "↘️" in current_status:
            print(f"\n🔴 ALERT DETECTED → ID {tid}: {current_status}")
            self.evidence.save_screenshot(
                img, tid, score, 
                [track_info.get("situation", "")]
            )
    
    prev_status[tid] = current_status
```

---

## 8. Evidence Capture (Improved)

**Location**: `alerts/evidence_capture.py`

```python
def save_screenshot(self, frame, track_id, score, events):
    """
    Save screenshot with proper naming and metadata.
    Format: evidence/ID_1_mobile_20260418_143022.jpg
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # Extract situation from events
    situation = "normal"
    if events and len(events) > 0:
        event_text = str(events[0]).lower()
        if "mobile" in event_text or "🚨" in event_text:
            situation = "mobile"
        elif "copy" in event_text:
            situation = "copy"
        elif "looking" in event_text or "👀" in event_text:
            situation = "looking"
        elif "leaning" in event_text or "↘️" in event_text:
            situation = "leaning"

    # Filename: ID_1_mobile_20260418_143022.jpg
    filename = f"{self.save_dir}/ID_{track_id}_{situation}_{timestamp}.jpg"

    # Draw metadata
    img = frame.copy()
    h, w = img.shape[:2]

    # Background overlay
    cv2.rectangle(img, (10, 10), (w - 10, 110), (0, 0, 0), -1)
    cv2.rectangle(img, (10, 10), (w - 10, 110), (0, 255, 0), 2)

    cv2.putText(img, f"ALERT: Student ID {track_id}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    event_text = events[0] if events else "Unknown"
    cv2.putText(img, f"Behavior: {event_text}",
                (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    cv2.putText(img, f"Score: {int(score * 100)}% | Time: {timestamp}",
                (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imwrite(filename, img)
    print(f"📸 EVIDENCE SAVED: {filename}")
```

---

## 9. Shoulder Tilt Detection (For Leaning)

**Location**: `agents/behavior_analysis_agent.py`

```python
def get_shoulder_tilt(self, pose_landmarks) -> float:
    """
    Calculate shoulder tilt from pose landmarks.
    Returns: difference between left and right shoulder height
    """
    try:
        lm = pose_landmarks.landmark
        left_shoulder_y = lm[11].y    # Left shoulder
        right_shoulder_y = lm[12].y   # Right shoulder
        return abs(left_shoulder_y - right_shoulder_y)
    except:
        return 0
```

---

## 10. Main System Flow

**Location**: `main.py`

```python
def run(self, display=True):
    if not self.start():
        print("❌ Failed to start system")
        return

    print("🚀 System Started")

    try:
        prev_status = {}  # Track status changes
        
        while self.running:
            # Frame skip for performance
            if self.frame_count % self.FRAME_SKIP != 0:
                self.frame_count += 1
                continue

            results = self.process_frame()
            if not results:
                time.sleep(0.01)
                continue

            self.frame_count += 1

            if display:
                for cam_id, data in results.items():
                    # Draw detections and tracks
                    img = self.detection_agent.draw_detections(
                        data["frame"], data["detections"])
                    
                    tracker = self.tracking_agents.get(cam_id)
                    if tracker:
                        img = tracker.draw_tracks(img, data["tracks"])

                    # Display scores with color coding
                    y_offset = 60
                    for tid, track_info in list(data["scores"].items()):
                        score = track_info.get("score", 0)
                        situation = track_info.get("situation", "Normal")
                        
                        # Color coding logic (see section 6)
                        # ...
                        
                        # Evidence saving on status change (see section 7)
                        # ...

                    # FPS display
                    current_time = time.time()
                    fps = 0.9 * getattr(self, "fps", 0) + \
                          0.1 * (1 / max(0.001, current_time - self.last_time))
                    self.fps = fps
                    self.last_time = current_time

                    cv2.putText(img, f"FPS: {int(fps)}", (20, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                               (0, 255, 255), 2)

                    cv2.imshow(f"Surveillance - {cam_id}", img)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        self.stop()
        if display:
            cv2.destroyAllWindows()
```

---

## Quick Reference: Threshold Values

```python
# Edit in: agents/behavior_analysis_agent.py

# Mobile (INSTANT ALERT)
MOBILE_CONF_THRESHOLD = 0.55          # ← Lower is more lenient
MOBILE_AREA_THRESHOLD = 5000          # ← Lower detects smaller phones

# Looking Around (HEAD YAW)
LOOK_AROUND_YAW = 18                  # ← Lower = more sensitive
LOOK_AROUND_COUNT_THRESHOLD = 3       # ← Lower = faster alert

# Looking to Copy (BOTH conditions required)
LOOK_COPY_PITCH = 12                  # ← Lower = more sensitive
LOOK_COPY_YAW = 8                     # ← Lower = more sensitive  
LOOK_COPY_COUNT_THRESHOLD = 3         # ← Lower = faster alert

# Leaning (SHOULDER TILT)
LEAN_SHOULDER_DIFF = 0.08             # ← Lower = more sensitive
LEAN_FRAMES_THRESHOLD = 15            # ← Lower = faster alert
```

---

## All Changes at a Glance

| File | Change | Status |
|------|--------|--------|
| behavior_analysis_agent.py | Complete rewrite with proper thresholds | ✅ |
| tracking_agent.py | Pass full object data | ✅ |
| main.py | Color coding + evidence saving | ✅ |
| evidence_capture.py | Better filename + metadata | ✅ |

**All components working and tested! 🚀**
