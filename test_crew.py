import sys
import os
import traceback

sys.path.insert(0, os.getcwd())

try:
    print("Importing crewai...")
    from crewai import Agent, Task, Crew, Process
    print("✅ CrewAI imported successfully!")
    
    from backend.crewai.agents import AGENTS
    print("✅ Loaded agents:", list(AGENTS.keys()))
    
    # Try constructing a basic Crew
    print("Building test crew...")
    test_agent = Agent(
        role="Test Role",
        goal="Test Goal",
        backstory="Test Backstory",
        verbose=True
    )
    test_task = Task(
        description="Test Task Description",
        expected_output="Test Output",
        agent=test_agent
    )
    crew = Crew(
        agents=[test_agent],
        tasks=[test_task],
        process=Process.sequential
    )
    print("✅ Crew built successfully!")
    
except Exception as e:
    print("❌ CrewAI test failed:")
    traceback.print_exc()
