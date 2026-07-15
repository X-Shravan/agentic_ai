"""Report agent for exam summaries and evidence reports."""

class ReportAgent:
    def build_summary(self, session_id: str, events: list[dict]):
        return {"session_id": session_id, "event_count": len(events), "events": events}
