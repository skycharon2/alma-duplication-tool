"""Minimal OT reference parity and geometry-only safety contracts."""
from dataclasses import replace
import json
from pathlib import Path

import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.queue_rectangle_grid import RectangleGeometry, generate_rectangle_grid, reconstruct_queue_rectangles
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes

CASES = json.loads((Path(__file__).parents[1]/'fixtures/queue/rectangle_reference.json').read_text())
BASE = RectangleGeometry(150., 0., 0., 0., 90., 90., 0., 27.8048262154, 'ICRS')


def grid(g=BASE, **kw):
    return generate_rectangle_grid(g, 12., spacing_reference_diameter_m=12., **kw)


@pytest.mark.parametrize('case', CASES)
def test_ot_reference(case):
    g = replace(BASE, length_arcsec=case['length'], width_arcsec=case['width'],
                pa_deg=case['pa'], spacing_arcsec=case['spacing'])
    r = generate_rectangle_grid(g, case['diameter'], spacing_reference_diameter_m=case['diameter'])
    assert r['pointing_count'] == len(r['pointings']) == case['count']
    for index, expected in zip([0, case['count']//2, -1], case['reference_offsets']):
        p = r['pointings'][index]
        assert p['east_arcsec'] == pytest.approx(expected['east'], abs=1e-8)
        assert p['north_arcsec'] == pytest.approx(expected['north'], abs=1e-8)
        # Spherical projection is provisional; OT fixture used planar Dec=0.
        assert (p['ra_deg']-150)*3600 == pytest.approx(expected['east'], abs=1e-5)
        assert p['dec_deg']*3600 == pytest.approx(expected['north'], abs=1e-5)
    assert not r['scientific_candidate_complete']


@pytest.mark.parametrize('changes,reason', [
    ({'spacing_arcsec': 0}, 'NONPOSITIVE_SIZE_OR_SPACING'),
    ({'spacing_arcsec': float('nan')}, 'INVALID_OR_MISSING_GEOMETRY'),
    ({'spacing_arcsec': 1e-300}, 'POINTING_LIMIT_EXCEEDED'),
    ({'frame': 'galactic'}, 'COORDINATE_FRAME_UNRESOLVED'),
    ({'frame': ''}, 'COORDINATE_FRAME_UNRESOLVED'),
    ({'length_arcsec': None}, 'INVALID_OR_MISSING_GEOMETRY'),
])
def test_unresolved_never_returns_truncated_grid(changes, reason):
    r = grid(replace(BASE, **changes))
    assert r['reasons'] == [reason]
    assert r['pointings'] == [] and r['pointing_count'] == 0


def test_limit_and_exact_edge():
    assert grid(max_points=3)['reasons'] == ['POINTING_LIMIT_EXCEEDED']
    assert grid(replace(BASE, spacing_arcsec=10, length_arcsec=20, width_arcsec=1))['pointing_count'] == 3
    assert grid(replace(BASE, spacing_arcsec=10, length_arcsec=19.999999, width_arcsec=1))['pointing_count'] == 1


def test_nonzero_dec_offset_wrap_and_scaling():
    g = replace(BASE, ra_deg=359.999, dec_deg=-30, longitude_offset_arcsec=30, latitude_offset_arcsec=-20)
    r = grid(g)
    center = SkyCoord(*r['center_icrs_deg'], unit='deg')
    origin = SkyCoord(g.ra_deg, g.dec_deg, unit='deg')
    assert origin.separation(center).arcsec == pytest.approx(1300**.5, abs=1e-7)
    for p in r['pointings']:
        sky = SkyCoord(p['ra_deg'], p['dec_deg'], unit='deg')
        assert center.separation(sky).arcsec == pytest.approx((p['east_arcsec']**2+p['north_arcsec']**2)**.5, abs=1e-7)
        assert 0 <= p['ra_deg'] < 360
    seven = generate_rectangle_grid(BASE, 7., spacing_reference_diameter_m=12.)
    assert seven['spacing_arcsec'] == pytest.approx(BASE.spacing_arcsec*12/7)
    assert seven['pointing_count'] == 4


def test_snapshot_adapter_preserves_row_identity():
    source = parse_queue_csv_bytes((Path(__file__).parents[1]/'fixtures/queue/queue_pipeline_v1.csv').read_bytes())
    report = reconstruct_queue_rectangles(source)
    rows = report['candidates']
    assert len(rows) >= 2
    assert len({r['source_row_id'] for r in rows}) == len(rows)
    assert all(not r['scientific_candidate_complete'] for r in rows)
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('diameter', [12., 7.])
def test_production_d3_against_original_ot_coordinates(diameter):
    from alma_duplicate.queue_mosaic_binding import _match
    fixture = json.loads((Path(__file__).parents[1]/'fixtures/queue/rectangle_d3_reference.json').read_text())
    expected = next(a for a in fixture['arrays'] if a['diameter_m'] == diameter)
    result = generate_rectangle_grid(RectangleGeometry(**fixture['geometry']), diameter,
        spacing_reference_diameter_m=fixture['spacing_reference_diameter_m'])
    assert result['geometry_status'] == 'GEOMETRY_RECONSTRUCTED'
    predicted = SkyCoord([[p['ra_deg'], p['dec_deg']] for p in result['pointings']], unit='deg')
    # Reverse the independent OT export to ensure no reliance on file ordering.
    observed = SkyCoord(expected['coordinates_icrs_deg'][::-1], unit='deg')
    distances = predicted[:, None].separation(observed[None, :]).arcsec
    matching = _match([[j for j, value in enumerate(row) if value <= fixture['tolerance_arcsec']]
                       for row in distances])
    assert len(matching) == len(observed) == result['pointing_count'] == (10 if diameter == 12 else 5)
    assert len(set(matching.values())) == len(observed)
    assert max(distances[i, j] for i, j in matching.items()) <= fixture['tolerance_arcsec']
    assert result['grid_model_status'] == 'PROVISIONAL'


@pytest.mark.parametrize('spacing,frequency,status', [
    (27.804826215407775,107.,'CONSISTENT_WITH_12M_NYQUIST'),
    (20.,107.,'NONDEFAULT_SPACING_REFERENCE_REVIEW'),
    (20.,0.,'UNAVAILABLE'), (None,107.,'UNAVAILABLE')])
def test_spacing_diagnostic_is_nonblocking(spacing,frequency,status):
    from alma_duplicate.queue_rectangle_grid import spacing_diagnostic
    d=spacing_diagnostic(spacing,frequency)
    assert d['status']==status and d['blocking'] is False
    if spacing is not None and spacing>0:
        generated=grid(replace(BASE,spacing_arcsec=spacing))
        assert generated['spacing_arcsec']==spacing
        assert generated['geometry_status']=='GEOMETRY_RECONSTRUCTED'
