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
def browser(monkeypatch, tmp_path):
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
    from tests.ui.test_queue_custom_mosaic import csv_bytes
    queue_file = tmp_path / "queue.csv"
    queue_file.write_bytes(csv_bytes())
    app = create_app(dict(OFFLINE_QUEUE_CSV=str(queue_file), TESTING=True, LIVE_ARCHIVE=True, LIVE_AQ=True, REPORT_DIRECTORY=None,
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

@pytest.mark.parametrize("intents", [["LINE"], ["LINE", "CONTINUUM"]])
def test_mosaic_both_sources_share_page_with_purpose_navigation(browser, intents):
    client, calls = browser
    data = form() | dict(sources=["ARCHIVE", "QUEUE"], mosaic_upload_token=upload(client),
                         normal_form_version="2", action="assess", intents=intents, aggregate="1",
                         representative="690", continuum_setup_declaration="on", setup_complete="")
    response = client.post("/proposed/mosaic", data=data)
    assert response.status_code == 303, response.text
    with client.session_transaction() as state:
        group, = state["mosaic_report_groups"]
    from bs4 import BeautifulSoup
    index = BeautifulSoup(client.get('/reports').text, 'html.parser')
    report_links = [a for a in index.find_all('a', href=True)
                    if a['href'].startswith('/runs/')]
    assert len(report_links) == 1
    assert set(group.values()) == {{"LINE": "Spectral line", "CONTINUUM": "Continuum"}[intent] + " · " + source for intent in intents for source in ("ARCHIVE", "QUEUE")}
    for key, label in group.items():
        url = "/runs/" + key
        page = client.get(url).text
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page, "html.parser")
        assert len(soup.find_all("html")) == 1
        assert soup.h1.get_text(strip=True) == 'Observation comparison'
        assert [node.get_text(strip=True) for node in soup.select('.report-page h2')
                if node.get_text(strip=True) in ('Results in this search', 'Matching candidates', 'Matching comparisons')] == [
                    'Results in this search', 'Matching candidates', 'Matching comparisons']
        assert soup.find('summary', string='Search scope and limitations')
        assert len(soup.select('#sources .source-retrieval-help > summary[title]')) == 2
        if label.startswith('Spectral line'):
            preparation = soup.select_one('.line-pair details.line-preparation')
            assert preparation and not preparation.has_attr('open')
            assert preparation.select_one('dl.calculation-facts > div > dt')
            assert 'Recorded pair status:' not in page
        for table in soup.select('table.comparison-table:has(tr[data-criterion])'):
            assert [th.get_text(strip=True) for th in table.select('thead > tr > th')[:4]] == [
                'Criterion', 'Your requirement', 'Candidate comparison', 'Result and explanation']
        assert page.count('Results in this search') == 1
        assert page.count('<h2>Matching candidates</h2>') == 1
        assert 'matching Queue candidate configurations' in page
        assert 'matching Archive Member' in page
        nav = soup.select_one('nav[aria-label="Assessment reports"]')
        if len(intents) == 2:
            assert [a.get_text(strip=True) for a in nav.find_all("a")] == ["Spectral line", "Continuum"]
            assert len(nav.select('[aria-current="page"]')) == 1
        else:
            assert nav is None
        assert soup.select_one('nav[aria-label="Mosaic assessment reports"]') is None
        source = label.split()[-1].upper()
        assert client.get(url + "/download/request").json["search_options"]["sources"] == [source]
        assert client.get(url + "/download/report").status_code == 200
    assert len(calls) == len(intents)


@pytest.mark.parametrize('discovery_status, expected', [
    ('COMPLETED', '0 matching Archive Members.'),
    ('INCOMPLETE', 'Archive results unavailable or incomplete.'),
])
def test_combined_mosaic_distinguishes_empty_and_incomplete_archive(browser, monkeypatch, discovery_status, expected):
    from bs4 import BeautifulSoup
    from alma_duplicate import mosaic_backend

    client, _ = browser
    discovery = json.loads((ROOT / 'selection/discovery.json').read_text())
    discovery.update(status=discovery_status, candidates=[])
    monkeypatch.setattr(mosaic_backend, 'discover_candidates', lambda *args, **kwargs: discovery)
    data = form() | dict(sources=['ARCHIVE', 'QUEUE'], mosaic_upload_token=upload(client), action='assess')
    response = client.post('/proposed/mosaic', data=data)
    assert response.status_code == 303
    summary = BeautifulSoup(client.get(response.location).text, 'html.parser').select_one('.matching-sources')
    assert expected in summary.get_text(' ', strip=True)


def test_saved_mosaic_explore_keeps_source_pages_and_intents_separate(browser):
    from bs4 import BeautifulSoup

    client, calls = browser
    data = form() | dict(sources=['ARCHIVE', 'QUEUE'], mosaic_upload_token=upload(client),
                         normal_form_version='2', action='assess', intents=['LINE', 'CONTINUUM'],
                         aggregate='1', representative='690', continuum_setup_declaration='on', setup_complete='')
    response = client.post('/proposed/mosaic', data=data)
    assert response.status_code == 303
    with client.session_transaction() as state:
        group, = state['mosaic_report_groups']
    searches = len(calls)
    for run_id, label in group.items():
        url = f'/runs/{run_id}'
        report = BeautifulSoup(client.get(url).data, 'html.parser')
        link = report.find('a', string='Explore this report')['href']
        result = client.get(link)
        assert result.status_code == 200
        page = BeautifulSoup(result.data, 'html.parser')
        back = page.find('a', string='Back to text report')
        assert client.get(back['href']).status_code == 200
        assert page.find('summary', string='Submitted Mosaic pointings (3)')
        assert {nav.get('aria-label') for nav in page.select('nav[aria-label$=" comparisons"]')} == {
            'Archive comparisons', 'Queue comparisons'}
        rows = page.select('[data-row]')
        if label.startswith('Spectral line'):
            assert rows and all('LINE' in row.get_text() for row in rows)
        assert not page.select('svg[aria-label*="illustrative"]')
        assert client.get(url + '/mosaic-visualization?page=999').status_code == 404
    assert len(calls) == searches
