"""Real three-execution evidence and conservative package inventory boundaries."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

from alma_duplicate import archive_mosaic_package_audit as module

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/archive/mosaic_multi_execution_2026_10_23'


def run(tmp_path, monkeypatch, change=None):
    recorded = json.loads((FIXTURE / 'package_audit.json').read_text())
    candidates = recorded['inspection']['candidates']
    archive = tmp_path / 'test.tar'
    with tarfile.open(archive, 'w') as tar:
        entries = list(candidates)
        if change == 'duplicate':
            entries.append(next(c for c in candidates if c.get('measurement_set_variant') == 'ORIGINAL'))
        for index, candidate in enumerate(entries):
            if change == 'target_only' and candidate.get('measurement_set_variant') == 'ORIGINAL':
                continue
            raw = (FIXTURE / 'listobs' / (candidate['sha256'] + '.txt')).read_bytes()
            if change == 'invalid' and index == 0:
                raw = b'bad header'
            info = tarfile.TarInfo(f'{index}/listobs.txt')
            info.size = len(raw)
            tar.addfile(info, BytesIO(raw))
    monkeypatch.setattr(module, 'acquire_auxiliary', lambda *args, **kwargs:
                        (archive, dict(sha256=sha256(archive.read_bytes()).hexdigest()), True))
    return module.audit_package(metadata=FIXTURE / 'metadata.xml',
        capture_receipt=FIXTURE / 'inventory_receipt.json', receipt=FIXTURE / 'discovery.json',
        row_index=3, cache=tmp_path / 'cache', output=tmp_path / 'out',
        member='uid://A001/X1284/X28b7', source='IC1954')


def test_real_three_executions_not_one_tap_row(tmp_path, monkeypatch):
    report = run(tmp_path, monkeypatch)
    assert report['status'] == 'ADDITIONAL_EXECUTIONS_FOUND'
    assert len(report['tap_asdm_uids']) == 1
    assert report['additional_package_asdm_uids'] == ['uid://A002/Xc63024/X568e', 'uid://A002/Xc63024/X98b']
    assert {e['science_field_count'] for e in report['executions'].values()} == {22}
    for uid, entry in report['executions'].items():
        raw = (tmp_path / 'out' / entry['execution_file']).read_bytes()
        assert sha256(raw).hexdigest() == entry['sha256']
        doc = json.loads(raw)
        assert doc['execution']['asdm_uid'] == uid
        assert doc['execution']['metadata_status'] == 'MEMBER_PACKAGE_BOUND_NOT_TAP_EXECUTION_BOUND'
        assert doc['execution']['completeness'] == 'MEMBER_COMPLETENESS_NOT_ESTABLISHED'
        assert len(doc['execution']['evidence']['fields']) == 22


@pytest.mark.parametrize('change', ['duplicate', 'target_only', 'invalid'])
def test_uncertain_candidates_never_count_as_complete(tmp_path, monkeypatch, change):
    result = run(tmp_path, monkeypatch, change)
    assert result['status'] == 'UNRESOLVED'
    assert result['unresolved']


def test_no_overwrite(tmp_path, monkeypatch):
    run(tmp_path, monkeypatch)
    with pytest.raises(FileExistsError):
        run(tmp_path, monkeypatch)


def rerun(tmp_path, output):
    from alma_duplicate.archive_mosaic_batch import run_batch
    return run_batch(metadata=FIXTURE / 'metadata.xml',
        capture_receipt=FIXTURE / 'inventory_receipt.json',
        member='uid://A001/X1284/X28b7', source='IC1954', cache=tmp_path / 'cache',
        output=tmp_path / output, package_audit_dir=tmp_path / 'out', offline=True)


def test_verified_package_batch_reuse(tmp_path, monkeypatch):
    first = run(tmp_path, monkeypatch)
    result = rerun(tmp_path, 'reuse')
    assert result['status'] == 'PACKAGE_EVIDENCE_COVERED'
    assert len(result['expected_asdm_uids']) == 3
    assert {e['status'] for e in result['executions'].values()} == {'REUSED'}
    for uid, entry in result['executions'].items():
        assert entry['sha256'] == first['executions'][uid]['sha256']
        assert entry['evidence_binding'] == 'MEMBER_PACKAGE_BOUND_NOT_TAP_EXECUTION_BOUND'


def test_missing_execution_only_is_rebuilt(tmp_path, monkeypatch):
    first = run(tmp_path, monkeypatch)
    uid = sorted(first['executions'])[1]
    (tmp_path / 'out' / first['executions'][uid]['execution_file']).unlink()
    result = rerun(tmp_path, 'retry')
    assert result['status'] == 'PACKAGE_EVIDENCE_COVERED'
    assert result['executions'][uid]['status'] == 'RECONSTRUCTED'
    assert sum(e['status'] == 'REUSED' for e in result['executions'].values()) == 2


@pytest.mark.parametrize('kind', ['coordinate', 'listobs', 'path'])
def test_corrupt_evidence_isolated_not_overwritten(tmp_path, monkeypatch, kind):
    first = run(tmp_path, monkeypatch)
    uid = sorted(first['executions'])[1]
    path = tmp_path / 'out' / first['executions'][uid]['execution_file']
    doc = json.loads(path.read_bytes())
    if kind == 'coordinate':
        doc['execution']['evidence']['fields'][0]['ra_deg'] = 0
        path.write_text(json.dumps(doc))
    elif kind == 'listobs':
        (tmp_path / 'out' / doc['provenance']['listobs_file']).write_bytes(b'changed')
    else:
        first['executions'][uid]['execution_file'] = '../outside.json'
        (tmp_path / 'out/package_audit.json').write_text(json.dumps(first))
    result = rerun(tmp_path, 'retry')
    assert result['status'] == 'INCOMPLETE'
    assert result['missing_asdm_uids'] == [uid]
    assert sum(e['status'] == 'REUSED' for e in result['executions'].values()) == 2


def test_wrong_archive_cannot_be_reused(tmp_path, monkeypatch):
    first = run(tmp_path, monkeypatch)
    first['download']['sha256'] = 'wrong'
    (tmp_path / 'out/package_audit.json').write_text(json.dumps(first))
    with pytest.raises(ValueError, match='archive hash'):
        rerun(tmp_path, 'retry')
