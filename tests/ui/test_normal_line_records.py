"""Existing Mosaic form: independent LINE and physical SPW records."""
import pytest
from tests.ui.test_mosaic_execution import browser as mosaic_browser, form, upload, ROW

browser = mosaic_browser

SECOND = 'wabcdef123456'
SPW = 'w111111111111'


def fields():
    data = form() | dict(normal_line_records='1', rows=[ROW, SECOND], spw_rows=[SPW],
                        setup_complete='', redshift='9')
    data.update({ROW+'_center': '1381.786358464217', ROW+'_center_kind': 'REST',
                 ROW+'_redshift': '1', SECOND+'_id': 'line-2',
                 SECOND+'_center': '1381.786358464217', SECOND+'_center_kind': 'REST',
                 SECOND+'_redshift': '0', SECOND+'_mode': 'FDM',
                 SECOND+'_resolution': '10', SECOND+'_rms': '8',
                 SPW+'_id': 'physical-a', SPW+'_bandwidth': '1875',
                 SPW+'_bandwidth_kind': 'USABLE', SPW+'_link': 'line-0'})
    return data


def test_export_and_real_run_use_same_separated_records(browser):
    client, calls = browser
    data = fields() | dict(mosaic_upload_token=upload(client))
    exported = client.post('/proposed', data=data | dict(action='download'))
    assert exported.is_json, exported.text
    raw = exported.json['request']
    assert [r['source_redshift'] for r in raw['line_requirements']] == ['1', '0']
    assert len(raw['physical_spw_evidence']) == 1
    assert not raw['physical_spw_inventory_complete']
    response = client.post('/proposed', data=data | dict(action='assess'))
    assert response.status_code == 303, response.text
    url = response.headers['Location']
    retained = client.get(url + '/download/request').json
    assert retained['request'] == raw
    report = client.get(url + '/download/report').json
    assert report['schema_version'] == 'submitted_observation_mosaic_search_report_2'
    assert len(calls) == 1


@pytest.mark.parametrize('change', [
    {'angular': ''}, {SECOND+'_rms': ''}, {SECOND+'_redshift': '-1'}, {SPW+'_link': 'missing'},
    {'geometry': 'SINGLE_POINTING'}, {'intents': ['LINE', 'CONTINUUM']},
])
def test_invalid_or_unsupported_records_never_query(browser, change):
    client, calls = browser
    response = client.post('/proposed', data=fields() | dict(action='assess',
                           mosaic_upload_token=upload(client)) | change)
    assert response.status_code == 200
    assert not calls


def test_independent_add_remove_and_retained_values(browser):
    client, _ = browser
    response = client.post('/proposed', data=fields() | dict(action='add-spw'))
    assert response.status_code == 200
    assert response.text.count('name="rows"') == 2
    assert response.text.count('name="spw_rows"') == 2
    assert 'name="'+SECOND+'_redshift" value="0"' in response.text
    response = client.post('/proposed', data=fields() | dict(action='remove-spw:'+SPW))
    assert response.text.count('name="rows"') == 2
    assert 'name="spw_rows"' not in response.text
    response = client.post('/proposed', data=fields() | dict(action='confirm-remove:'+ROW))
    assert response.text.count('name="rows"') == 1
    assert response.text.count('name="spw_rows"') == 1
    assert 'Retained reference: line-0' in response.text
