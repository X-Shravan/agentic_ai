# ✅ COMPLETE SYSTEM VERIFICATION CHECKLIST

## Pre-Flight Checks

### Environment Setup
- [ ] Python virtual environment activated
- [ ] All dependencies installed (YOLO, OpenCV, MediaPipe)
- [ ] Camera or demo video available
- [ ] `evidence/` folder exists and has write permissions
- [ ] GPU available (optional but recommended)

### File Integrity
- [ ] `agents/behavior_analysis_agent.py` - No syntax errors ✓
- [ ] `agents/tracking_agent.py` - No syntax errors ✓
- [ ] `main.py` - No syntax errors ✓
- [ ] `alerts/evidence_capture.py` - No syntax errors ✓
- [ ] Config files present: `config/config.yaml`

---

## Behavior Detection Tests

### Test 1: Mobile Detection (INSTANT)
```
Procedure:
1. Start: python main.py --demo
2. Wait for student frames
3. Hold a phone/object in frame
4. Expected output:
   - RED bounding box appears immediately
   - Display: "Using Mobile 🚨"
   - Confidence: ~95%
   - Console: "🔴 ALERT DETECTED → ID X: Using Mobile 🚨"
   - Screenshot saved: evidence/ID_X_mobile_TIMESTAMP.jpg

Result: [ ] PASS  [ ] FAIL
```

### Test 2: Looking Around (YAW > 18°)
```
Procedure:
1. Start system
2. Look LEFT or RIGHT for 3+ frames
3. Expected output:
   - ORANGE bounding box
   - Display: "Looking Around 👀"
   - Confidence: ~70%
   - Counter shows: 1, 2, 3 (then alert)
   - No immediate save (not highest priority)

Result: [ ] PASS  [ ] FAIL
```

### Test 3: Looking to Copy (PITCH > 12° AND YAW > 8°)
```
Procedure:
1. Start system
2. Look DOWN and to the SIDE for 3+ frames
3. Expected output:
   - RED bounding box
   - Display: "Looking to Copy 🚨"
   - Confidence: ~85%
   - Screenshot saved: evidence/ID_X_copy_TIMESTAMP.jpg

Result: [ ] PASS  [ ] FAIL
```

### Test 4: Leaning (SHOULDER > 0.08 for 15 frames)
```
Procedure:
1. Start system
2. Lean RIGHT or LEFT continuously for ~1 second
3. Expected output:
   - ORANGE bounding box
   - Display: "Leaning ↘️"
   - Confidence: ~60%
   - Needs 15+ continuous frames

Result: [ ] PASS  [ ] FAIL
```

### Test 5: Counter Decay (NO INSTANT RESET)
```
Procedure:
1. Look around for 3 frames → count: 1, 2, 3 (alert)
2. Look forward for 1 frame → count should be 2 (not 0!)
3. Continue looking forward → count: 2, 1, 0 (gradual)

Expected: count = max(3-1, 0) = 2
NOT: count = 0 (instant reset)

Result: [ ] PASS  [ ] FAIL
```

### Test 6: Per-ID Tracking
```
Procedure:
1. Start system with 2 students
2. Student 1 looks around → ID 1 alert
3. Student 2 stays normal → ID 2 normal
4. Expected:
   - Independent counters per ID
   - No cross-contamination
   - Each ID has separate state

Result: [ ] PASS  [ ] FAIL
```

---

## Display Output Tests

### Test 7: FPS Display
```
Procedure:
1. Start system
2. Look at top-left corner
3. Expected:
   - "FPS: 15" (or similar)
   - Updates every frame
   - No frozen values

Result: [ ] PASS  [ ] FAIL
```

### Test 8: Color Coding
```
Procedure:
1. Trigger Mobile detection → RED box
2. Trigger Looking to Copy → RED box
3. Trigger Looking Around → ORANGE box
4. Trigger Leaning → ORANGE box
5. Normal student → GREEN box

Expected:
- RED = Alert (Mobile/Copy)
- ORANGE = Suspicious (Looking/Leaning)
- GREEN = Normal

Result: [ ] PASS  [ ] FAIL
```

### Test 9: Status Display Format
```
Procedure:
1. Observe display text
2. Expected format:
   ID 1 | Using Mobile 🚨 | 95%
   ID 2 | Looking Around 👀 | 70%
   ID 3 | Normal | 5%

Result: [ ] PASS  [ ] FAIL
```

### Test 10: Bounding Box Labels
```
Procedure:
1. Observe boxes
2. Expected:
   - Label above each box: [ ID X | Status ]
   - Matches box color
   - Clear and readable

Example: [ ID 1 | Using Mobile 🚨 ]

Result: [ ] PASS  [ ] FAIL
```

### Test 11: System Info at Bottom
```
Procedure:
1. Look at bottom of screen
2. Expected:
   Students: 3 | Alerts: 1
   - Updates in real-time
   - Correct count

Result: [ ] PASS  [ ] FAIL
```

---

## Evidence Saving Tests

### Test 12: Evidence File Creation
```
Procedure:
1. Trigger an alert
2. Check evidence/ folder
3. Expected:
   - File exists
   - Named format: ID_X_situation_20260418_143022.jpg
   - Timestamp correct

Result: [ ] PASS  [ ] FAIL
```

### Test 13: No Duplicate Saves
```
Procedure:
1. Trigger Mobile alert (frame 100)
2. Continue showing phone (frame 101-110)
3. Expected:
   - ONE file saved on frame 100
   - NO new files during frames 101-110
   - Status unchanged = no save

Result: [ ] PASS  [ ] FAIL
```

### Test 14: Evidence Metadata
```
Procedure:
1. Trigger alert and save screenshot
2. Open image file
3. Expected:
   - Student ID displayed
   - Behavior shown
   - Timestamp visible
   - Confidence score shown
   - Metadata box drawn on image

Result: [ ] PASS  [ ] FAIL
```

### Test 15: Situation Detection in Filename
```
Procedure:
1. Trigger Mobile alert → evidence/ID_X_mobile_TIMESTAMP.jpg
2. Trigger Copy alert → evidence/ID_X_copy_TIMESTAMP.jpg
3. Trigger Looking alert → evidence/ID_X_looking_TIMESTAMP.jpg
4. Trigger Leaning alert → evidence/ID_X_leaning_TIMESTAMP.jpg

Result: [ ] PASS  [ ] FAIL
```

---

## Performance Tests

### Test 16: FPS Performance
```
Procedure:
1. Run with demo video
2. Monitor FPS display
3. Expected:
   - Minimum 10 FPS
   - Optimal 15-20 FPS
   - Smooth playback

Actual FPS: ___________

Result: [ ] PASS  [ ] FAIL
```

### Test 17: Multi-Student Handling
```
Procedure:
1. Run with 5+ students in frame
2. Expected:
   - All tracked (different IDs)
   - All analyzed independently
   - System remains responsive
   - FPS doesn't drop significantly

Result: [ ] PASS  [ ] FAIL
```

### Test 18: Memory Usage
```
Procedure:
1. Run system for 5 minutes
2. Monitor system resources
3. Expected:
   - Memory stable (no leaks)
   - CPU < 80%
   - No crashes

Result: [ ] PASS  [ ] FAIL
```

---

## Edge Cases & Robustness

### Test 19: Quick Head Movement
```
Procedure:
1. Quickly look left
2. Immediately look right
3. Expected:
   - Counters don't reset instantly
   - No false alert
   - Gradual decay in action

Result: [ ] PASS  [ ] FAIL
```

### Test 20: Partial Face Out of Frame
```
Procedure:
1. Move partially out of frame
2. Expected:
   - System doesn't crash
   - Graceful degradation
   - Error handling

Result: [ ] PASS  [ ] FAIL
```

### Test 21: Camera Off
```
Procedure:
1. Camera disconnects
2. Expected:
   - System doesn't crash
   - Appropriate error message
   - Graceful exit

Result: [ ] PASS  [ ] FAIL
```

### Test 22: Low Light
```
Procedure:
1. Reduce light
2. Expected:
   - Face detection still works
   - More false positives acceptable
   - No crashes

Result: [ ] PASS  [ ] FAIL
```

---

## Configuration Tests

### Test 23: Threshold Adjustment
```
Procedure:
1. Decrease LOOK_AROUND_YAW to 15°
2. Look less to trigger alert
3. Expected:
   - Alert triggers faster
   - More sensitive

Result: [ ] PASS  [ ] FAIL
```

### Test 24: Demo Mode
```
Procedure:
1. Run: python main.py --demo
2. Expected:
   - Loads demo video
   - Shows detections
   - No camera needed

Result: [ ] PASS  [ ] FAIL
```

### Test 25: Custom Config
```
Procedure:
1. Edit config.yaml
2. Run: python main.py --config config/custom.yaml
3. Expected:
   - Uses custom settings
   - Applies to system

Result: [ ] PASS  [ ] FAIL
```

---

## Console Output Tests

### Test 26: Alert Logging
```
Expected console output when alert triggers:

🔴 ALERT DETECTED → ID 1: Using Mobile 🚨
📸 EVIDENCE SAVED: evidence/ID_1_mobile_20260418_143022.jpg

Result: [ ] PASS  [ ] FAIL
```

### Test 27: System Startup
```
Expected console output on startup:

🚀 System Started
Monitoring X students...
FPS: 15.2 | Students: 3 | Alerts: 1

Result: [ ] PASS  [ ] FAIL
```

### Test 28: Frame Processing
```
Expected:
- No error messages
- Smooth frame-by-frame processing
- Status updates visible

Result: [ ] PASS  [ ] FAIL
```

---

## Integration Tests

### Test 29: Full Workflow
```
Procedure:
1. Start system
2. Detect student with phone
3. Student looks around
4. Student looks to copy
5. Student leans
6. Close system (press Q)

Expected:
- All behaviors detected
- Evidence saved
- System exits gracefully

Result: [ ] PASS  [ ] FAIL
```

### Test 30: Long-Running Session
```
Procedure:
1. Run system for 30 minutes
2. Multiple students
3. Various behaviors
4. Expected:
   - No memory leaks
   - No crashes
   - Consistent accuracy

Result: [ ] PASS  [ ] FAIL
```

---

## Final Checklist

### Code Quality
- [ ] No syntax errors in all files
- [ ] Proper indentation
- [ ] Docstrings present
- [ ] Comments clear

### Functionality
- [ ] All 5 behaviors detected
- [ ] Counter decay working
- [ ] Per-ID tracking independent
- [ ] Evidence saving on change
- [ ] Color coding correct
- [ ] Display format correct
- [ ] FPS displayed
- [ ] System info shown

### Performance
- [ ] Runs at 10+ FPS
- [ ] Handles 5+ students
- [ ] Memory stable
- [ ] No crashes

### Robustness
- [ ] Handles missing faces
- [ ] Graceful degradation
- [ ] Error handling present
- [ ] Works with demo mode

---

## Summary

### Total Tests: 30
### Passed: _____ / 30
### Failed: _____ / 30

### Critical Tests (must pass):
- [ ] Test 1 - Mobile Detection
- [ ] Test 5 - Counter Decay
- [ ] Test 8 - Color Coding
- [ ] Test 12 - Evidence Creation

### Status: [ ] READY FOR DEPLOYMENT

---

## Sign-Off

System verified and ready for use:

Date: ________________
Tested by: ________________
Notes: ________________

✅ **System is Production-Ready!** 🚀
