"""CrewAI crew assembly helpers."""
from backend.crewai.agents import AGENT_ROLES
from backend.crewai.tasks import TASKS

def build_crew_config():
    return {"agents": AGENT_ROLES, "tasks": TASKS}
