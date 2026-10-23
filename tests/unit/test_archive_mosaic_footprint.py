"""Explicit diagnostic assumptions, frequency scaling and spherical boundaries."""
from copy import deepcopy
import math
import pytest

from alma_duplicate.archive_mosaic_footprint import circular_footprint, probe_footprint


def inputs():
    field = dict(asdm_uid='A', field_id=1, frame='ICRS', ra_deg=0, dec_deg=0,
        ra_original='00:00:00', dec_original='+00.00.00', input_status='EVIDENCE_BOUND',
        scans=[dict(scan_id=4, spw_ids=[16])], explicit_full_res_spw_ids=[16],
        spectral_windows=[dict(spw_id=16, frame='TOPO', reported_centre_hz=100e9)])
    return dict(member_ous_uid='M', source_name='S', provenance={}, executions=[dict(asdm_uid='A',
        antenna_evidence=dict(diameters_m=[12.0]), array_evidence=dict(status='BOUND'),
        fields=[field], listobs_sha256='hash')])


def build(r=None, **kwargs):
    args = dict(asdm_uid='A', spw_id=16, hpbw_coefficient=1.13,
                frequency_choice='reported-spw-centre', assume_uniform_field_antennas=True)
    args.update(kwargs)
    return circular_footprint(r or inputs(), **args)


def test_half_width_not_full_width():
    result = build()
    expected = 1.13 * 299792458 / 100e9 / 12 * 180 / math.pi * 3600
    assert result['hpbw_arcsec'] == pytest.approx(expected)
    assert result['half_power_radius_arcsec'] == pytest.approx(expected / 2)
    assert result['policy_status'] == 'NOT_EVALUATED'


def test_inverse_frequency_and_diameter_scaling():
    r = inputs()
    r['executions'][0]['fields'][0]['spectral_windows'][0]['reported_centre_hz'] *= 2
    assert build(r)['half_power_radius_arcsec'] == pytest.approx(build()['half_power_radius_arcsec'] / 2)
    r['executions'][0]['antenna_evidence']['diameters_m'] = [7.0]
    assert build(r)['half_power_radius_arcsec'] == pytest.approx(build()['half_power_radius_arcsec'] / 2 * 12 / 7)


def test_boundary_inside_outside_and_ra_wrap():
    f = build()
    radius = f['half_power_radius_arcsec'] / 3600
    points = [dict(id='centre', frame='ICRS', ra_deg=0, dec_deg=0),
              dict(id='edge', frame='ICRS', ra_deg=radius, dec_deg=0),
              dict(id='outside', frame='ICRS', ra_deg=radius * 1.01, dec_deg=0),
              dict(id='wrap', frame='ICRS', ra_deg=360 - radius / 2, dec_deg=0)]
    r = probe_footprint(f, points, boundary_epsilon_arcsec=1e-6)
    assert [p['status'] for p in r['points']] == ['INSIDE', 'BOUNDARY', 'OUTSIDE', 'INSIDE']


def test_union_inside_overrides_another_circle_boundary():
    f = build()
    other = deepcopy(f['circles'][0]); other['field_id'] = 2
    other['ra_deg'] = other['radius_arcsec'] / 3600
    f['circles'].append(other)
    r = probe_footprint(f, [dict(id='p', frame='ICRS', ra_deg=0, dec_deg=0)], boundary_epsilon_arcsec=1e-6)['points'][0]
    assert r['status'] == 'INSIDE' and r['inside_field_ids'] == [1] and r['boundary_field_ids'] == [2]


@pytest.mark.parametrize('kwargs', [dict(hpbw_coefficient=0), dict(hpbw_coefficient=float('nan')),
    dict(assume_uniform_field_antennas=False), dict(frequency_choice='average'), dict(spw_id=99)])
def test_invalid_or_missing_choices(kwargs):
    with pytest.raises(ValueError): build(**kwargs)


@pytest.mark.parametrize('change', ['mixed', 'array', 'missing', 'frame', 'nonpositive', 'unready', 'not_full_res'])
def test_unready_inputs_never_become_footprints(change):
    r = inputs(); e = r['executions'][0]; f = e['fields'][0]
    if change == 'mixed': e['antenna_evidence']['diameters_m'] = [7.0, 12.0]
    if change == 'array': e['array_evidence']['status'] = 'UNKNOWN'
    if change == 'missing': f['spectral_windows'] = []
    if change == 'frame': f['spectral_windows'][0]['frame'] = 'LSRK'
    if change == 'nonpositive': f['spectral_windows'][0]['reported_centre_hz'] = 0
    if change == 'unready': f['input_status'] = 'NOT_READY'
    if change == 'not_full_res': f['explicit_full_res_spw_ids'] = []
    with pytest.raises(ValueError): build(r)


def test_unselected_field_is_reported_not_borrowed():
    r = inputs(); f = deepcopy(r['executions'][0]['fields'][0]); f['field_id'] = 2
    f['scans'] = [dict(scan_id=5, spw_ids=[18])]
    r['executions'][0]['fields'].append(f)
    result = build(r)
    assert len(result['circles']) == 1 and result['excluded_field_ids'] == [2]
