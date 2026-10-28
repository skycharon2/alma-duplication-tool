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
    assert len(calls) == 1
