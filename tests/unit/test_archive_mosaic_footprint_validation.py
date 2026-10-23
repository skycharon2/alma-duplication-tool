"""Boundary sweep and sampled polygon scope checks without network access."""
from pathlib import Path
import pytest
from alma_duplicate.archive_mosaic_footprint_validation import validate_footprints, region_vertices


def readiness():
    field = dict(asdm_uid='A', field_id=1, frame='ICRS', ra_deg=359.999, dec_deg=80,
        ra_original='original', dec_original='original', input_status='EVIDENCE_BOUND',
        scans=[dict(scan_id=1, spw_ids=[16, 18])], explicit_full_res_spw_ids=[16, 18],
        spectral_windows=[dict(spw_id=16, frame='TOPO', reported_centre_hz=100e9),
                          dict(spw_id=18, frame='TOPO', reported_centre_hz=200e9)])
    return dict(member_ous_uid='M', source_name='S', provenance={}, executions=[dict(asdm_uid='A',
        array_evidence=dict(status='BOUND'), antenna_evidence=dict(diameters_m=[7.0]),
        fields=[field], listobs_sha256='test')])


def run(**kwargs):
    args = dict(asdm_uid='A',spw_ids=[16,18],hpbw_coefficient=1.13,frequency_choice='reported-spw-centre',
        assume_uniform_field_antennas=True,boundary_epsilon_arcsec=1e-6,boundary_offset_arcsec=0.01)
    args.update(kwargs)
    return validate_footprints(readiness(), **args)


def test_all_bearings_at_high_declination_and_wrap():
    report = run()
    assert report['status'] == 'DIAGNOSTIC_CHECKS_PASSED'
    assert report['inverse_frequency_scaling_passed']
    for item in report['runs']:
        assert len(item['boundary_probes']['points']) == 13
        assert item['union_status_counts'] == {'INSIDE':5, 'BOUNDARY':4, 'OUTSIDE':4}
    assert report['runs'][0]['footprint']['half_power_radius_arcsec'] == pytest.approx(2 * report['runs'][1]['footprint']['half_power_radius_arcsec'])


@pytest.mark.parametrize('options', [dict(spw_ids=[]),dict(spw_ids=[16,16]),
    dict(boundary_epsilon_arcsec=-1),dict(boundary_offset_arcsec=1e-7),dict(boundary_offset_arcsec=1000)])
def test_bad_validation_options(options):
    with pytest.raises(ValueError):run(**options)


REGION = Path(__file__).resolve().parents[2] / 'tests/fixtures/archive/mosaic_region_2026_10_23/metadata.xml'


def parse(raw):
    return region_vertices(raw,member='uid://A001/X1284/X28b7',source='IC1954',asdm='uid://A002/Xc63024/X4c8')


def test_real_region_capture_is_only_vertex_evidence():
    result = parse(REGION.read_bytes())
    assert len(result['vertices']) >= 3
    assert result['frequency_relation'] == 'NOT_ESTABLISHED_WITH_SELECTED_LISTOBS_SPW'
    assert result['metadata_sha256']


def test_mismatched_region_identity_rejected():
    with pytest.raises(ValueError):
        parse(REGION.read_bytes().replace(b'IC1954',b'OTHER'))


def test_polygon_probe_does_not_certify_region_equivalence():
    raw = REGION.read_bytes()
    parsed = parse(raw)
    r = readiness()
    r['member_ous_uid']='uid://A001/X1284/X28b7';r['source_name']='IC1954'
    e=r['executions'][0];e['asdm_uid']='uid://A002/Xc63024/X4c8'
    f=e['fields'][0];f['asdm_uid']=e['asdm_uid'];f['ra_deg']=parsed['vertices'][0]['ra_deg'];f['dec_deg']=parsed['vertices'][0]['dec_deg']
    report=validate_footprints(r,asdm_uid=e['asdm_uid'],spw_ids=[16],hpbw_coefficient=1.13,
        frequency_choice='reported-spw-centre',assume_uniform_field_antennas=True,
        boundary_epsilon_arcsec=1e-6,boundary_offset_arcsec=0.01,region_raw=raw)
    comparison=report['runs'][0]['s_region_vertex_comparison']
    assert comparison['probes']['points'][0]['status']=='INSIDE'
    assert report['policy_status']=='NOT_EVALUATED'
    assert 'NOT_HALF_POWER_GROUND_TRUTH' in comparison['interpretation']
