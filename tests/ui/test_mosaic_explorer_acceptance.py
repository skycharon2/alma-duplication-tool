"""P0 Mosaic Explorer acceptance over immutable captured and synthetic evidence.

These tests deliberately do not acquire live ALMA data or assign scientific
truth. They compare saved report records to the rendered read-only explorer.
"""
from copy import deepcopy
import re

from bs4 import BeautifulSoup
import pytest

from alma_duplicate.ui.mosaic_visualization import (
    archive_rows, position_chart, queue_rows, spectral_overview,
)
from tests.ui.test_mosaic_execution import browser as case2_browser, form, upload  # noqa: F401
from tests.ui.test_queue_geometry_visualization import sample


def test_case2_archive_saved_report_equals_explorer_and_is_not_mutated(case2_browser):  # noqa: F811
    client, discovery_calls = case2_browser
    token = upload(client)
    response = client.post('/proposed/mosaic', data=form() | dict(
        action='assess', mosaic_upload_token=token, setup_complete=''))
    assert response.status_code == 303
    url = response.headers['Location']
    run_id = url.split('/runs/', 1)[1].split('?', 1)[0]
    report_before = client.get(url + '/download/report').data
    request_before = client.get(url + '/download/request').data
    retained = client.get(url + '/download/request').json
    proposed = retained['mosaic_pointings']
    assert len(proposed['points']) == 3

    stored_page = client.application.extensions['assessment_runs'].page(run_id, 1, 'matches')
    rows = list(archive_rows(stored_page))
    assert rows
    assert all(row['source'] == 'Archive' and row['status'] == 'CRITERIA_MET'
               and row['intent'] == 'LINE' for row in rows)
    charts = [position_chart(row, proposed) for row in rows]
    contexts = {item['record']['context_id']: item['record']
                for entry in stored_page['candidate_entries'] for item in entry['contexts']}

    calls_before = len(discovery_calls)
    result = client.get(url + '/mosaic-visualization')
    assert result.status_code == 200
    soup = BeautifulSoup(result.data, 'html.parser')
    assert len(soup.select('[data-row]')) == len(rows)
    assert soup.find('summary', string='Submitted Mosaic pointings (3)')
    assert soup.find('a', string='Back to text report')['href'].startswith(url)

    for i, (row, chart) in enumerate(zip(rows, charts)):
        coverage = contexts[row['context_id']]['coverage']
        assert row['inside'] == coverage['inside_count']
        assert row['total'] == coverage['pointing_count'] == len(proposed['points'])
        assert row['outcome'] == coverage['outcome']
        assert chart['available'], f'Saved Case 2 geometry missing: {chart.get("reason")}'
        panel = soup.select_one(f'#charts > section:first-child [data-evidence="{i}"]')
        assert panel is not None
        markers = panel.select('path.proposed-marker')
        assert len(markers) == len(proposed['points'])
        for marker, point in zip(markers, chart['points']):
            numbers = re.fullmatch(r'translate\(([^ ]+) ([^ ]+)\)', marker['transform'])
            assert numbers is not None
            assert float(numbers[1]) == pytest.approx(point['xy'][0], abs=1e-7)
            assert float(numbers[2]) == pytest.approx(point['xy'][1], abs=1e-7)
        assert len(panel.select('g.footprint > polygon')) == len(chart['outlines'])

        detail = soup.select_one(f'[data-evidence="{i}"] a[href*="#"]')
        assert detail is not None
        assert detail['href'].endswith('#' + row['anchor'])
        assert BeautifulSoup(client.get(detail['href'].split('#')[0]).data,
                             'html.parser').find(id=row['anchor']) is not None
        recorded = [spectrum for spectrum in row['spectra'] if spectrum.get('available')]
        assert recorded
        frequencies = soup.select_one(
            f'#charts > section:nth-of-type(2) [data-evidence="{i}"]')
        assert frequencies is not None
        assert len(frequencies.select('svg text[data-select-pair]')) == len(recorded)
        overview = spectral_overview(row['spectra'])
        assert overview is not None
        assert [int(n['data-select-pair']) for n in frequencies.select('svg [data-select-pair]')] == [
            item['number'] for item in overview['rows']]
        for segment, item in zip(frequencies.select('g.candidate-spectrum > line'),
                                 (r for r in overview['rows'] if r['kind'] == 'interval')):
            assert float(segment['x1']) == pytest.approx(item['low'], abs=1e-7)
            assert float(segment['x2']) == pytest.approx(item['high'], abs=1e-7)
        diamonds = frequencies.select('svg path.proposed-marker')
        assert len(diamonds) == len(overview['rows'])
        for diamond, item in zip(diamonds, overview['rows']):
            position = re.fullmatch(r'translate\(([^ ]+) ([^ ]+)\)', diamond['transform'])
            assert position is not None
            assert float(position[1]) == pytest.approx(item['proposed'], abs=1e-7)

    assert len(discovery_calls) == calls_before
    assert client.get(url + '/download/report').data == report_before
    assert client.get(url + '/download/request').data == request_before
    assert client.get(url + '/visualization').status_code == 404  # Single-only endpoint
    assert client.get(url + '/mosaic-visualization?page=999').status_code == 404
    assert client.get(url + '/mosaic-visualization?view=review').status_code == 400


def test_queue_array_candidate_binding_and_unknown_are_not_promoted_to_matches():
    page = sample()
    before = deepcopy(page)
    rows = list(queue_rows(page))
    assert len(rows) == 1
    row = rows[0]
    assert (row['source'], row['candidate'], row['geometry'], row['array']) == (
        'Queue', 'candidate-1', 'RECTANGLE', '12 m')
    assert row['status'] == 'CRITERIA_MET'
    assert row['footprint_evidence']['snapshot'] == 'abc'
    chart = position_chart(row, dict(points=[
        dict(id='proposed-1', frame='ICRS', ra_deg=0., dec_deg=0.)]))
    assert chart['available'] and len(chart['outlines']) == 2
    assert page == before

    # A nonmatching/unknown result stays absent from a matching-only explorer.
    page['document']['geometry_reports']['RECTANGLE']['candidates'][0]['science']['variants'][0]['branches'][0].update(
        truth='UNKNOWN', status='INDETERMINATE')
    assert list(queue_rows(page)) == []


def test_missing_footprint_and_oversized_proposal_do_not_draw_partial_geometry():
    row = next(queue_rows(sample()))
    proposed = dict(points=[dict(id='p1', frame='ICRS', ra_deg=0., dec_deg=0.)])
    row['footprint_evidence']['variant']['coverage']['complete'] = False
    result = position_chart(row, proposed)
    assert not result['available']

    row = next(queue_rows(sample()))
    proposed['points'] = [dict(id=f'p{i}', frame='ICRS', ra_deg=0., dec_deg=0.)
                          for i in range(2001)]
    result = position_chart(row, proposed)
    assert not result['available'] and '2000' in result['reason']
