def test_pose_structure_exists():
    from pathlib import Path
    assert Path('backend/cv/pose_detector.py').exists()
