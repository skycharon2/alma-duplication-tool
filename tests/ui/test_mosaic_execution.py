"""Browser upload through the real Mosaic backend and retained report, without network."""
import io
import json
import re
from pathlib import Path

import pytest

from alma_duplicate.ui import create_app
from alma_duplicate.mosaic_region_acceptance import MetadataBundleClient

ROOT = Path(__file__).parents[1] / 'fixtures/archive/s_region_acceptance_2026_10_26/line'
ROW = 'w123456abcdef'


def form():
    return dict(target_kind='FIXED', geometry='MOSAIC', target_name='NGC253_CASE2_SYNTHETIC_LINE',
                setup_id='setup-1', setup_complete='on', intents='LINE', angular='0.07',
                rows=ROW, sources='ARCHIVE', mosaic_array='12m', mosaic_complete='on',
                mosaic_fixed_icrs='on', **{ROW+'_id':'line-0', ROW+'_center':'690.8931792321085',
                ROW+'_center_kind':'SKY', ROW+'_mode':'FDM', ROW+'_resolution':'10', ROW+'_rms':'8'})


@pytest.fixture
def browser(monkeypatch):
    import requests
    from alma_duplicate import mosaic_backend
    from alma_duplicate.clients import archive_mirrors
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **k: pytest.fail('Network forbidden'))
    monkeypatch.setattr(archive_mirrors, 'MirroredArchiveClient',
                        lambda **kw: MetadataBundleClient(ROOT / 'metadata'))
    calls = []
    def discover(proposed, output, **kwargs):
        calls.append((proposed, kwargs))
        return json.loads((ROOT / 'selection/discovery.json').read_text())
    monkeypatch.setattr(mosaic_backend, 'discover_candidates', discover)
    app = create_app(dict(TESTING=True, LIVE_ARCHIVE=True, LIVE_AQ=True, REPORT_DIRECTORY=None,
                          OFFLINE_ARCHIVE_REPLAY=None))
    yield app.test_client(), calls
    app.extensions['assessment_runs'].close()


def upload(client):
    raw = json.loads((ROOT/'proposed.json').read_text())['raw_text'].encode()
    response = client.post('/proposed', data=form() | dict(action='preview-pointings',
        ot_pointings=(io.BytesIO(raw), 'ngc253.txt')))
    return re.search(r'name="mosaic_upload_token" value="([a-f0-9]+)"', response.text).group(1)


@pytest.mark.parametrize('connection', ['AUTO', 'EAST_ASIA'])
def test_upload_to_real_backend_report_and_downloads(browser, connection):
    client, calls = browser
    token = upload(client)
    response = client.post('/proposed', data=form() | dict(action='assess',
                          mosaic_upload_token=token, archive_connection=connection, ra='invalid', dec='invalid'))
    assert response.status_code == 303, response.text
    url = response.headers['Location']
    page = client.get(url)
    assert page.status_code == 200
    assert 'Mosaic assessment' in page.text and 'POS-MOSAIC' in page.text
    report = client.get(url+'/download/report').json
    assert report['schema_version'] == 'submitted_line_mosaic_search_report_1'
    assert report['preparation']['status'] == 'NOT_REQUIRED'
    assert len(report['candidates']) == 2
    assert report['proposed']['row_count'] == 3
    contexts = [c for candidate in report['candidates'] for c in candidate['evaluation']['contexts']]
    assert any(b['truth'] == 'TRUE' for c in contexts for b in c['branches'])
    retained = client.get(url+'/download/request').json
    assert retained['request']['position'] is None
    assert len(retained['mosaic_pointings']['points']) == 3
    from alma_duplicate.ui.runs import ARCHIVE_CONNECTIONS
    assert calls[0][1]['origins'] == ARCHIVE_CONNECTIONS[connection]
    assert client.get(url+'?page=2').status_code == 404
    assert client.get(url+'/visualization').status_code == 404
    assert client.get('/reports').status_code == 200


@pytest.mark.parametrize('change', [dict(mosaic_array='TP'), dict(target_name=''), dict(mosaic_upload_token='invalid'), dict(angular='bad')])
def test_invalid_mosaic_never_queries(browser, change):
    client, calls = browser
    token = upload(client)
    response = client.post('/proposed', data=form() | dict(action='assess', mosaic_upload_token=token) | change)
    assert response.status_code == 200
    assert not calls


def test_failed_discovery_remains_incomplete_and_progress_finishes(browser, monkeypatch):
    client, _ = browser
    from alma_duplicate import mosaic_backend
    def failed(*args, **kwargs):
        discovery = json.loads((ROOT/'selection/discovery.json').read_text())
        discovery.update(status='INCOMPLETE', candidates=[])
        return discovery
    monkeypatch.setattr(mosaic_backend, 'discover_candidates', failed)
    token = upload(client)
    progress = 'a' * 32
    response = client.post('/proposed', data=form() | dict(action='assess', mosaic_upload_token=token),
                           headers={'X-Assessment-Progress': progress})
    url = response.json['report_url']
    report = client.get(url+'/download/report').json
    assert report['assessment_status'] == 'INCOMPLETE'
    assert report['absence_interpretation'] == 'NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION'
    assert 'INCOMPLETE' in client.get(url).text
    state = client.get('/assessment-progress/'+progress).json
    assert state['status'] == 'COMPLETED'  # The report exists; science is still incomplete.
    assert state['stages']['archive_ready']['completed'] == 0


def test_metadata_failure_is_retained_and_candidates_are_paginated(browser, monkeypatch):
    client, _ = browser
    from alma_duplicate import mosaic_backend
    def many(*args, **kwargs):
        discovery = json.loads((ROOT/'selection/discovery.json').read_text())
        discovery['candidates'] = [dict(member_ous_uid=f'uid://missing/{i}', source_name='missing')
                                   for i in range(21)]
        return discovery
    monkeypatch.setattr(mosaic_backend, 'discover_candidates', many)
    token = upload(client)
    response = client.post('/proposed', data=form() | dict(action='assess', mosaic_upload_token=token))
    url = response.headers['Location']
    first, second = client.get(url+'?view=all').text, client.get(url+'?view=all&page=2').text
    assert 'Page 1 of 2' in first and 'Page 2 of 2' in second
    assert 'missing/20' not in first and 'missing/20' in second
    report = client.get(url+'/download/report').json
    assert len(report['candidates']) == 21
    assert all(c['status'] == 'INCOMPLETE' for c in report['candidates'])


def test_normal_form_without_inventory_uses_v2_and_retains_exact_report(browser):
    client, calls = browser
    token = upload(client)
    response = client.post('/proposed', data=form() | dict(
        action='assess', setup_complete='', mosaic_upload_token=token))
    assert response.status_code == 303
    url = response.headers['Location']
    original = client.get(url + '/download/report').data
    report = json.loads(original)
    retained = client.get(url + '/download/request').json
    assert retained['request'] == report['request']['raw']
    assert retained['request']['physical_spw_inventory_complete'] is False
    assert 'setup_complete' not in retained['request']
    assert len(retained['request']['line_requirements']) == 1
    assert retained['request']['physical_spw_evidence'] == []
    contexts = report['candidates'][0]['evaluation']['contexts']
    assert [c['branches'][0]['truth'] for c in contexts] == ['TRUE', 'FALSE', 'FALSE', 'FALSE']
    assert all(c['branches'][0]['method_version'] == 'archive_line_context_submitted_or_2'
               for c in contexts)
    for view in ('all', 'matching', 'not_met', 'review'):
        page = client.get(url + '?view=' + view)
        assert page.status_code == 200
    assert 'Archive Member OUS' in client.get(url).text
    assert 'Archive SPW 25' in client.get(url).text
    assert client.get(url + '/download/report').data == original
    assert len(calls) == 1


def test_upload_is_sufficient_without_separate_confirmations(browser):
    client, calls = browser
    token = upload(client)
    data = form() | dict(action='assess', mosaic_upload_token=token)
    data.pop('mosaic_complete', None)
    data.pop('mosaic_fixed_icrs', None)
    response = client.post('/proposed', data=data)
    assert response.status_code == 303
    assert calls
