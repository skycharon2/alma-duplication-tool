"""Candidate groups preserve every record and reject non-transitive ambiguity."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic
from alma_duplicate.archive_mosaic_groups import group_pointings
from alma_duplicate.cli import archive_mosaic_groups as cli


def execution(uid, positions):
    return dict(project_code='P', member_ous_uid='M', source_name='S', asdm_uid=uid,
        evidence=dict(fields=[dict(field_id=i, source_id=0, target_name='S', frame='ICRS',
            ra_deg=10 + offset / 3600, dec_deg=0, ra_original=str(offset), dec_original='0',
            scans=[dict(scan_id=1, spw_ids=[2])]) for i, offset in positions]))


def group(*executions):
    return group_pointings(list(executions), tolerance_arcsec=1)


def test_full_group_different_ids_preserves_records():
    items = [execution('A', [(1, 0)]), execution('B', [(9, 0.2)]), execution('C', [(4, 0.4)])]
    before = deepcopy(items)
    report = group(*items)
    assert report['status_counts'] == {'CANDIDATE_FULL': 1}
    assert report['field_record_count'] == 3
    assert len(report['groups'][0]['members']) == 3
    assert items == before
    assert report['representative_coordinate_status'] == 'NOT_COMPUTED'


def test_tolerance_chain_not_merged():
    report = group(execution('A', [(1, 0)]), execution('B', [(1, 0.8)]), execution('C', [(1, 1.6)]))
    item = report['groups'][0]
    assert item['status'] == 'AMBIGUOUS'
    assert item['ambiguity_reasons'] == ['NON_TRANSITIVE_TOLERANCE_CHAIN']
    assert len(item['outside_tolerance_pairs']) == 1
    assert item['maximum_pair_separation_arcsec'] == pytest.approx(1.6)


def test_multiple_fields_same_execution_ambiguous():
    report = group(execution('A', [(1, 0), (2, 0.2)]), execution('B', [(1, 0.1)]))
    item = report['groups'][0]
    assert item['status'] == 'AMBIGUOUS'
    assert item['duplicate_execution_uids'] == ['A']
    assert item['member_count'] == 3


def test_partial_group_and_singleton_keep_missing_scope():
    report = group(execution('A', [(1, 0)]), execution('B', [(1, 0)]), execution('C', [(1, 10)]))
    assert report['status_counts'] == {'CANDIDATE_PARTIAL': 1, 'UNMATCHED': 1}
    assert report['groups'][0]['missing_execution_uids'] == ['C']
    keys = [(m['asdm_uid'], m['field_id']) for g in report['groups'] for m in g['members']]
    assert len(keys) == len(set(keys)) == 3


def test_order_independent_ids_and_output():
    a, b = execution('A', [(2, 10), (1, 0)]), execution('B', [(4, 0), (3, 10)])
    first = group(a, b)
    a['evidence']['fields'].reverse()
    b['evidence']['fields'].reverse()
    assert group(b, a) == first


@pytest.mark.parametrize('tolerance', [0, -1, float('nan')])
def test_invalid_tolerance(tolerance):
    with pytest.raises(ValueError):
        group_pointings([execution('A', [(1, 0)]), execution('B', [(1, 0)])], tolerance_arcsec=tolerance)


def test_real_ic1954_forms_22_candidates():
    fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/archive/mosaic_multi_execution_2026_10_23'
    audit = json.loads((fixture / 'package_audit.json').read_text())
    executions = []
    for candidate in audit['inspection']['candidates']:
        if candidate.get('measurement_set_variant') != 'ORIGINAL':
            continue
        raw = (fixture / 'listobs' / (candidate['sha256'] + '.txt')).read_bytes()
        executions.append(asdict(reconstruct_archive_mosaic(raw, project_code='2017.1.00886.L',
            member_ous_uid=audit['member_ous_uid'], source_name='IC1954',
            asdm_uid=candidate['reported_asdm_uid'], metadata_reference='discovery.json')))
    report = group_pointings(executions, tolerance_arcsec=0.1)
    assert report['status_counts'] == {'CANDIDATE_FULL': 22}
    assert report['field_record_count'] == 66
    assert all(g['member_count'] == 3 and g['maximum_pair_separation_arcsec'] == 0 for g in report['groups'])


def test_cli_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'load_package_executions', lambda path:
        ([execution('A', [(1, 0)]), execution('B', [(1, 0)])], {'verification_scope': 'TEST'}))
    output = tmp_path / 'groups.json'
    args = ['--package-audit-dir', str(tmp_path), '--tolerance-arcsec', '1', '--output', str(output)]
    assert cli.main(args) == 0
    original = output.read_bytes()
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    assert output.read_bytes() == original
