"""Human-in-the-loop invigilator assistant agent."""

class InvigilatorAgent:
    def recommend(self, alert: dict):
        return {"action": "review", "message": "Human invigilator review required", "alert": alert}
