"""The manual browser preview must remain offline and yield usable reports."""
import json

from scripts.preview_multi_source import preview_app


def test_preview_ignores_live_environment_and_retains_matching_reports(monkeypatch):
    import requests
    def no_network(*args, **kwargs):
        raise AssertionError('Preview attempted external source access')
    monkeypatch.setattr(requests.sessions.Session, 'request', no_network)
    for name in ('ALMA_UI_AUTO_QUEUE', 'ALMA_UI_LIVE_ARCHIVE', 'ALMA_UI_LIVE_ARCHIVE_AQ'):
        monkeypatch.setenv(name, '1')
    monkeypatch.setenv('ALMA_UI_QUEUE_SNAPSHOT_ROOT', '/missing/managed-queue')
    monkeypatch.setenv('ALMA_UI_ARCHIVE_ARRAY_EVIDENCE', '/missing/evidence')
    app = preview_app()
    try:
        client = app.test_client()
        entry = client.get('/acceptance/batch')
        assert entry.status_code == 302
        assert client.get(entry.location).status_code == 200
        manifest = client.get(entry.location + '/download/manifest').json
        assert manifest['execution_complete'] and len(manifest['sources']) == 2
        for source in manifest['sources']:
            assert len(source['reports']) == 2
            for report in source['reports']:
                assert report['availability'] == 'AVAILABLE'
                url = '/runs/' + report['run_id']
                document = json.loads(client.get(url + '/download/report').data)
                assert all(item['status'] == 'COMPLETED' for item in document['sources'].values())
                assert document['context_evaluations']
                assert client.get(url + '/visualization').status_code == 200
        assert app.test_client().get(entry.location).status_code == 404
    finally:
        app.extensions['assessment_runs'].close()
        app.extensions['source_uploads'].close()
        app.extensions['mosaic_uploads'].close()
