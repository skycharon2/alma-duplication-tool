"""Read-only paired charts over recorded single-pointing evidence."""
from copy import deepcopy
import json
import math
import re

import pytest
import requests

from alma_duplicate.ui import create_app
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.report_pages import report_page, report_projection
from alma_duplicate.ui.visualization import beam_outline, sky_offset, visualization_data
from tests.ui.test_calculation_view import serialized, report, case
from tests.ui.test_runs import config, line_form


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith('ALMA_UI_'):
            monkeypatch.delenv(key)
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **kw: pytest.fail('Visualization accessed a source'))


def page(document, number=1, compact=False):
    return report_page(report_projection(document, {}, compact=compact), number, 'matches',
                       lambda i: document['context_evaluations'][i])


def visual_response(client, url):
    response = client.get(url)
    assert response.status_code == 200
    match = re.search(r'<script id="visual-data" type="application/json">(.*?)</script>', response.text, re.S)
    return json.loads(match.group(1))


def test_line_evidence_exact_identity_and_immutable_document():
    document = serialized(report())
    before = deepcopy(document)
    v = visualization_data(page(document, compact=True))
    r = v['rows'][0]
    assert r['identity']['SPW'] == '0'
    assert r['anchor'] == 'pair-0-0' and r['window'] == 'line-0'
    assert r['spectral']['proposed'] == 230.538 / 1.024
    assert [r['spectral']['low'], r['spectral']['high']] == [224.8, 225.4]
    assert r['spatial']['center'] == [201.3665, -43.0185]
    assert math.hypot(*r['spatial']['offset']) == pytest.approx(r['spatial']['separation_arcsec'], rel=1e-9)
    assert document == before


@pytest.mark.parametrize('damage', ['duplicate', 'reference', 'context', 'geometry', 'missing', 'unapproved'])
def test_archive_never_borrows_ambiguous_or_unconfirmed_centers(damage):
    document = serialized(report())
    row = document['sources']['ARCHIVE']['rows'][0]
    if damage == 'duplicate':
        document['sources']['ARCHIVE']['rows'].append(deepcopy(row))
    elif damage == 'reference':
        row['reference']['component_index'] = 999
    elif damage == 'context':
        row['spatial_evidence']['context_id'] = 'different-context'
    elif damage == 'geometry':
        row['spatial_evidence']['geometry'] = 'MOSAIC'
    elif damage == 'missing':
        row['spatial_evidence']['center'] = None
    else:
        document['context_evaluations'][0]['line_pairs'][0]['criteria'][0]['eligible_for_formal_aggregation'] = False
    r = visualization_data(page(document))['rows'][0]
    assert not r['spatial']['available']
    assert r['spectral']['available']


def test_queue_continuum_uses_two_markers_and_backend_radius():
    _, evaluation, _ = case()
    v = visualization_data(page(serialized(evaluation)))
    r = v['rows'][0]
    assert r['spatial']['available'] and r['spatial']['center'] == [201.365, -43.019]
    assert r['spectral']['kind'] == 'representative'
    assert r['spectral']['proposed'] == r['spectral']['candidate'] == 230
    assert 'low' not in r['spectral'] and 'high' not in r['spectral']


@pytest.mark.parametrize('origin,point,expected', [((359.999, 0), (.001, 0), (-7.2, 0)),
    ((0, 0), (0, .001), (0, 3.6)), ((10, 90), (10, 89.999), (0, -3.6))])
def test_spherical_display_wrap_and_poles(origin, point, expected):
    assert sky_offset(origin, point) == pytest.approx(expected, abs=1e-7)
    assert sky_offset((0, 0), (180, 0)) is None


@pytest.mark.parametrize('center', [(0, 0), (359.999, -43), (0, 90), (20, -90)])
def test_stored_radius_projects_to_equal_distance_circle(center):
    points = beam_outline(center, center, .005)
    assert len(points) == 73
    assert all(math.hypot(*p) == pytest.approx(18, abs=1e-7) for p in points)


def test_missing_radius_does_not_derive_beam_and_old_index_is_safe():
    document = serialized(report())
    record = document['context_evaluations'][0]['line_pairs'][0]['criteria'][0]
    record['derived'] = [p for p in record['derived'] if p[0] != 'candidate_radius_deg']
    row = visualization_data(page(document))['rows'][0]
    assert row['spatial']['available'] and row['spatial']['outline'] is None
    projection = report_projection(document, {}, compact=True)
    del projection['spatial']
    old = report_page(projection, 1, 'matches', lambda i: document['context_evaluations'][i])
    assert not visualization_data(old)['rows'][0]['spatial']['available']


def test_pagination_keeps_execution_pair_and_beam_variants_separate():
    document = serialized(report())
    context = document['context_evaluations'][0]
    pair = context['line_pairs'][0]
    context['line_pairs'] = [deepcopy(pair) for _ in range(31)]
    data = page(document)
    first, second = visualization_data(data), visualization_data(data, 2)
    assert len(first['rows']) == 30 and len(second['rows']) == 1
    assert first['total'] == 31 and second['rows'][0]['anchor'] == 'pair-0-30'
    assert not set(r['id'] for r in first['rows']) & set(r['id'] for r in second['rows'])
    with pytest.raises(IndexError):
        visualization_data(data, 3)
    context['beam_variants'] = [deepcopy(context), deepcopy(context)]
    for variant in context['beam_variants']:
        variant['line_pairs'] = [deepcopy(pair)]
    rows = visualization_data(page(document))['rows']
    assert [r['anchor'] for r in rows] == ['pair-0-beam-0-0', 'pair-0-beam-1-0']


def test_report_route_escape_empty_scope_and_original_download(tmp_path):
    document = serialized(report())
    document['request']['normalized']['target_name'] = '</script><script>alert(1)</script>'
    directory = tmp_path / 'line'
    directory.mkdir()
    raw = report_json_text(document).encode()
    (directory / 'report.json').write_bytes(raw)
    app = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path})
    client = app.test_client()
    base = '/reports/1'
    response = client.get(base + '/visualization')
    assert response.status_code == 200
    assert b'</script><script>alert(1)</script>' not in response.data
    assert 'Position' in response.text and 'Frequency' in response.text
    assert response.text.index('static/visualization_view.js') < response.text.index('static/visualization.js')
    assert client.get('/static/visualization_view.js').status_code == 200
    assert len(visual_response(client, base + '/visualization')['rows']) == 1
    assert client.get(base + '/download/report').data == raw
    assert base + '/visualization' in client.get(base).text
    for query, status in [('?page=0', 400), ('?plot_page=-1', 400), ('?plot_page=x', 400),
                          ('?page=99', 404), ('?plot_page=99', 404)]:
        assert client.get(base + '/visualization' + query).status_code == status
    assert client.get('/reports/unknown/visualization').status_code == 404
    document['request']['normalized']['geometry'] = 'MOSAIC'
    assert not visualization_data(page(document))['rows']
    assert not visualization_data(page(document))['supported']
    document['context_evaluations'] = []
    assert visualization_data(page(document))['total'] == 0


def test_two_disk_runs_dual_source_no_requery_or_download_change(monkeypatch):
    from alma_duplicate.ui import runs as execution
    app = create_app(config(LIVE_AQ=False))
    client = app.test_client()
    form = line_form()
    form.setlist('sources', ['ARCHIVE', 'QUEUE'])
    locations = []
    for name in ['First observation', 'Second observation']:
        form.setlist('target_name', [name])
        response = client.post('/proposed', data=form)
        assert response.status_code == 303
        locations.append(response.location)
    monkeypatch.setattr(execution, 'assess_observation', lambda *a, **kw: pytest.fail('viewer ran assessment'))
    for location, name in zip(locations, ['First observation', 'Second observation']):
        before = {kind: client.get(location + '/download/' + kind).data for kind in ['request', 'inspection', 'report']}
        visual = visual_response(client, location + '/visualization')
        assert {r['source'] for r in visual['rows']} == {'ARCHIVE', 'QUEUE'}
        assert all(r['spatial']['available'] and r['spectral']['available'] for r in visual['rows'])
        assert name in client.get(location + '/visualization').text
        for kind, raw in before.items():
            assert client.get(location + '/download/' + kind).data == raw
    app.extensions['assessment_runs'].close()
    assert client.get(locations[0] + '/visualization').status_code == 404


def test_result_group_pages_do_not_repeat_comparisons():
    _, evaluation, _ = case(count=21)
    document = serialized(evaluation)
    first = visualization_data(page(document, 1))
    second = visualization_data(page(document, 2))
    assert len(first['rows']) == 20 and len(second['rows']) == 1
    assert not {r['id'] for r in first['rows']} & {r['id'] for r in second['rows']}
    assert any(c['label'] == 'Proposed continuum setup' for c in first['rows'][0]['criteria'])


def test_missing_frequency_cannot_borrow_from_request_or_other_pair():
    document = serialized(report())
    record = next(r for r in document['context_evaluations'][0]['line_pairs'][0]['criteria']
                  if r['criterion_id'] == 'LINE-COVERAGE')
    record['derived'] = [p for p in record['derived'] if p[0] != 'interval_low_ghz']
    row = visualization_data(page(document))['rows'][0]
    assert not row['spectral']['available']
    assert row['spatial']['available']


def test_mosaic_region_display_uses_bound_saved_geometry():
    from hashlib import sha256
    from alma_duplicate.ui.visualization import spatial_view
    raw = 'Polygon ICRS 359 -1 1 -1 1 1 359 1'
    context = {'context_id': 'm1', 'reference': {'source': 'ARCHIVE'}}
    evidence = dict(context, geometry='MOSAIC')
    record = {'criterion_id': 'POS-SINGLE', 'method_version': 'archive_pos_single_mosaic_s_region_1',
              'eligible_for_formal_aggregation': True,
              'derived': [('point_status', 'INSIDE')],
              'details': [('raw_s_region', raw), ('s_region_sha256', sha256(raw.encode()).hexdigest())]}
    result = spatial_view(context, [record], (0, 0), evidence)
    assert result['available']
    assert result['coverage_source'] == 'ARCHIVE_S_REGION'
    assert result['radius_arcsec'] is None
    assert len(result['sky_outline']) == 65
    assert result['sky_outline'][0] == result['sky_outline'][-1]
    assert all(abs(x) < 4000 and abs(y) < 4000 for x, y in result['outline'])
    broken = deepcopy(record)
    broken['details'][0] = ('raw_s_region', 'Circle ICRS 0 0 1')
    assert not spatial_view(context, [broken], (0, 0), evidence)['available']
    assert not spatial_view(context, [record], (0, 0), dict(evidence, context_id='other'))['available']


def test_region_display_circle_and_pole():
    from hashlib import sha256
    from alma_duplicate.ui.region_display import saved_region_outline
    for raw in ['Circle ICRS 359.99 0 .1', 'Polygon ICRS 0 89 120 89 240 89']:
        center, points = saved_region_outline({'raw_s_region':raw, 's_region_sha256':sha256(raw.encode()).hexdigest()})
        assert all(math.isfinite(x) for p in [center, *points] for x in p)
        assert points[0] == pytest.approx(points[-1])


def test_mosaic_candidate_backend_report_and_explore_roundtrip(tmp_path):
    from tests.integration.test_line_evaluation import evaluate
    original = report().search_result.archive.source_record
    evaluation = evaluate(original, changes={'is_mosaic': 'T'})
    document = serialized(evaluation)
    directory = tmp_path / 'mosaic-candidate'
    directory.mkdir()
    raw = report_json_text(document).encode()
    (directory / 'report.json').write_bytes(raw)
    client = create_app({'TESTING': True, 'REPORT_DIRECTORY': tmp_path}).test_client()
    assert 'Archive Mosaic s_region' in client.get('/reports/1').text
    visual = visual_response(client, '/reports/1/visualization')
    assert visual['rows']
    spatial = visual['rows'][0]['spatial']
    assert spatial['coverage_source'] == 'ARCHIVE_S_REGION'
    assert spatial['sky_outline'] and spatial['outline']
    assert spatial['radius_arcsec'] is None
    assert client.get('/reports/1/download/report').data == raw


def test_continuum_coverage_uses_saved_component_and_preserves_frequency_points():
    from alma_duplicate.ui.visualization import spectral_view
    document = serialized(report())
    context = document['context_evaluations'][0]
    before = deepcopy(document)
    records = [dict(criterion_id='CONT-FREQ',
                    proposed=dict(unit='GHz', value=230.),
                    candidate=dict(unit='GHz', value=225.1))]
    result = spectral_view(records, 'CONTINUUM', context)
    assert result['candidate'] == 225.1
    assert result['proposed'] == 230.
    assert len(result['coverage']) == 1
    interval = result['coverage'][0]
    assert interval['low'] == 224.8
    assert interval['high'] == 225.4
    assert interval['bandwidth_ghz'] == pytest.approx(.6)
    assert interval['resolution'] is not None
    assert document == before


@pytest.mark.parametrize('damage', ['missing', 'reference', 'component', 'invalid'])
def test_display_coverage_never_guesses_or_crosses_context(damage):
    from alma_duplicate.ui.visualization import continuum_coverage
    context = serialized(report())['context_evaluations'][0]
    if damage == 'missing':
        del context['spectral_display']
    elif damage == 'reference':
        context['spectral_display']['reference']['raw_row_id'] = 'other'
    elif damage == 'component':
        context['spectral_display']['component']['component_index'] = 999
    else:
        context['spectral_display']['component']['frequency_interval']['low'] = -1
    assert continuum_coverage(context) == []


def test_full_spectral_setup_preserves_components_without_unique_mapping():
    from alma_duplicate.ui.visualization import spectral_setup
    document = serialized(report())
    context = document['context_evaluations'][0]
    parsed = context['spectral_setup_display']['evidence']['parse_result']
    original = deepcopy(parsed['components'][0])
    overlap = deepcopy(original)
    overlap['component_index'] = 5
    overlap['frequency_interval'].update(low=225.0, high=226.0)
    gap = deepcopy(original)
    gap['component_index'] = 6
    gap['frequency_interval'].update(low=240.0, high=241.0)
    centre = deepcopy(original)
    centre.update(component_index=7, frequency_interval=None,
                  displayed_center={'value': 250, 'unit': 'GHz'})
    parsed['components'] = [original, overlap, gap, centre]
    before = deepcopy(context)
    setup = spectral_setup(context)
    assert len(setup['components']) == 4
    assert setup['components'][1]['interval']['low'] == 225.0
    assert setup['components'][2]['interval']['low'] == 240.0
    assert setup['components'][3]['interval'] is None
    assert setup['selected_component'] == original['component_index']
    assert context == before
    del context['spectral_display']
    unbound = spectral_setup(context)
    assert unbound['id'] == setup['id']
    assert unbound['selected_component'] is None
    assert unbound['components'] == setup['components']


def test_full_spectral_setup_scope_and_version_are_not_globally_merged():
    from alma_duplicate.ui.visualization import spectral_setup
    context = serialized(report())['context_evaluations'][0]
    first = spectral_setup(context)
    altered = deepcopy(context)
    altered['reference']['source_record_id'] = 'other-run'
    altered['spectral_setup_display']['reference'] = deepcopy(altered['reference'])
    assert spectral_setup(altered)['id'] != first['id']
    altered = deepcopy(context)
    altered['spectral_setup_display']['evidence']['parse_result']['parser_version'] = 'other-parser'
    assert spectral_setup(altered)['id'] != first['id']
    altered['spectral_setup_display']['evidence']['raw_row_id'] = 'other-row'
    assert spectral_setup(altered) is None


def test_visualization_payload_shares_setup_and_handles_legacy_reports():
    document = serialized(report())
    visual = visualization_data(page(document))
    assert len(visual['spectral_setups']) == 1
    assert visual['rows'][0]['spectral_setup_id'] in visual['spectral_setups']
    for context in document['context_evaluations']:
        context.pop('spectral_setup_display', None)
    legacy = visualization_data(page(document))
    assert not legacy['spectral_setups']
    assert 'spectral_setup_id' not in legacy['rows'][0]


def test_setup_groups_repeated_spw_rows_only_with_same_execution_and_signature():
    from alma_duplicate.ui.visualization import spectral_setup
    first = serialized(report())['context_evaluations'][0]
    first['display_identity'].update({'Member OUS': 'member-a', 'ASDM': 'execution-a', 'Target': 'source-a'})
    second = deepcopy(first)
    second['reference'].update(raw_row_id='another-spw-row', component_index=2)
    second['spectral_setup_display']['reference'] = deepcopy(second['reference'])
    second['spectral_setup_display']['evidence']['raw_row_id'] = 'another-spw-row'
    second.pop('spectral_display', None)
    assert spectral_setup(first)['id'] == spectral_setup(second)['id']
    assert spectral_setup(first)['source_rows'] != spectral_setup(second)['source_rows']
    for field in ('Member OUS', 'ASDM', 'Target'):
        other = deepcopy(second)
        other['display_identity'][field] = 'different'
        assert spectral_setup(first)['id'] != spectral_setup(other)['id']
    other = deepcopy(second)
    other['spectral_setup_display']['evidence']['parse_result']['components'][0]['frequency_interval']['high'] += 1
    assert spectral_setup(first)['id'] != spectral_setup(other)['id']
    for record in (first, second):
        record['display_identity']['ASDM'] = None
    assert spectral_setup(first)['id'] != spectral_setup(second)['id']


def test_explore_pagers_keep_independent_state_and_comparison_numbers(monkeypatch):
    from html import unescape
    from tests.ui.test_queue_geometry_visualization import sample

    document = serialized(report())
    context = document['context_evaluations'][0]
    context['line_pairs'] = [deepcopy(context['line_pairs'][0]) for _ in range(31)]
    app = create_app(config(LIVE_AQ=False))
    store = app.extensions['assessment_runs']
    monkeypatch.setattr(store, 'page', lambda *_: page(document))

    def queue_page(run_id, number, view):
        batch = sample()
        batch.update(page=number, pages=3, result_view=view)
        return batch

    monkeypatch.setattr(store, 'queue_page', queue_page)
    client = app.test_client()
    url = '/runs/example/visualization?queue_page=2&queue_view=all'

    def follow(html, label):
        href = re.search(r'href="([^"]+)">' + label + r'</a>', html).group(1)
        return unescape(href)

    try:
        first = visual_response(client, url)
        assert (first['start'], first['stop'], first['total']) == (1, 30, 31)
        assert first['rows'][-2]['display_number'] == 30
        queue_number = first['rows'][-1]['display_number']
        second_url = follow(client.get(url).text, 'Next comparisons')
        second = visual_response(client, second_url)
        assert (second['start'], second['stop'], second['total']) == (31, 31, 31)
        assert [r['display_number'] for r in second['rows']] == [31, queue_number]
        assert (second['queue_page'], second['queue_view']) == (2, 'all')
        next_queue = follow(client.get(second_url).text, 'Next Queue match batch')
        third = visual_response(client, next_queue)
        assert (third['plot_page'], third['queue_page'], third['queue_view']) == (2, 3, 'all')
        assert third['rows'][-1]['display_number'] != queue_number
    finally:
        store.close()
