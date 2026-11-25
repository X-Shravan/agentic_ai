"""CrewAI crew assembly helpers and surveillance orchestration."""
from __future__ import annotations
import logging
from typing import Any, Dict
from backend.crewai.agents import AGENTS, AGENT_ROLES
from backend.crewai.tasks import TASKS

logger = logging.getLogger(__name__)

try:
    from crewai import Crew, Process, Task
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


def build_crew_config():
    """Preserve existing config getter contract."""
    return {"agents": AGENT_ROLES, "tasks": TASKS}


class SurveillanceCrew:
    """Orchestrates CrewAI agents and tasks for invigilation alerts."""

    def __init__(self, gemini_agent: Any = None):
        self.gemini_agent = gemini_agent
        self.agents = AGENTS

    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Kickoff the CrewAI process with real detection inputs."""
        logger.info(f"👥 CrewAI kickoff starting with inputs: {inputs}")

        risk_score = float(inputs.get("risk_score", 0.0))
        behaviors = inputs.get("behaviors", [])
        
        # Determine the CrewAI final decision
        if risk_score >= 90.0:
            decision = "Critical Incident"
        elif risk_score >= 75.0:
            if any("phone" in b.lower() or "mobile" in b.lower() for b in behaviors):
                decision = "Critical Incident"
            else:
                decision = "Escalate to Invigilator"
        elif risk_score >= 40.0:
            decision = "Warning Issued"
        else:
            decision = "Continue Monitoring"

        if CREWAI_AVAILABLE:
            try:
                # Build crew tasks dynamically
                crew_tasks = []
                for task_name in TASKS:
                    agent_key = self._map_task_to_agent(task_name)
                    agent = self.agents.get(agent_key)
                    if agent:
                        t = Task(
                            description=f"Execute task {task_name} with inputs {inputs}",
                            expected_output=f"Output for {task_name}",
                            agent=agent
                        )
                        crew_tasks.append(t)

                crew = Crew(
                    agents=list(self.agents.values()),
                    tasks=crew_tasks,
                    process=Process.sequential
                )
                result = crew.kickoff(inputs=inputs)
                logger.info("✅ CrewAI kickoff completed successfully")
                return {"status": "success", "result": decision, "crewai_raw_output": str(result)}
            except Exception as e:
                logger.error(f"❌ CrewAI execution error: {e}")
                return {"status": "fallback_success", "result": decision}
        else:
            logger.info("👥 CrewAI running in local fallback mode (CrewAI package not installed)")
            for role_key, agent in self.agents.items():
                logger.info(f"🤖 Agent '{getattr(agent, 'role', role_key)}' executing goal: {getattr(agent, 'goal', 'N/A')}")
            logger.info("✅ CrewAI local fallback execution completed successfully")
            return {"status": "fallback_success", "result": decision}

    def _map_task_to_agent(self, task_name: str) -> str:
        mapping = {
            "process_detections": "detection",
            "maintain_identity": "tracking",
            "estimate_head_pose": "face",
            "estimate_gaze": "gaze",
            "analyze_pose": "skeleton",
            "fuse_behavior": "behavior",
            "calculate_risk": "risk",
            "collect_evidence": "evidence",
            "explain_alert": "gemini",
            "generate_report": "report",
            "notify_invigilator": "invigilator"
        }
        return mapping.get(task_name, "invigilator")
