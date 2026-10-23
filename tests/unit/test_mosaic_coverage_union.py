from copy import deepcopy
import json
import pytest
from test_archive_mosaic_footprint import inputs
from test_ot_pointings import proposed
from alma_duplicate.mosaic_coverage_union import assess_union
from alma_duplicate.cli import proposed_mosaic as cli


def ready(offset=0):
    r = inputs()
    e = deepcopy(r['executions'][0]); e['asdm_uid'] = 'B'
    e['fields'][0]['asdm_uid'] = 'B'; e['fields'][0]['ra_deg'] = offset
    r['executions'].append(e)
    return r


def run(r=None, p=None, selections=None):
    return assess_union(p or proposed('0,0,Absolute,Degrees\n1,0,Absolute,Degrees'),
        r or ready(), selections=selections if selections is not None else [
            dict(asdm_uid='A',spw_id=16),dict(asdm_uid='B',spw_id=16)],
        hpbw_coefficient=1.13, boundary_epsilon_arcsec=1e-6, assume_uniform_field_antennas=True)


def test_identical_execution_centres_do_not_multiply_counts():
    r = run()
    assert r['circle_count'] == 2 and r['status_counts']['INSIDE'] == 1
    assert r['spatial_condition'] == 'NOT_MET'
    hits = r['probe_results']['points'][0]['inside_circles']
    assert [h['asdm_uid'] for h in hits] == ['A','B']
    assert all(h['field_id'] == 1 for h in hits)


def test_disjoint_union_and_selection_scope():
    r = run(ready(1))
    assert r['spatial_condition'] == 'MET' and r['covered_fraction_lower'] == 1
    r = run(ready(1), selections=[dict(asdm_uid='A',spw_id=16)])
    assert r['unselected_asdm_uids'] == ['B'] and r['spatial_condition'] == 'NOT_MET'
    assert r['archive_completeness'] == 'MEMBER_COMPLETENESS_NOT_ESTABLISHED'


def test_each_execution_uses_its_own_frequency():
    r = ready(); r['executions'][1]['fields'][0]['spectral_windows'][0]['reported_centre_hz'] *= 2
    result = run(r)
    assert result['circles'][0]['radius_arcsec'] == pytest.approx(2*result['circles'][1]['radius_arcsec'])
    assert result['spectral_compatibility'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('selections', [[],[dict(asdm_uid='Z',spw_id=16)],
    [dict(asdm_uid='A',spw_id=16)]*2,[dict(asdm_uid='A',spw_id=True)],
    [dict(asdm_uid='B',spw_id=99)],{},[dict(asdm_uid='A')]])
def test_invalid_selection_fails_atomically(selections):
    with pytest.raises(ValueError): run(selections=selections)


def test_mixed_arrays_and_unready_selected_input_fail():
    r = ready(); r['executions'][1]['antenna_evidence']['diameters_m'] = [7.0]
    with pytest.raises(ValueError,match='Cross-array'): run(r)
    r = ready(); r['executions'][1]['fields'][0]['input_status'] = 'NOT_READY'
    with pytest.raises(ValueError): run(r)


def test_incomplete_proposed_list_and_boundary():
    p = proposed('0,0,Absolute,Degrees',False)
    assert run(p=p)['spatial_condition'] == 'PROPOSED_COMPLETENESS_UNCONFIRMED'
    radius = run()['circles'][0]['radius_arcsec']/3600
    p = proposed(f'0,0,Absolute,Degrees\n{radius},0,Absolute,Degrees')
    assert run(p=p)['spatial_condition'] == 'BOUNDARY_UNRESOLVED'


def test_cli_union_and_exclusive_single_selection(tmp_path, monkeypatch):
    from test_ot_pointings import raw
    f = tmp_path/'pointings.txt'; f.write_bytes(raw('0,0,Absolute,Degrees'))
    s = tmp_path/'selection.json'; s.write_text(json.dumps([dict(asdm_uid='A',spw_id=16),dict(asdm_uid='B',spw_id=16)]))
    out = tmp_path/'out.json'
    monkeypatch.setattr(cli,'build_readiness',lambda *a,**kw:ready())
    args = ['--pointings',str(f),'--source','S','--array','12m','--confirm-fixed-icrs',
        '--confirm-complete','--output',str(out),'--selections',str(s),'--package-audit-dir',str(tmp_path),
        '--array-catalog',str(tmp_path),'--hpbw-coefficient','1.13','--boundary-epsilon-arcsec','0.000001',
        '--assume-uniform-field-antennas']
    assert cli.main(args) == 0
    report = json.loads(out.read_text())
    assert report['status_counts']['INSIDE'] == 1
    assert report['position_criterion']['criterion_id'] == 'POS-MOSAIC'
    assert report['position_criterion']['outcome'] == 'SATISFIED'
    with pytest.raises(SystemExit): cli.main(args+['--asdm','A','--spw','16'])
