"""Existing Mosaic form -> shared Queue source -> Custom backend -> retained report."""
import io
import re
from pathlib import Path

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.ui import create_app
from tests.integration.test_queue_custom_science import candidate
from tests.ui.test_mosaic_ot_preview import OT
from tests.unit.test_queue_csv_parser import _records, _render


def csv_bytes(changes=None):
    parsed = candidate({'Project Code':'2024.1.00001.S', 'Polarization':'DOUBLE',
        'Req.Sensitivity':'0.001', 'Spec.Res. SPW 1':'0.9765625'} | (changes or {}))
    return _render(_records()[:41] + [list(r.raw_values) for r in parsed.raw_rows])


def form(*, version='2', intents=('CONTINUUM',)):
    row = 'w123456abcdef'
    data = MultiDict(dict(target_kind='FIXED', geometry='MOSAIC', target_name='Custom test',
        setup_id='setup-1', angular='.45', sources='QUEUE', mosaic_array='12m',
        representative='230', representative_kind='SKY',
        aggregate='.1', continuum_setup_declaration='on', normal_form_version=version))
    data.setlist('intents', intents)
    if 'LINE' in intents:
        data.update(dict(rows=row, **{row+'_id':'line-1', row+'_center':'226',
            row+'_center_kind':'SKY', row+'_mode':'FDM', row+'_resolution':'20', row+'_rms':'.1'}))
    return data


@pytest.fixture
def browser(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **k: pytest.fail('network'))
    path = tmp_path/'queue.csv'
    path.write_bytes(csv_bytes())
    app = create_app(dict(TESTING=True, REPORT_DIRECTORY=None, OFFLINE_QUEUE_CSV=str(path),
        MANAGED_QUEUE_ROOT=None, OFFLINE_ARCHIVE_REPLAY=None, LIVE_ARCHIVE=False, LIVE_AQ=False))
    yield app, app.test_client()
    app.extensions['assessment_runs'].close()


def submit(client, data):
    upload = data.copy()
    upload['action'] = 'preview-pointings'
    upload['ot_pointings'] = (io.BytesIO(OT), 'proposed.txt')
    response = client.post('/proposed/mosaic', data=upload)
    assert response.status_code == 200
    token = re.search(r'name="mosaic_upload_token" value="([a-f0-9]+)"', response.text)
    assert token, response.text
    data = data.copy()
    data['mosaic_upload_token'] = token.group(1)
    data['action'] = 'assess'
    return client.post('/proposed/mosaic', data=data)


@pytest.mark.parametrize('version,intents', [('', ('CONTINUUM',)), ('2', ('CONTINUUM',)),
    ('2', ('LINE',)), ('2', ('LINE','CONTINUUM'))])
def test_existing_form_runs_queue_without_archive(browser, version, intents):
    app, client = browser
    response = submit(client, form(version=version, intents=intents))
    assert response.status_code == 303, response.text
    report = client.get(response.location+'/download/report').json
    assert report['schema_version'] == 'queue_mosaic_assessment_1'
    assert report['assessment_status'] == 'COMPLETED'
    assert set(report['sources']) == {'QUEUE'}
    assert report['geometry_reports']['CUSTOM_POINTING']['candidates'][0]['science']['matching_arrays_by_intent'] == {intents[0]: [7., 12.]}
    if len(intents) == 2:
        first_page = client.get(response.location).text
        sibling = re.search(r'href="([^"]+)">Continuum</a>', first_page).group(1)
        assert sibling != response.location
        assert response.location in client.get(sibling).text
        continuum = client.get(sibling + '/download/report').json
        assert continuum['geometry_reports']['CUSTOM_POINTING']['candidates'][0]['science']['matching_arrays_by_intent'] == {'CONTINUUM': [7., 12.]}
    assert report['proposed']['sensitivity_basis'] == 'PER_POINTING'
    assert report['proposed']['setup_id'] == 'setup-1'
    if version == '2':
        assert report['scientific_request']['line_input_contract'] == 'SEPARATE_OBSERVATION_REQUIREMENTS_V2'
        if 'LINE' in intents:
            assert report['geometry_reports']['CUSTOM_POINTING']['candidates'][0]['science']['variants'][0]['line_pairing']['proposed_enumeration_complete']
    page = client.get(response.location)
    assert page.status_code == 200
    assert 'Matching candidates' in page.text
    assert page.text.count('Results in this search') == 1
    assert 'matching Queue candidate configurations' in page.text
    assert 'href="#queue-' in page.text
    for label in ('Results in this search', 'Matching comparisons',
                  'Your requirement', 'Candidate comparison', 'Result and explanation',
                  'How this comparison was made', 'Half-power radius', '3/3 inside'):
        assert label in page.text
    assert '7.0 m' in page.text and '12.0 m' in page.text and 'POS-MOSAIC' in page.text
    assert client.get(response.location+'?view=all').status_code == 200
    assert client.get(response.location+'?page=2').status_code == 404
    assert client.get(response.location+'/visualization').status_code == 404
    assert client.get('/reports').status_code == 200
    retained = client.get(response.location+'/download/request').json
    assert retained['search_options']['sources'] == ['QUEUE']
    assert len(retained['mosaic_pointings']['points']) == 3


def test_source_choice_roundtrip_does_not_read_csv(browser, monkeypatch):
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient
    monkeypatch.setattr(QueueCsvClient, 'load', lambda *a: pytest.fail('source loaded'))
    _, client = browser
    data = form(); data['action'] = 'scope'
    response = client.post('/proposed/mosaic', data=data)
    assert 'name="sources" value="QUEUE" checked' in response.text
    assert 'name="mosaic_per_pointing_rms"' not in response.text
    data['action'] = 'download'
    assert client.post('/proposed/mosaic', data=data).json['search_options']['sources'] == ['QUEUE']


def test_unreadable_csv_gets_source_failure_report(browser):
    app, client = browser
    Path(app.config['OFFLINE_QUEUE_CSV']).unlink()
    response = submit(client, form())
    assert response.status_code == 303
    report = client.get(response.location+'/download/report').json
    assert report['assessment_status'] == 'SOURCES_UNAVAILABLE'
    assert report['sources']['QUEUE']['status'] == 'FAILED'
    assert 'unavailable or incomplete' in client.get(response.location).text


@pytest.mark.parametrize("intents", [("CONTINUUM",), ("LINE", "CONTINUUM")])
def test_managed_queue_source_uses_existing_pin_and_provenance(tmp_path, monkeypatch, intents):
    from tests.ui.test_managed_queue import acquired, NOW
    from alma_duplicate.storage.queue_active import QueueActiveRegistry
    from alma_duplicate.ui import runs
    first = acquired(tmp_path, csv_bytes())
    registry = QueueActiveRegistry(tmp_path, clock=lambda: NOW)
    registry.activate(first['source_id'], first['run_id'], reason='Reviewed')
    later = acquired(tmp_path, csv_bytes().replace(b'2026 March 3.', b'2026 March 10.'))
    original = runs.pin_active_queue
    pins = []
    def pin(root):
        pins.append(root)
        selected = original(root)
        registry.activate(later['source_id'], later['run_id'], reason='Later')
        return selected
    monkeypatch.setattr(runs, 'pin_active_queue', pin)
    app = create_app(dict(TESTING=True, REPORT_DIRECTORY=None, OFFLINE_QUEUE_CSV=None,
        MANAGED_QUEUE_ROOT=str(tmp_path), OFFLINE_ARCHIVE_REPLAY=None, LIVE_ARCHIVE=False, LIVE_AQ=False))
    client = app.test_client()
    response = submit(client, form(intents=intents))
    assert response.status_code == 303, response.text
    report = client.get(response.location+'/download/report').json
    assert report['sources']['QUEUE']['managed_snapshot']['source_id'] == first['source_id']
    assert report['sources']['QUEUE']['snapshot']['snapshot_sha256'] == first['snapshot_sha256']
    with client.session_transaction() as session:
        ids = session["report_history"]
    assert len(ids) == len(intents)
    assert len(pins) == 1
    for report_id in ids:
        saved = client.get("/runs/" + report_id + "/download/report").json
        assert saved["sources"]["QUEUE"]["managed_snapshot"]["source_id"] == first["source_id"]
        assert saved["sources"]["QUEUE"]["snapshot"]["snapshot_sha256"] == first["snapshot_sha256"]
    assert registry.current()['source_id'] == later['source_id']
    app.extensions['assessment_runs'].close()
