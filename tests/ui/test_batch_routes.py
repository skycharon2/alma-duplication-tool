"""Owner-scoped source upload and real offline batch browser acceptance."""
from io import BytesIO
import json

from bs4 import BeautifulSoup
import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.ui import create_app
from alma_duplicate.ui.runs import BrowserAssessment
from tests.ui.test_batch_assessment import RAW, values
from tests.ui.test_batch_requests import ROW
from tests.ui.test_runs import config


@pytest.fixture
def client():
    app = create_app(config())
    yield app.test_client()
    app.extensions['assessment_runs'].close()
    app.extensions['source_uploads'].close()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **kw: pytest.fail('Network invoked'))


def hidden(response, name):
    tag = BeautifulSoup(response.data, 'html.parser').find('input', attrs={'name': name})
    return tag['value'] if tag else None


def fields(client):
    page = client.get('/proposed/batch')
    return values() | dict(rows=[ROW], batch_csrf=hidden(page, 'batch_csrf'),
                           submission_token=hidden(page, 'submission_token'))


def upload(client, data=None, raw=RAW, format='csv'):
    data = data or fields(client)
    page = client.post('/proposed/batch', data=data | dict(action='preview-sources',
        source_format=format, source_list=(BytesIO(raw), 'targets.' + format)))
    return page, data | dict(source_upload_token=hidden(page, 'source_upload_token'),
                             submission_token=hidden(page, 'submission_token'))


def test_preview_and_validation_are_offline_and_keep_science(client, monkeypatch):
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Assessment invoked'))
    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', lambda *a: pytest.fail('Queue accessed'))
    page, data = upload(client)
    assert page.status_code == 200 and b'2 targets' in page.data
    assert b'name="ra"' not in page.data and b'name="redshift"' not in page.data
    assert b'name="source_upload_token"' in page.data
    assert b'name="angular"' in page.data and b'value="0.3"' in page.data
    for action in ('validate', 'purpose', 'scope'):
        page = client.post('/proposed/batch', data=data | dict(action=action))
        assert page.status_code == 200 and b'first' in page.data
        assert hidden(page, 'source_upload_token') == data['source_upload_token']
    page = client.post('/proposed/batch', data=data | dict(action='validate'))
    assert b'All targets ready: <strong>Yes' in page.data


@pytest.mark.parametrize('v2', [False, True])
def test_real_run_overview_exports_history_and_existing_report_links(client, v2, monkeypatch):
    page, data = upload(client, fields(client) | values(v2))
    response = client.post('/proposed/batch', data=data | dict(action='assess'))
    assert response.status_code == 303, response.text
    location = response.location
    assert location.startswith('/batches/')
    # Reading or downloading must not rerun scientific assessment.
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Read triggered assessment'))
    overview = client.get(location)
    assert overview.status_code == 200
    assert b'Batch overview' in overview.data and b'Shared scientific requirements' in overview.data
    manifest = client.get(location + '/download/manifest')
    assert manifest.is_json and 'attachment' in manifest.headers['Content-Disposition']
    assert manifest.json['execution_complete'] and len(manifest.json['sources']) == 2
    soup = BeautifulSoup(overview.data, 'html.parser')
    links = [a['href'] for a in soup.select('.batch-table a')]
    assert len(links) == 8
    for link in links:
        assert client.get(link).status_code == 200, link
    for source in manifest.json['sources']:
        for report in source['reports']:
            assert client.get('/runs/' + report['run_id'] + '/download/request').is_json
    history = client.get('/reports')
    assert history.text.count('Multi-source assessment · 2 targets') == 1
    with client.session_transaction() as session:
        assert session['batch_history'] == [location.rsplit('/', 1)[1]]
        assert not session.get('report_history')
    other = client.application.test_client()
    assert other.get(location).status_code == 404
    assert other.get(location + '/download/manifest').status_code == 404
    assert b'2 targets' not in other.get('/reports').data


def test_invalid_rows_and_failed_replacement_never_run_old_upload(client, monkeypatch):
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Assessment invoked'))
    page, data = upload(client, raw=b'name,ra,dec,redshift\nblue,0,0,-0.001\nzero,1,90,0\nbad,360,0,-1')
    assert b'Correct this row' in page.data and b'bad' in page.data
    rows = BeautifulSoup(page.data, 'html.parser').select('.batch-table tbody tr')
    assert 'Valid ICRS position' in rows[0].text and 'Valid blueshift' in rows[0].text
    assert 'Valid redshift' in rows[1].text
    assert 'Valid ICRS position' not in rows[2].text
    assert 'Require a finite numeric redshift z > -1.' in rows[2].text
    response = client.post('/proposed/batch', data=data | dict(action='assess'))
    assert b'Correct all source-list errors' in response.data
    page, data = upload(client)
    old = data['source_upload_token']
    response = client.post('/proposed/batch', data=data | dict(action='preview-sources',
        source_format='csv', source_list=(BytesIO(b'wrong header'), 'bad.csv')))
    assert hidden(response, 'source_upload_token') is None
    response = client.post('/proposed/batch', data=data | dict(action='assess', source_upload_token=old))
    assert b'Upload your source list again' in response.data


def test_upload_owner_expiry_removal_and_limits(client):
    page, data = upload(client)
    other = client.application.test_client()
    foreign = fields(other) | dict(source_upload_token=data['source_upload_token'], action='validate')
    assert b'Upload your source list again' in other.post('/proposed/batch', data=foreign).data
    removed = client.post('/proposed/batch', data=data | dict(action='remove-sources'))
    assert hidden(removed, 'source_upload_token') is None
    assert b'Upload your source list again' in client.post('/proposed/batch', data=data | dict(action='validate')).data
    page, data = upload(client)
    store = client.application.extensions['source_uploads']
    now = store.clock()
    store.clock = lambda: now + store.ttl + 1
    assert b'Upload your source list again' in client.post('/proposed/batch', data=data | dict(action='validate')).data
    page, _ = upload(client, raw=b'x' * 100001)
    assert b'at most 100000 bytes' in page.data


def test_csrf_repeated_fields_and_scope_are_rejected(client):
    data = fields(client)
    for change in ({'batch_csrf': 'bad'}, {'batch_csrf': '非法'}, {'submission_token': 'bad'}, {'geometry': 'MOSAIC'}, {'target_kind': 'SUN'}, {'action': 'download'}):
        assert client.post('/proposed/batch', data=data | dict(action='validate') | change).status_code == 400
    repeated = MultiDict(data | dict(action='validate'))
    repeated.add('angular', '2')
    assert client.post('/proposed/batch', data=repeated).status_code == 400


def test_missing_rest_redshift_keeps_per_target_diagnostics(client):
    page, data = upload(client, fields(client) | values(kind='REST'), raw=RAW.replace(b',0\n', b',\n'))
    response = client.post('/proposed/batch', data=data | dict(action='assess'))
    assert response.status_code == 200
    assert b'second' in response.data and b'Needs input' in response.data
    assert hidden(response, 'source_upload_token') == data['source_upload_token']
    assert b'value="230.538"' in response.data


def test_progress_post_and_duplicate_run_preserve_one_batch(client, monkeypatch):
    page, data = upload(client)
    token = 'a' * 32
    response = client.post('/proposed/batch', data=data | dict(action='assess'), headers={'X-Assessment-Progress': token})
    assert response.is_json
    state = client.get('/batches/progress/' + token)
    assert state.json['status'] == 'COMPLETED'
    assert state.json['stages']['batch_finished']['batch_completed'] == 4
    assert client.application.test_client().get('/batches/progress/' + token).status_code == 404
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Duplicate assessment'))
    repeated = client.post('/proposed/batch', data=data | dict(action='assess'))
    assert repeated.location == response.json['report_url']


def test_failed_branches_and_evicted_reports_are_readable(client, monkeypatch):
    original = BrowserAssessment.assess
    count = []
    def fail_second(self, document):
        count.append(1)
        if len(count) == 2:
            raise ValueError('Source unavailable')
        return original(self, document)
    monkeypatch.setattr(BrowserAssessment, 'assess', fail_second)
    client.application.extensions['assessment_runs']._max_runs = 1
    page, data = upload(client)
    response = client.post('/proposed/batch', data=data | dict(action='assess'))
    page = client.get(response.location)
    assert page.status_code == 200
    assert b'Failed' in page.data and b'storage capacity limit' in page.data
    assert b'Removed to free storage' not in page.data
    assert page.text.count('Text report</a>') == 1
    store = client.application.extensions['assessment_runs']
    store.batches.close()
    assert client.get(response.location).status_code == 404


def test_names_are_escaped_and_manifest_is_json(client):
    raw = b'name,ra,dec\n<script>alert(1)</script>,201.365,-43.019'
    page, data = upload(client, raw=raw)
    assert b'<script>alert(1)</script>' not in page.data
    response = client.post('/proposed/batch', data=data | dict(action='assess'))
    page = client.get(response.location)
    assert b'<script>alert(1)</script>' not in page.data
    assert json.loads(client.get(response.location + '/download/manifest').data)


def test_txt_upload_and_science_edits_keep_upload_bytes(client):
    raw = b'name ra dec redshift\n"Target one" 201.365 -43.019 0.024'
    page, data = upload(client, raw=raw, format='txt')
    assert b'Target one' in page.data
    # A format dropdown edit only applies to the next upload.
    response = client.post('/proposed/batch', data=data | dict(action='validate', source_format='csv'))
    assert b'All targets ready: <strong>Yes' in response.data


def test_changed_inputs_after_submission_get_fresh_token_on_conflict(client):
    page, data = upload(client)
    assert client.post('/proposed/batch', data=data | dict(action='assess')).status_code == 303
    response = client.post('/proposed/batch', data=data | dict(action='assess', angular='0.4'))
    assert response.status_code == 200
    assert hidden(response, 'submission_token') != data['submission_token']
    assert hidden(response, 'source_upload_token') == data['source_upload_token']


def test_busy_upload_store_and_extra_files_fail_without_silent_reuse(client):
    page, data = upload(client)
    client.application.extensions['source_uploads'].capacity = 0
    response = client.post('/proposed/batch', data=data | dict(action='preview-sources',
        source_format='csv', source_list=(BytesIO(RAW), 'targets.csv')))
    assert b'Upload storage is busy' in response.data
    assert hidden(response, 'source_upload_token') is None
    client.application.extensions['source_uploads'].capacity = 64
    posted = MultiDict(fields(client) | dict(action='preview-sources', source_format='csv'))
    posted.add('source_list', (BytesIO(RAW), 'one.csv'))
    posted.add('source_list', (BytesIO(RAW), 'two.csv'))
    assert b'Choose one source-list file' in client.post('/proposed/batch', data=posted).data
