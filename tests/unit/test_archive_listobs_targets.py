"""Target selection from a captured multi-target original MeasurementSet."""
from pathlib import Path

import pytest

from alma_duplicate.parsers.archive_listobs import parse_science_fields
from alma_duplicate.archive_auxiliary import inspect_auxiliary
from tests.unit.test_archive_auxiliary import archive_bytes

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/archive/mosaic_target_selection_2026_10_26'
RAW = (FIXTURE / 'lmc-listobs.txt').read_bytes()
ASDM = 'uid://A002/Xb8f857/X3977'


@pytest.mark.parametrize('target,ids', [('LMC0NT197', [2, 3, 4]),
    ('LMC1N127', [6, 7, 8]), ('LMC2N113', [9, 10, 11])])
def test_select_exact_target(target, ids):
    excluded = []
    result = parse_science_fields(RAW, asdm_uid=ASDM, target_name=target, exclusions=excluded)
    assert [f.field_id for f in result.fields] == ids
    assert all(f.target_name == target and f.scans for f in result.fields)
    assert len(excluded) == 6
    assert all(e['target_name'] != target and e['scan_ids'] for e in excluded)


def test_unknown_target_is_not_empty_success():
    with pytest.raises(ValueError, match='requested target'):
        parse_science_fields(RAW, asdm_uid=ASDM, target_name='LMC')


def test_other_target_scan_field_disagreement_rejected():
    scans, fields = RAW.split(b'Fields:', 1)
    corrupted = scans.replace(b'LMC1N127', b'OTHER') + b'Fields:' + fields
    with pytest.raises(ValueError, match='name/frame mismatch'):
        parse_science_fields(corrupted, asdm_uid=ASDM, target_name='LMC0NT197')


def test_acquisition_records_excluded_fields(tmp_path):
    archive = tmp_path / 'auxiliary.tar'
    archive.write_bytes(archive_bytes([('qa/weblog.tgz', archive_bytes([('listobs.txt', RAW)]))]))
    report, selected = inspect_auxiliary(archive, asdm_uid=ASDM, source_name='LMC0NT197')
    assert report['status'] == 'FOUND' and selected == RAW
    assert report['selected']['science_field_count'] == 3
    assert len(report['selected']['excluded_science_fields']) == 6


def test_startup_log_does_not_supply_pointings():
    with pytest.raises(ValueError, match='MeasurementSet'):
        parse_science_fields((FIXTURE / 'n55-calibrated.log').read_bytes(),
                             asdm_uid=ASDM, target_name='N55')
