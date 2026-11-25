# Behavior Detection Guide

This project combines computer vision signals to identify suspicious exam behavior and produce structured alerts.

## Detection Categories

- `phone_detected`: mobile phone or similar device appears near a student.
- `gaze_sideways`: repeated sideways gaze or excessive head turning.
- `gaze_downward`: repeated downward gaze that may indicate hidden notes or device use.
- `leaning`: body posture suggests leaning toward another student or desk area.
- `paper_sharing`: movement or proximity pattern suggests answer sharing.
- `wrist_below_desk`: wrist or hand position remains below desk level for suspicious duration.

## Main Signals

- YOLO/object detection for people, phones, and exam-room objects.
- MediaPipe face and gaze analysis for head direction and attention shifts.
- MediaPipe pose/skeleton analysis for posture, shoulders, wrists, and leaning.
- Tracking IDs for associating alerts with the same student over time.
- Risk scoring for combining repeated low-confidence signals into higher-level alerts.

## Threshold Configuration

Tune thresholds in `config/config.yaml` under `detection`:

```yaml
detection:
  mobile_confidence_threshold: 0.55
  look_around_yaw_threshold: 18
  look_around_count_threshold: 3
  look_to_copy_pitch_threshold: 12
  lean_shoulder_diff_threshold: 0.08
  lean_frame_threshold: 15
```

Increase thresholds to reduce false positives. Decrease thresholds only when the system misses obvious suspicious behavior.

## Alert Logging Flow

1. Detection modules produce behavior candidates for each tracked student.
2. The risk engine combines candidates into a risk score.
3. Alert-worthy events are written through `AlertLogger`.
4. Evidence images are stored under `evidence/` when available.
5. Reports are generated from the real session log.

## Testing Recommendations

- Start with a short webcam session and verify no alerts fire during normal posture.
- Test one behavior at a time: phone, looking sideways, looking down, leaning.
- Review generated PDFs in `reports/` for correct student IDs, confidence, and evidence paths.
- Adjust `config/config.yaml` only after repeated false positives or false negatives.
