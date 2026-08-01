def test_tracking_structure_exists():
    from pathlib import Path
    assert Path('backend/agents/tracking_agent.py').exists()
