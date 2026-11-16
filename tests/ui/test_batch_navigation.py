"""Saved batch navigation preserves source, purpose and view independently."""
from bs4 import BeautifulSoup
import pytest

from tests.ui.test_batch_routes import client as browser_fixture, upload, fields
from tests.ui.test_batch_assessment import values
from alma_duplicate.ui.runs import BrowserAssessment

client = browser_fixture


def batch(client, **changes):
    _, data = upload(client, fields(client) | values() | changes)
    response = client.post('/proposed/batch', data=data | dict(action='assess'))
    assert response.status_code == 303
    return response.location, client.get(response.location + '/download/manifest').json


def nav(client, url):
    response = client.get(url)
    return response, BeautifulSoup(response.data, 'html.parser').select_one('.batch-navigation')


@pytest.mark.parametrize('visual', [False, True])
@pytest.mark.parametrize('purpose', ['LINE', 'CONTINUUM'])
def test_target_and_purpose_navigation_preserves_mode(client, monkeypatch, visual, purpose):
    location, manifest = batch(client)
    def report(index, purpose):
        return next(r['run_id'] for r in manifest['sources'][index]['reports'] if r['purpose'] == purpose)
    first, second = report(0, purpose), report(1, purpose)
    other = report(0, 'CONTINUUM' if purpose == 'LINE' else 'LINE')
    suffix = '/visualization' if visual else ''
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('navigation reran assessment'))
    response, navigation = nav(client, '/runs/' + first + suffix)
    assert response.status_code == 200 and navigation
    assert 'Target 1 of 2' in navigation.text and 'First target' in navigation.text
    links = {a.get_text(' ', strip=True): a['href'] for a in navigation.select('a')}
    assert links['Back to batch overview'] == location + '#source-line-2'
    assert links['Next target: second'] == '/runs/' + second + suffix
    assert '/runs/' + other + suffix in links.values()
    assert links['Text report'] == '/runs/' + first
    assert links['Visualization'] == '/runs/' + first + '/visualization'
    _, next_nav = nav(client, links['Next target: second'])
    assert 'Target 2 of 2' in next_nav.text and 'Last target' in next_nav.text
    assert next_nav.find('a', string='Previous target: first')['href'] == '/runs/' + first + suffix
    # New targets start at their own first page, without carrying old filters.
    assert all('?' not in value for value in links.values())
    assert 'id="source-line-2"' in client.get(location).text


def test_unavailable_sibling_links_to_status_without_switching_purpose(client, monkeypatch):
    original = BrowserAssessment.assess
    def fail_line(self, document):
        if document['request']['target_name'] == 'second' and document['request']['intents'] == ['LINE']:
            raise ValueError('Unavailable LINE branch')
        return original(self, document)
    monkeypatch.setattr(BrowserAssessment, 'assess', fail_line)
    location, manifest = batch(client)
    first = manifest['sources'][0]['reports'][0]['run_id']
    _, navigation = nav(client, '/runs/' + first + '/visualization')
    link = navigation.find('a', string='Next target: second · View status')
    assert link['href'] == location + '#source-line-3'
    second_continuum = manifest['sources'][1]['reports'][1]['run_id']
    _, navigation = nav(client, '/runs/' + second_continuum)
    assert navigation.find('a', string='Spectral line · View status')['href'] == location + '#source-line-3'


def test_evicted_current_and_sibling_reports_keep_return_path(client):
    runs = client.application.extensions['assessment_runs']
    location, manifest = batch(client)
    # Legacy/lost-file navigation remains supported even though new batches are protected.
    with runs._lock:
        for source in manifest['sources']:
            for report in source['reports']:
                if report['run_id'] != manifest['sources'][-1]['reports'][-1]['run_id']:
                    runs._retire(report['run_id'], 'EVICTED')
    overview = client.get(location)
    assert b'3 previously saved reports are no longer available' in overview.data
    assert b'Completed \xc2\xb7 report unavailable' in overview.data
    old = manifest['sources'][0]['reports'][0]['run_id']
    response, navigation = nav(client, '/runs/' + old)
    assert response.status_code == 404 and navigation
    assert navigation.find('a', string='Back to batch overview')['href'] == location + '#source-line-2'
    assert 'Current report unavailable' in navigation.text
    index, latest = next((i, r['run_id']) for i, source in enumerate(manifest['sources'])
                         for r in source['reports'] if runs.unavailable_reason(r['run_id']) is None)
    _, navigation = nav(client, '/runs/' + latest + '/visualization')
    label = 'Previous target: first' if index else 'Next target: second'
    anchor = '#source-line-2' if index else '#source-line-3'
    assert navigation.find('a', string=label + ' · View status')['href'] == location + anchor


def test_owner_parent_lifetime_and_standalone_reports(client):
    location, manifest = batch(client)
    run_id = manifest['sources'][0]['reports'][0]['run_id']
    other = client.application.test_client()
    # Existing opaque run URLs retain their old behavior, but expose no batch metadata.
    assert nav(other, '/runs/' + run_id)[1] is None
    assert other.get(location).status_code == 404
    runs = client.application.extensions['assessment_runs']
    request = client.get('/runs/' + run_id + '/download/request').json
    from tests.ui.test_batch_assessment import runner
    standalone = runs.add(request, runner().pin_queue_for_submission(True).assess(request))
    assert nav(client, '/runs/' + standalone)[1] is None
    runs.batches.close()
    assert nav(client, '/runs/' + run_id)[1] is None


def test_current_report_download_bytes_and_filters_unchanged(client):
    _, manifest = batch(client)
    run_id = manifest['sources'][0]['reports'][0]['run_id']
    before = {kind: client.get('/runs/' + run_id + '/download/' + kind).data
              for kind in ('report', 'inspection', 'request')}
    response, navigation = nav(client, '/runs/' + run_id + '?view=all&page=1&technical=1')
    assert response.status_code == 200 and navigation
    response, navigation = nav(client, '/runs/' + run_id + '/queue?view=all&page=1')
    assert response.status_code == 200 and navigation
    for kind, raw in before.items():
        assert client.get('/runs/' + run_id + '/download/' + kind).data == raw
