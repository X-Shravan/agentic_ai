# Persistent State Fix for Backend API 🔄

## Problem
Dashboard behavior detection was NOT working because:
- Backend API processed each frame independently
- Counters (look_count, copy_count, lean_frames, sharing_count) reset on each request
- No temporal memory across frames
- Behavior detection failed (needs counter accumulation)

## Root Cause
Counter variables were **instance attributes** → destroyed when object recreated  
Each API request = fresh counters = detection impossible

## Solution: GLOBAL PERSISTENT COUNTERS ✅

### 1. Global State at Module Level
**File**: `agents/behavior_analysis_agent.py` (Lines 15-27)

```python
# GLOBAL PERSISTENT COUNTERS (for backend API)
# These persist across HTTP requests and frames
GLOBAL_LOOK_AROUND_COUNT = defaultdict(int)
GLOBAL_LOOK_COPY_COUNT = defaultdict(int)
GLOBAL_LEAN_FRAME_COUNT = defaultdict(int)
GLOBAL_SHARING_COUNT = defaultdict(int)
GLOBAL_LAST_STATUS = defaultdict(str)
GLOBAL_LAST_ALERT_TIME = defaultdict(float)
GLOBAL_LOOK_AROUND_START_TIME = defaultdict(float)
GLOBAL_LOOK_COPY_START_TIME = defaultdict(float)
GLOBAL_STATUS_HISTORY = defaultdict(lambda: deque(maxlen=5))
GLOBAL_CONFIRMED_STATUS = defaultdict(str)
GLOBAL_SHARING_PAIRS = defaultdict(int)
GLOBAL_HEAD_POSITIONS = {}
```

### 2. Reference in __init__
**File**: `agents/behavior_analysis_agent.py` (Lines 86-102)

Instance attributes now POINT TO global counters:
```python
# ✅ USE GLOBAL COUNTERS FOR PERSISTENCE ACROSS API REQUESTS
self.look_around_count = GLOBAL_LOOK_AROUND_COUNT
self.look_copy_count = GLOBAL_LOOK_COPY_COUNT
self.lean_frame_count = GLOBAL_LEAN_FRAME_COUNT
self.last_status = GLOBAL_LAST_STATUS
# ... etc
```

### 3. Per-ID Memory
All counters are `defaultdict(int)` keyed by student ID:
```python
look_around_count[id] = count
copy_count[id] = count
lean_frames[id] = count
```

### 4. Counter Decay (Gradual Reset)
In `determine_status()`:
```python
# If no movement detected:
self.look_around_count[tid] = self.decay_counter(self.look_around_count[tid])
# = max(count - 1, 0)  [gradual decrease, not instant reset]
```

### 5. Debugging Output
**File**: `agents/behavior_analysis_agent.py`

Added debug prints to show counter state:
```python
print(f"[DEBUG] ID: {tid} | Status: {status} | " +
      f"Look_Count: {self.look_around_count[tid]} | " +
      f"Copy_Count: {self.look_copy_count[tid]} | " +
      f"Lean_Frames: {self.lean_frame_count[tid]}")
```

### 6. Debug API Endpoint
**File**: `api_server.py` (Lines 325-344)

New endpoint: `/api/debug/counters`
```
GET /api/debug/counters
Response: {
  "counters": {
    "1": {"look_around": 3, "look_copy": 0, "lean_frames": 5, "status": "Looking Around 👀"},
    "2": {"look_around": 0, "look_copy": 2, "lean_frames": 0, "status": "Normal"}
  },
  "timestamp": "2026-04-20T15:30:45.123456"
}
```

## How It Works

### Before (BROKEN ❌)
```
Request 1: Frame → Fresh BehaviorAnalysisAgent → Counters = {} → Detection fails
Request 2: Frame → Fresh BehaviorAnalysisAgent → Counters = {} → Detection fails
```

### After (FIXED ✅)
```
Request 1: Frame → Shared BehaviorAnalysisAgent → GLOBAL_LOOK_AROUND_COUNT[id]++ → persist
Request 2: Frame → Shared BehaviorAnalysisAgent → GLOBAL_LOOK_AROUND_COUNT[id]++ → accumulate
Request 3: Frame → Shared BehaviorAnalysisAgent → Check if count >= 3 → DETECT!
```

## Key Changes

| File | Line(s) | Change |
|------|---------|--------|
| behavior_analysis_agent.py | 15-27 | Added global counter definitions |
| behavior_analysis_agent.py | 86-102 | Instance attrs point to globals |
| behavior_analysis_agent.py | 428-429 | Added debug output for counters |
| behavior_analysis_agent.py | 560-577 | Added get_counter_stats() method |
| behavior_analysis_agent.py | 418 | Added frame processing debug |
| api_server.py | 325-344 | Added /api/debug/counters endpoint |

## Testing

### 1. Check Counters via API
```bash
curl http://localhost:5000/api/debug/counters
```

Expected output:
```json
{
  "counters": {
    "1": {
      "look_around": 3,
      "look_copy": 0,
      "lean_frames": 8,
      "status": "Looking Around 👀"
    }
  }
}
```

### 2. Run Demo
```bash
python main.py --demo
```

Expected behavior:
- Head movements detected consistently
- Counters accumulate (not reset)
- Status changes after threshold (3-15 frames)
- Console shows debug output per frame

### 3. Test Backend
```bash
python api_server.py
# In another terminal:
curl http://localhost:5000/api/debug/counters
```

Expected:
- Counters increment over multiple requests
- DO NOT reset between requests
- Status updates consistently

## Verification Checklist

- [x] Global counters defined at module level
- [x] Instance attributes reference global counters
- [x] Per-ID storage works (defaultdict)
- [x] Decay mechanism working (max(count-1, 0))
- [x] Debug output shows counter state
- [x] API endpoint returns counter stats
- [x] Counters persist across requests
- [x] No false resets on new frames

## Result

✅ Backend behavior detection now works like demo mode  
✅ Counters accumulate across API requests  
✅ Temporal state maintained  
✅ Dashboard matches demo output  
✅ No more "Always Normal" status bug  
