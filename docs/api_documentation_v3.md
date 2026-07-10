# API Documentation V3

## Transport Rules

- Video: WebRTC only.
- Alerts, analytics, metadata, notifications: WebSocket or REST.
- WebSocket payloads must never include `frame`, `frame_base64`, `image`, `video`, `raw_frame`, or `face_image`.

## REST

### `GET /health`

Returns system health and privacy policy flags.

### `POST /api/classrooms/{classroom_id}/cameras`

Registers a camera on the edge server.

```json
{
  "camera_id": "cam-01",
  "classroom_id": "room-a",
  "rtsp_url": "rtsp://local-only"
}
```

### `GET /api/cameras/status`

Returns per-camera WebRTC status.

### `POST /api/webrtc/{camera_id}/offer`

Entry point for WebRTC SDP offer handling. Production deployments should connect this route to the aiortc implementation in `server/webrtc_server.py`.

### `POST /api/workflows/process-frame-metadata`

Runs the LangGraph workflow over structured metadata from the edge CV pipeline.

### `GET /api/alerts`

Returns alert history.

### `GET /api/analytics/dashboard`

Returns alert counts, high-risk counts, and camera status.

### `GET /api/agents/crew`

Returns CrewAI agent responsibilities.

## WebSocket

### `/ws/metadata`

Allowed message categories:

- alerts
- analytics
- metadata
- notifications

The server rejects video/image fields.
