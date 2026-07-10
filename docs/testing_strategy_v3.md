# Testing Strategy V3

## Unit Tests

- Detection validation and duplicate removal.
- Seat mapping and stable identity assignment.
- Face, gaze, and pose semantic signal thresholds.
- Temporal behavior windows: alert only after repeated suspicious frames.
- Risk scoring thresholds and history bonuses.
- Evidence acceptance/rejection thresholds.
- WebSocket metadata-only policy.

## Integration Tests

- Full LangGraph workflow with synthetic tracks and metadata.
- FastAPI route tests for health, camera status, alerts, and metadata workflow.
- WebRTC endpoint contract tests.
- Supabase schema migration validation.

## Performance Tests

- Synthetic 3-6 camera input with 60+ tracks.
- Queue behavior under overload: stale frames must drop.
- Gemini batch queue latency.
- Report generation under large alert timelines.

## Privacy/Security Tests

- Verify no raw video fields pass through WebSocket.
- Verify Gemini input JSON excludes images and video.
- Verify RLS is enabled on production tables.
- Verify audit events are written for report and evidence access.
