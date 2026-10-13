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
