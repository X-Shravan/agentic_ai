# Enterprise Dashboard Blueprint

## Pages

- `/`: live operations overview.
- `/classrooms`: classroom and camera management.
- `/classrooms/[id]`: live camera grid, seat map, risk heatmap, camera status.
- `/alerts`: alert timeline and filtering.
- `/evidence/[id]`: verified evidence viewer.
- `/reports`: PDF report index and generation status.
- `/system`: health, GPU, queues, WebRTC peers, Redis/Celery status.

## Components

- LiveCameraGrid: subscribes to WebRTC streams.
- SeatMap: maps students to A1/B2-style seats.
- RiskHeatmap: visualizes risk by seat.
- AlertTimeline: consumes `/ws/metadata` for alert events.
- EvidenceViewer: displays verified screenshots/clips from storage.
- AIExplanationPanel: shows Gemini structured reasoning.
- SystemHealthCards: reports camera, queue, GPU, database health.

## UI Stack

- Next.js App Router
- React Server Components where suitable
- Tailwind CSS
- Shadcn UI
- Framer Motion for non-blocking UI transitions
- Supabase Auth for RBAC-aware sessions

## Client Transport

- Use WebRTC peer connections for video.
- Use WebSocket only for metadata.
- Use REST for reports, historical analytics, and configuration.
