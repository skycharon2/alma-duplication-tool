"""Legacy QA discovery preserves evidence without manufacturing ready pointings."""
from pathlib import Path

import pytest
from alma_duplicate.parsers.archive_qa_text import inspect_qa_text
from alma_duplicate.archive_auxiliary import inspect_auxiliary
from tests.unit.test_archive_auxiliary import archive_bytes

RAW = next(Path('tests/fixtures/archive/legacy_qa_text_2026_10_26').glob('*__textfile.txt')).read_bytes()


def test_real_legacy_fields_are_not_ready():
    r = inspect_qa_text(RAW, target_name='RX_J1347.5-1145')
    assert r['status'] == 'LEGACY_QA_SCIENCE_FIELDS_IDENTIFIED'
    assert [f['field_id'] for f in r['science_fields']] == list(range(3, 10))
    assert [f['field_id'] for f in r['excluded_fields']] == [2]
    assert [f['field_id'] for f in r['fields']] == list(range(2, 10))
    assert r['position_status'] == 'NOT_READY'
    assert all(f['reported_frame'] == 'J2000' for f in r['fields'])
    assert inspect_qa_text(RAW, target_name='RX_J1347')['fields'] == []


def test_acquisition_retains_alternative_not_listobs(tmp_path):
    tar = tmp_path/'aux.tar'
    tar.write_bytes(archive_bytes([('qa/example__textfile.txt', RAW)]))
    report, selected = inspect_auxiliary(tar, asdm_uid='uid://A002/X984bbe/X2df7',
        source_name='RX_J1347.5-1145', capture_dir=tmp_path/'captured')
    assert selected is None and report['status'] == 'NOT_FOUND'
    assert report['candidates'] == []
    evidence = report['alternative_evidence'][0]
    assert (tmp_path/'captured'/(evidence['sha256']+'.txt')).read_bytes() == RAW
    assert len(evidence['fields']) == 8


@pytest.mark.parametrize('name', ['../qa/example__textfile.txt', 'qa/example__textfile.txt'])
def test_unsafe_legacy_members_rejected(tmp_path, name):
    tar = tmp_path/'aux.tar'
    tar.write_bytes(archive_bytes([(name, None)]))
    with pytest.raises(ValueError):
        inspect_auxiliary(tar, asdm_uid='uid://A002/X984bbe/X2df7', source_name='RX_J1347.5-1145')


def test_multiple_summaries_not_selected():
    assert inspect_qa_text(RAW+RAW, target_name='RX_J1347.5-1145')['status'] == 'UNSUPPORTED_QA_LAYOUT'


@pytest.mark.parametrize('old,new,reason', [
    (b'9    3    2', b'9    3   99', 'QA_SCAN_FIELD_IDENTITY_CONFLICT'),
    (b'9    3    2', b'9   99    2', 'QA_SCAN_FIELD_IDENTITY_CONFLICT'),
    (b'RX_J1347.5-1*', b'WRONG*', 'QA_SCAN_FIELD_NAME_CONFLICT'),
    (b'Obs Target', b'Unknown Intent', 'QA_SCAN_INTENT_UNSUPPORTED'),
    (b'13:47:30.54000', b'25:47:30.54000', 'Invalid RA'),
])
def test_bad_qa_binding_cannot_produce_science_fields(old, new, reason):
    r = inspect_qa_text(RAW.replace(old, new), target_name='RX_J1347.5-1145')
    assert r['status'] == 'INVALID_QA_EVIDENCE'
    assert r['science_fields'] == []
    assert reason in r['reasons'][0]
