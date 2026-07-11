def test_evidence_manager_paths():
    from backend.evidence.manager import evidence_paths
    paths = evidence_paths('evt-1')
    assert {'screenshots', 'clips', 'metadata'} <= set(paths)
