# Performance Optimization Guide

## Edge AI

- Use `Queue(maxsize=1)` or `LatestFrameQueue` to keep only current frames.
- Apply frame skipping for heavy models and run full analysis only on tracked ROIs.
- Use YOLOv8n for real-time detection and export to ONNX/TensorRT for production GPU inference.
- Batch MediaPipe ROI crops per frame where possible.
- Run Gemini reasoning asynchronously after risk thresholds; never call Gemini per frame.

## Target Thread Architecture

1. Camera capture
2. YOLO detection
3. DeepSORT tracking
4. Face mesh
5. Pose
6. Eye gaze
7. Behavior fusion
8. Risk engine
9. Evidence collection
10. WebRTC streaming
11. Gemini reasoning
12. Report generation
13. WebSocket metadata alerts

## Latency Budget

- Capture: 5-10 ms
- YOLO: 10-25 ms on GPU
- Tracking: 2-5 ms
- ROI MediaPipe: 10-30 ms depending on student count
- Fusion/risk: below 5 ms
- WebRTC encode: 10-20 ms

## Scaling

- Assign 1 GPU process per 2-3 HD streams for YOLOv8n unless TensorRT benchmarks support more.
- Reduce per-camera resolution to the minimum that preserves faces, hands, and phone-size objects.
- Use seat mapping to reduce expensive re-identification operations.
- Persist identities in memory during the session and snapshot metadata to PostgreSQL.
