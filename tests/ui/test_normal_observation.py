"""The normal page runs LINE, continuum and combined Archive observations."""
import pytest
from tests.ui.test_separated_v2_browser_step05a import make_client as client_factory
from tests.ui.test_mosaic_execution import browser as mosaic_fixture, upload
from tests.ui.test_normal_line_records import fields, ROW, SECOND
from tests.integration.test_line_preparation import EXAMPLE, payload

make_client = client_factory
browser = mosaic_fixture


def data(intents):
    values = fields() | dict(intents=list(intents), representative='225.1', aggregate='0.3',
        continuum_setup_declaration='on', sources='ARCHIVE', setup_complete='')
    values.update({ROW+'_center':'450.2', ROW+'_redshift':'1', ROW+'_rms':'0.3',
                   SECOND+'_center':'450.2', SECOND+'_redshift':'0', SECOND+'_rms':'0.3'})
    if 'CONTINUUM' not in intents:
        values.pop('aggregate')
    if 'LINE' not in intents:
        values['rows'] = []
        values['spw_rows'] = []
    return values


@pytest.mark.parametrize('intents', [('LINE',), ('CONTINUUM',), ('LINE','CONTINUUM')])
def test_single_normal_form_roundtrip(make_client, intents):
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE/'archive/manifest.json'))
    position = payload()['request']['position']
    values = data(intents) | dict(geometry='SINGLE_POINTING', ra=str(position['ra']),
        dec=str(position['dec']), ra_format=position['ra_format'], dec_format=position['dec_format'],
        radius_mode='EXPLICIT', radius='30', result_limit='1', angular='0.5')
    export = client.post('/proposed', data=values | dict(action='download'))
    assert export.is_json, export.text
    result = client.post('/proposed', data=values | dict(action='assess'))
    assert result.status_code == 303, result.text
    url = result.headers['Location']
    assert client.get(url).status_code == 200
    assert client.get(url+'?view=all').status_code == 200
    raw = client.get(url+'/download/request').json
    assert raw == export.json
    report = client.get(url+'/download/report').json
    assert report['report_version'] == '8'
    assert {b['branch'] for c in report['context_evaluations'] for b in c['branches']} == set(intents)
    assert client.get(url+'/download/inspection').status_code == 200


@pytest.mark.parametrize('intents', [('CONTINUUM',), ('LINE','CONTINUUM')])
def test_mosaic_normal_form_continuum(browser, intents):
    client, calls = browser
    values = data(intents) | dict(mosaic_upload_token=upload(client))
    result = client.post('/proposed', data=values | dict(action='assess'))
    assert result.status_code == 303, result.text
    url = result.headers['Location']
    assert client.get(url).status_code == 200
    report = client.get(url+'/download/report').json
    assert {b['branch'] for candidate in report['candidates'] for c in candidate['evaluation']['contexts'] for b in c['branches']} == set(intents)
    for candidate in report['candidates']:
        for context in candidate['evaluation']['contexts']:
            identity = context['display_identity']
            assert identity['Member OUS'] == candidate['member_ous_uid']
            assert identity['Target'] == candidate['source_name']
            assert 'ASDM' in identity and 'SPW' in identity
    rendered = client.get(url + '?view=all').text
    assert 'Execution (ASDM):' in rendered
    if 'LINE' in intents:
        assert 'LINE requirement 1' in rendered
        assert 'LINE requirement 2' in rendered
        assert 'Input frequency' in rendered
    assert len(calls) == 1


def test_frequency_local_redshift_export_has_no_shared_default(make_client):
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE/'archive/manifest.json'))
    position = payload()['request']['position']
    values = data(('LINE', 'CONTINUUM')) | dict(
        frequency_local_redshift='1', redshift='99', continuum_redshift='2',
        representative_kind='REST', representative='675.3', geometry='SINGLE_POINTING',
        ra=str(position['ra']), dec=str(position['dec']),
        ra_format=position['ra_format'], dec_format=position['dec_format'], angular='0.5',
        radius_mode='EXPLICIT', radius='30', result_limit='1')
    exported = client.post('/proposed', data=values | dict(action='download'))
    assert exported.is_json, exported.text
    raw = exported.json['request']
    assert 'source_redshift' not in raw
    assert raw['continuum_requirement']['source_redshift'] == '2'
    assert [r['source_redshift'] for r in raw['line_requirements']] == ['1', '0']
    from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
    prepared = prepare_submitted_line_request(raw)
    assert prepared.continuum_request.source_redshift == 2
    assert prepared.line_request.source_redshift is None
    html = client.post('/proposed', data=values | dict(action='validate')).text
    assert 'id="shared-redshift"' not in html
    assert 'id="continuum_redshift"' in html


def test_no_selected_science_hides_shared_redshift(make_client):
    client = make_client()
    html = client.get('/proposed').text
    import re
    assert re.search(r'<div id="shared-redshift"[^>]*\bhidden\b', html)


def test_single_pointing_editor_does_not_depend_on_source_selection(make_client):
    client = make_client()
    values = data(('LINE',)) | dict(normal_form_version='2', geometry='SINGLE_POINTING',
                                   sources=['ARCHIVE', 'QUEUE'], action='purpose')
    values.pop('normal_line_records', None)
    html = client.post('/proposed', data=values).text
    assert 'Physical SPW evidence' in html
    assert 'name="frequency_local_redshift"' in html
    assert 'id="shared-redshift"' not in html
    assert 'This optional separated V2 editor currently runs Archive-only' not in html


@pytest.mark.parametrize('intents', [('LINE',), ('CONTINUUM',), ('LINE', 'CONTINUUM')])
def test_single_v2_form_runs_both_sources_and_downloads_report(make_client, tmp_path, intents):
    from tests.unit.test_queue_csv_parser import _records, _indices, _render
    records = _records()
    columns = _indices(records)
    p = payload()['request']['position']
    row = records[41].copy()
    for key, value in {'RA': str(p['ra']), 'Dec': str(p['dec']),
                       'Long Offset': '0', 'Lat Offset': '0',
                       'Use TP?': 'False', 'Use 7-m?': 'False'}.items():
        row[columns[key]] = value
    csv = tmp_path / 'queue.csv'
    csv.write_bytes(_render(records[:41] + [row]))
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE / 'archive/manifest.json'),
                         OFFLINE_QUEUE_CSV=str(csv))
    values = data(intents) | dict(normal_form_version='2', frequency_local_redshift='1',
        geometry='SINGLE_POINTING', ra=str(p['ra']), dec=str(p['dec']),
        ra_format='DEG', dec_format='DEG', sources=['ARCHIVE', 'QUEUE'],
        radius_mode='EXPLICIT', radius='30', angular='0.5', action='assess')
    result = client.post('/proposed', data=values)
    assert result.status_code == 303, result.text
    url = result.headers['Location']
    assert client.get(url + '?view=all').status_code == 200
    report = client.get(url + '/download/report').json
    assert all(report['sources'][s]['status'] == 'COMPLETED' for s in ['ARCHIVE', 'QUEUE'])
    for source in ['ARCHIVE', 'QUEUE']:
        contexts = [c for c in report['context_evaluations'] if c['reference']['source'] == source]
        assert contexts
        assert {b['branch'] for c in contexts for b in c['branches']} == set(intents)
    assert report['request']['raw']['line_input_contract'] == 'SEPARATE_OBSERVATION_REQUIREMENTS_V2'
