from pathlib import Path
import json
import math
import pytest
from alma_duplicate.parsers.ot_pointings import parse_ot_pointings
from alma_duplicate.proposed_mosaic import import_proposed, assess_proposed
from alma_duplicate.cli.proposed_mosaic import main
from test_archive_mosaic_footprint import inputs, build

HEADER = 'RA,Dec,Coordinate Type,Coordinate Units\n--   This signals end of the header\n'
FIXTURES = Path(__file__).parents[1] / 'fixtures/ot_pointings'


def raw(rows):
    return (HEADER + rows).encode()


def proposed(rows, complete=True):
    return import_proposed(raw(rows), source_name='Proposed', array='12m',
                           confirm_fixed_icrs=True, confirm_complete=complete)


def assess(p):
    return assess_proposed(p, inputs(), asdm_uid='A', spw_id=16, hpbw_coefficient=1.13,
                          boundary_epsilon_arcsec=1e-6, assume_uniform_field_antennas=True)


def test_native_precision_and_duplicates_preserved():
    degrees = parse_ot_pointings((FIXTURES/'c04_degrees.txt').read_bytes())
    sex = parse_ot_pointings((FIXTURES/'c04_sexagesimal.txt').read_bytes())
    assert degrees['row_count'] == sex['row_count'] == 3
    assert degrees['points'][0]['ra_deg'] != degrees['points'][1]['ra_deg']
    assert degrees['duplicate_coordinates'] == []
    assert sex['duplicate_coordinates'] == [{'id':'row-2', 'same_coordinates_as':'row-1'}]
    assert [p['line_number'] for p in sex['points']] == [3,4,5]


@pytest.mark.parametrize('row', ['1,2,Offset,ARCSECS', 'nan,2,Absolute,Degrees',
    '360,0,Absolute,Degrees', '0,-91,Absolute,Degrees', '1,2,Absolute,Unknown',
    '24:00:00,00:00:00,Absolute,Sexagesimal', '12:60:00,00:00:00,Absolute,Sexagesimal',
    '12:00:00,-90:00:01,Absolute,Sexagesimal', '1,2,Absolute'])
def test_invalid_row_is_not_skipped(row):
    with pytest.raises(ValueError, match='Line 3'):
        parse_ot_pointings(raw(row))


def test_units_wrap_and_negative_zero_dec():
    p = parse_ot_pointings(raw('23:59:59.9999,-00:00:01,absolute,sexagesimal'))['points'][0]
    assert 359.99 < p['ra_deg'] < 360 and p['dec_deg'] == pytest.approx(-1/3600)
    p = parse_ot_pointings(raw(f'{math.pi},{-math.pi/6},Absolute,Radians'))['points'][0]
    assert p['ra_deg'] == pytest.approx(180) and p['dec_deg'] == pytest.approx(-30)


def test_strict_majority_overlap_and_incomplete():
    r = assess(proposed('0,0,Absolute,Degrees\n1,0,Absolute,Degrees'))
    assert r['spatial_condition'] == 'NOT_MET' and r['covered_fraction_upper'] == .5
    r = assess(proposed('0,0,Absolute,Degrees\n0,0,Absolute,Degrees\n1,0,Absolute,Degrees'))
    assert r['spatial_condition'] == 'MET' and r['pointing_count'] == 3
    assert r['policy_status'] == 'NOT_EVALUATED'
    assert r['probe_results']['points'][0]['circle_relations'][0]['separation_arcsec'] == 0
    assert assess(proposed('0,0,Absolute,Degrees', False))['spatial_condition'] == 'PROPOSED_COMPLETENESS_UNCONFIRMED'


def test_boundary_interval():
    radius = build()['half_power_radius_arcsec']/3600
    r = assess(proposed(f'0,0,Absolute,Degrees\n{radius},0,Absolute,Degrees'))
    assert r['spatial_condition'] == 'BOUNDARY_UNRESOLVED'
    assert r['covered_fraction_lower'] == .5 and r['covered_fraction_upper'] == 1


def test_binding_required_and_cross_array_rejected():
    with pytest.raises(ValueError):
        import_proposed(raw('0,0,Absolute,Degrees'),source_name='S',array='12m')
    p = proposed('0,0,Absolute,Degrees'); p['array'] = '7m'
    with pytest.raises(ValueError,match='Cross-array'): assess(p)


def test_cli_import_and_no_overwrite(tmp_path):
    output = tmp_path/'report.json'
    args = ['--pointings',str(FIXTURES/'c04_degrees.txt'),'--source','S','--array','12m',
            '--confirm-fixed-icrs','--output',str(output)]
    assert main(args) == 0
    assert json.loads(output.read_text())['completeness'] == 'NOT_CONFIRMED'
    with pytest.raises(SystemExit) as exc: main(args)
    assert exc.value.code == 2


@pytest.mark.parametrize('payload', [b'', raw(''), raw('0,0,Absolute,Degrees\n0,0,Absolute,Radians'),
    raw('0,0,Absolute,Degrees\ninvalid'), b'Name,RA,Dec\n--\nS,0,0'])
def test_empty_mixed_and_partial_inputs_fail(payload):
    with pytest.raises(ValueError): parse_ot_pointings(payload)


def test_multiple_archive_hits_count_once():
    from copy import deepcopy
    readiness = inputs()
    other = deepcopy(readiness['executions'][0]['fields'][0])
    other['field_id'] = 2
    readiness['executions'][0]['fields'].append(other)
    r = assess_proposed(proposed('0,0,Absolute,Degrees'), readiness, asdm_uid='A', spw_id=16,
        hpbw_coefficient=1.13, boundary_epsilon_arcsec=1e-6, assume_uniform_field_antennas=True)
    assert r['status_counts']['INSIDE'] == 1
    assert r['probe_results']['points'][0]['inside_field_ids'] == [1,2]
