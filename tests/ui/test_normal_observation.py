"""The normal page runs LINE, continuum and combined Archive observations."""
import pytest
from tests.ui.test_separated_v2_browser_step05a import make_client as client_factory
from tests.ui.test_mosaic_execution import browser as mosaic_fixture, upload
from tests.ui.test_normal_line_records import single_line_fields, ROW
from tests.integration.test_line_preparation import EXAMPLE, payload

make_client = client_factory
browser = mosaic_fixture


def data(intents):
    values = single_line_fields() | dict(intents=list(intents), representative='225.1', aggregate='0.3',
        continuum_setup_declaration='on', sources='ARCHIVE', setup_complete='')
    values.update({ROW+'_center':'450.2', ROW+'_redshift':'1', ROW+'_rms':'0.3'})
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
    if len(intents) == 1:
        assert raw == export.json
    else:
        assert raw["request"]["intents"] == [intents[0]]
    report = client.get(url+'/download/report').json
    assert report['report_version'] == '8'
    assert {b['branch'] for c in report['context_evaluations'] for b in c['branches']} == {intents[0]}
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
    assert {b['branch'] for candidate in report['candidates'] for c in candidate['evaluation']['contexts'] for b in c['branches']} == {intents[0]}
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
        assert 'LINE requirement 2' not in rendered
        assert 'Input frequency' in rendered
    assert len(calls) == len(intents)


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
    assert [r['source_redshift'] for r in raw['line_requirements']] == ['1']
    from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
    prepared = prepare_submitted_line_request(raw)
    assert prepared.continuum_request.source_redshift == 2
    assert prepared.line_request.source_redshift is None
    html = client.post('/proposed', data=values | dict(action='validate')).text
    assert 'id="shared-redshift"' not in html
    assert 'id="continuum_redshift"' in html


def test_initial_target_shows_shared_redshift(make_client):
    client = make_client()
    html = client.get('/proposed').text
    target = html.split('class="form-pair target-identity-grid"', 1)[1].split('id="scope-support"', 1)[0]
    assert '<div id="shared-redshift">' in target


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
        assert {b['branch'] for c in contexts for b in c['branches']} == {intents[0]}
    assert report['request']['raw']['line_input_contract'] == 'SEPARATE_OBSERVATION_REQUIREMENTS_V2'


@pytest.mark.parametrize("selected", [[], ["LINE"], ["CONTINUUM"], ["LINE", "CONTINUUM"]])
def test_purpose_edit_only_opens_selected_sections(make_client, selected):
    client = make_client()
    values = data(("LINE", "CONTINUUM")) | dict(
        geometry="SINGLE_POINTING", intents=selected, action="purpose")
    html = client.post("/proposed", data=values).text
    for intent, section in [("LINE", "line-requirements"), ("CONTINUUM", "sensitivities")]:
        opening = html.split(f'<section id="{section}"', 1)[1].split(">", 1)[0]
        assert ("hidden" in opening) == (intent not in selected)


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
def test_target_redshift_survives_purpose_changes(make_client, geometry):
    from bs4 import BeautifulSoup
    client = make_client()
    values = dict(target_kind="FIXED", geometry=geometry, normal_form_version="2",
                  redshift="0.5", sources=["ARCHIVE", "QUEUE"], action="purpose")
    url = "/proposed/mosaic" if geometry == "MOSAIC" else "/proposed"
    for intents in [["CONTINUUM"], ["LINE", "CONTINUUM"], [], ["CONTINUUM"]]:
        page = BeautifulSoup(client.post(url, data=values | {"intents": intents}).text, "html.parser")
        assert page.select_one('[name="redshift"]')["value"] == "0.5"
        continuum = page.select_one('[name="continuum_redshift"]')
        if continuum:
            assert continuum["value"] == "0.5"
        for field in page.select('input[name]'):
            name = field["name"]
            if name.endswith("_redshift") or name in {"frequency_local_redshift", "normal_line_records"}:
                values[name] = field.get("value", "")
        values["rows"] = [field["value"] for field in page.select('input[name="rows"]')]
    values.update(continuum_redshift="", intents=["CONTINUUM"])
    page = BeautifulSoup(client.post(url, data=values).text, "html.parser")
    assert page.select_one('[name="continuum_redshift"]')["value"] == ""


@pytest.mark.parametrize('draft', ['', 'not-a-frequency', '450.2'])
def test_mosaic_continuum_ignores_deselected_line_draft(browser, draft):
    from bs4 import BeautifulSoup
    client, calls = browser
    values = data(('CONTINUUM',)) | dict(normal_form_version='2',
        mosaic_upload_token=upload(client))
    # Reproduce the purpose toggle that creates the otherwise empty LINE row.
    page = BeautifulSoup(client.post('/proposed/mosaic', data=values | dict(
        action='purpose', intents=['LINE'])).text, 'html.parser')
    row = page.select_one('input[name="rows"]')['value']
    values.update(rows=[row], **{row+'_id': row, row+'_center': draft,
                                 row+'_resolution': '', row+'_rms': ''})
    retained = BeautifulSoup(client.post('/proposed/mosaic', data=values | dict(
        action='purpose')).text, 'html.parser')
    assert retained.select_one('#line-requirements').has_attr('hidden')
    assert retained.select_one(f'[name="{row}_center"]')['value'] == draft
    assert not calls
    exported = client.post('/proposed/mosaic', data=values | dict(action='download'))
    assert exported.is_json, exported.text
    assert exported.json['request']['line_requirements'] == []
    result = client.post('/proposed/mosaic', data=values | dict(action='assess'))
    assert result.status_code == 303, result.text
    assert len(calls) == 1
    saved = client.get(result.headers['Location'] + '/download/request').json
    assert saved['request']['intents'] == ['CONTINUUM']
    assert saved['request']['line_requirements'] == []
    # Switching LINE back on must validate the retained incomplete draft.
    invalid = client.post('/proposed/mosaic', data=values | dict(
        action='assess', intents=['LINE', 'CONTINUUM']))
    assert invalid.status_code == 200
    assert len(calls) == 1
    assert 'Expected a decimal number' in invalid.text


@pytest.mark.parametrize('geometry', ['MOSAIC', 'SINGLE_POINTING'])
def test_v2_inactive_line_draft_does_not_mutate_editor_or_drop_physical_evidence(geometry):
    from copy import deepcopy
    from alma_duplicate.ui.proposed import build_document
    values = data(('LINE', 'CONTINUUM')) | dict(geometry=geometry,
        intents=['CONTINUUM'], spw_rows=['w111111111111'],
        w111111111111_id='physical-1', w111111111111_bandwidth='2000',
        w111111111111_bandwidth_kind='USABLE', w111111111111_link='')
    rows = [ROW]
    before = deepcopy(values)
    document, _ = build_document(values, rows)
    assert document['request']['line_requirements'] == []
    assert document['request']['physical_spw_evidence'] == [dict(
        spw_id='physical-1', bandwidth=dict(value='2000', unit='MHz'), bandwidth_kind='USABLE')]
    assert values == before and rows == [ROW]
    values['intents'] = ['LINE', 'CONTINUUM']
    restored, _ = build_document(values, rows)
    assert restored['request']['line_requirements'][0]['window_center']['value'] == '450.2'


def test_continuum_preserves_explicit_physical_spw_dependency_on_line():
    from alma_duplicate.ui.proposed import build_document
    values = data(('LINE', 'CONTINUUM')) | dict(intents=['CONTINUUM'])
    document, _ = build_document(values, [ROW])
    assert document['request']['line_requirements'][0]['requirement_id'] == 'line-0'
    assert document['request']['physical_spw_evidence'][0]['linked_line_requirement_id'] == 'line-0'


@pytest.mark.parametrize('version', ['legacy', '2'])
def test_single_pointing_executes_continuum_with_inactive_line_draft(make_client, version):
    client = make_client(OFFLINE_ARCHIVE_REPLAY=str(EXAMPLE/'archive/manifest.json'))
    position = payload()['request']['position']
    values = data(('CONTINUUM',)) | dict(geometry='SINGLE_POINTING',
        ra=str(position['ra']), dec=str(position['dec']),
        ra_format=position['ra_format'], dec_format=position['dec_format'],
        radius_mode='EXPLICIT', radius='30', result_limit='1', angular='0.5',
        rows=[ROW], spw_rows=[])
    values.update({ROW+'_center': 'unfinished', ROW+'_resolution': '', ROW+'_rms': ''})
    values.pop('normal_line_records', None)
    if version == '2':
        values['normal_form_version'] = '2'
    response = client.post('/proposed', data=values | dict(action='assess'))
    assert response.status_code == 303, response.text
    url = response.headers['Location']
    request = client.get(url+'/download/request').json['request']
    assert request['intents'] == ['CONTINUUM']
    assert request.get('line_requirements', request.get('spectral_windows')) == []
    report = client.get(url+'/download/report').json
    assert {b['branch'] for c in report['context_evaluations'] for b in c['branches']} == {'CONTINUUM'}
