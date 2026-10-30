"""Independent same-position setups produce separate immutable reports."""
from copy import deepcopy

from tests.ui.test_separated_v2_browser_step05a import make_client as make_client
from tests.ui.test_normal_observation import data, ROW
from tests.integration.test_line_preparation import EXAMPLE, payload


def inputs():
    p = payload()['request']['position']
    values = data(('LINE',))
    values.update(normal_form_version='2', frequency_local_redshift='1',
                  geometry='SINGLE_POINTING', target_kind='FIXED', ra=str(p['ra']), dec=str(p['dec']),
                  ra_format='DEG', dec_format='DEG', radius_mode='EXPLICIT', radius='30', angular='0.5')
    values['rows'] = [ROW]
    values[ROW + '_rms'] = '10'
    return values


def group(client):
    with client.session_transaction() as session:
        return client.application.extensions['observation_sets'].get(session['observation_group'], session['mosaic_owner'])


def form(client):
    values, rows = client.application.extensions['observation_sets'].load_draft(group(client))
    return values | {'rows': rows}


def test_two_observations_get_separate_reports_explore_and_requests(make_client):
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE / 'archive/manifest.json'))
    response = client.post('/proposed', data=inputs() | {'action': 'observation-add'})
    assert response.status_code == 200
    assert 'Observation 2' in response.text
    second = form(client)
    second[ROW + '_redshift'] = '0'
    response = client.post('/proposed', data=second | {'action': 'assess'})
    assert response.status_code == 303
    second_url = response.headers['Location']
    client.post('/proposed', data=form(client) | {'action': 'observation-switch:1'})
    first = form(client)
    assert first[ROW + '_redshift'] == '1'
    response = client.post('/proposed', data=first | {'action': 'assess'})
    assert response.status_code == 303
    first_url = response.headers['Location']
    assert first_url != second_url
    reports = [client.get(url + '/download/report').json for url in (first_url, second_url)]
    requests = [r['request']['raw'] for r in reports]
    assert requests[0]['position'] == requests[1]['position']
    assert requests[0]['setup_id'] != requests[1]['setup_id']
    assert requests[0]['line_requirements'][0]['source_redshift'] == '1'
    assert requests[1]['line_requirements'][0]['source_redshift'] == '0'
    assert any(b['status'] == 'CRITERIA_MET' for c in reports[0]['context_evaluations'] for b in c['branches'])
    assert not any(b['status'] == 'CRITERIA_MET' for c in reports[1]['context_evaluations'] for b in c['branches'])
    for url in (first_url, second_url):
        page = client.get(url)
        assert 'Reports for shared position' in page.text
        assert first_url in page.text and second_url in page.text
        assert client.get(url + '/visualization').status_code == 200
    assert client.get(first_url + '/download/report').json == reports[0]


def test_invalid_second_observation_does_not_block_first_or_access_sources(make_client):
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE / 'archive/manifest.json'))
    client.post('/proposed', data=inputs() | {'action': 'observation-add'})
    invalid = form(client) | {ROW + '_rms': '', 'action': 'assess'}
    assert client.post('/proposed', data=invalid).status_code == 200
    assert not any(o['reports'] for o in group(client)['observations'])
    client.post('/proposed', data=form(client) | {'action': 'observation-switch:1'})
    assert client.post('/proposed', data=form(client) | {'action': 'assess'}).status_code == 303
    assert len(group(client)['observations'][0]['reports']) == 1
    assert group(client)['observations'][1]['reports'] == []


def test_position_shared_drafts_isolated_stale_and_foreign_posts_rejected(make_client):
    client = make_client()
    client.post('/proposed', data=inputs() | {'action': 'observation-add'})
    stale = deepcopy(form(client))
    changed = form(client) | {'ra': '42', 'action': 'observation-switch:1'}
    assert client.post('/proposed', data=changed).status_code == 200
    assert form(client)['ra'] == '42'
    assert client.post('/proposed', data=stale | {'action': 'validate'}).status_code == 409
    foreign = make_client()
    assert foreign.post('/proposed', data=form(client) | {'action': 'validate'}).status_code == 410
    assert client.post('/proposed', data=form(client) | {'geometry': 'MOSAIC'}).status_code == 400


def test_continuum_setup_and_line_setup_keep_separate_purposes(make_client):
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE / 'archive/manifest.json'))
    client.post('/proposed', data=inputs() | {'action': 'observation-add'})
    continuum = form(client) | {'intents': ['CONTINUUM'], 'rows': [], 'spw_rows': [],
                               'representative': '225.1', 'representative_kind': 'SKY',
                               'aggregate': '10', 'continuum_setup_declaration': 'on',
                               'action': 'assess'}
    response = client.post('/proposed', data=continuum)
    assert response.status_code == 303
    report = client.get(response.headers['Location'] + '/download/report').json
    assert report['request']['raw']['intents'] == ['CONTINUUM']
    assert {b['branch'] for c in report['context_evaluations'] for b in c['branches']} == {'CONTINUUM'}
    client.post('/proposed', data=form(client) | {'action': 'observation-switch:1'})
    assert form(client)['intents'] == ['LINE']
    assert form(client)['rows'] == [ROW]
