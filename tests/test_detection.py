def test_detection_structure_exists():
    from pathlib import Path
    assert Path('backend/agents/detection_agent.py').exists()
