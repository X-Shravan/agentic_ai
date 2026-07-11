def test_report_builder_returns_ready_status():
    from backend.reports.report_builder import ReportBuilder
    assert ReportBuilder().build('session-1', [])['status'] == 'ready'
