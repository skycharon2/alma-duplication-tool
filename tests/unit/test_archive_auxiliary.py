"""Bounded acquisition, cache integrity, and archive candidate selection."""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

from alma_duplicate.archive_auxiliary import (
    acquire_auxiliary, acquire_listobs, inspect_auxiliary, select_auxiliary,
)

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / 'tests/fixtures/archive/mosaic_products_2026_10_23/7m/discovery.json'
ASDM = 'uid://A002/Xfb8480/X4f37'
SOURCE = 'SPT0303-59'
RAW = (ROOT / 'experiments/mosaic_footprint_ab/data/source_listobs.md').read_bytes()


def archive_bytes(entries):
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        for name, content in entries:
            entry = tarfile.TarInfo(name)
            if content is None:
                entry.type = tarfile.SYMTYPE
                entry.linkname = '/tmp/outside'
                tar.addfile(entry)
            else:
                entry.size = len(content)
                tar.addfile(entry, BytesIO(content))
    return buffer.getvalue()


def inspect(tmp_path, entries):
    path = tmp_path / 'input.tar'
    path.write_bytes(archive_bytes(entries))
    return inspect_auxiliary(path, asdm_uid=ASDM, source_name=SOURCE)


class Response(BytesIO):
    status = 200
    def __init__(self, raw):
        super().__init__(raw)
        self.headers = {'Content-Length': str(len(raw))}


def test_receipt_binding():
    product, digest, scope = select_auxiliary(RECEIPT, 3)
    assert product.content_length == 56154112
    assert scope == ASDM and len(digest) == 64
    for row in (-1, 0, 4, 100):
        with pytest.raises(ValueError):
            select_auxiliary(RECEIPT, row)


def test_tampered_receipt_response(tmp_path):
    saved = json.loads(RECEIPT.read_text())
    (tmp_path / 'discovery.json').write_text(json.dumps(saved))
    (tmp_path / 'response.xml').write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        select_auxiliary(tmp_path / 'discovery.json', 3)


def test_nested_weblog_and_other_ms(tmp_path):
    other = RAW.replace(b'uid___A002_Xfb8480_X4f37.ms', b'uid___A002_Xfb8480_X4f37_target.ms')
    nested = archive_bytes([('raw/listobs.txt', RAW), ('target/listobs.txt', other), ('index.html', None)])
    result, raw = inspect(tmp_path, [('qa/example.weblog.tgz', nested)])
    assert result['status'] == 'FOUND' and raw == RAW
    assert result['selected']['science_field_count'] == 19
    assert result['selected']['path_chain'] == ['qa/example.weblog.tgz', 'raw/listobs.txt']
    assert result['candidates'][1]['status'] == 'OTHER_MEASUREMENT_SET'
    assert result['skipped'][0]['reason'] == 'NON_REGULAR_MEMBER'


def test_ambiguity_and_unparsed_candidate_are_not_hidden(tmp_path):
    result, raw = inspect(tmp_path, [('a/listobs.txt', RAW), ('b/listobs.txt', RAW)])
    assert result['status'] == 'AMBIGUOUS' and raw is None
    result, raw = inspect(tmp_path, [('a/listobs.txt', RAW), ('b/listobs.txt', b'bad')])
    assert result['status'] == 'UNRESOLVED_CANDIDATES' and raw is None


def test_empty_and_non_weblog_scope(tmp_path):
    result, raw = inspect(tmp_path, [('calibration.tgz', archive_bytes([('listobs.txt', RAW)]))])
    assert result['status'] == 'NOT_FOUND' and raw is None
    assert result['skipped'][0]['reason'] == 'OUTSIDE_WEBLOG_SCOPE'


@pytest.mark.parametrize('entries', [
    [('../listobs.txt', RAW)], [('/listobs.txt', RAW)], [('listobs.txt', None)],
    [('listobs.txt', RAW), ('listobs.txt', RAW)],
])
def test_unsafe_layout_rejected(tmp_path, entries):
    with pytest.raises(ValueError):
        inspect(tmp_path, entries)


def test_budget_and_nesting(tmp_path, monkeypatch):
    import alma_duplicate.archive_auxiliary as module
    monkeypatch.setattr(module, 'MAX_TEXT', 10)
    with pytest.raises(ValueError, match='size limit'):
        inspect(tmp_path, [('listobs.txt', RAW)])
    monkeypatch.setattr(module, 'MAX_TEXT', 5_000_000)
    monkeypatch.setattr(module, 'MAX_DEPTH', 0)
    with pytest.raises(ValueError, match='nesting'):
        inspect(tmp_path, [('weblog.tgz', archive_bytes([('listobs.txt', RAW)]))])
    monkeypatch.setattr(module, 'MAX_ENTRIES', 0)
    with pytest.raises(ValueError, match='budget'):
        inspect(tmp_path, [('listobs.txt', RAW)])


def test_download_and_verified_offline_cache(tmp_path):
    product, _, _ = select_auxiliary(RECEIPT, 3)
    payload = archive_bytes([('listobs.txt', RAW)])
    product = replace(product, content_length=len(payload))
    path, record, hit = acquire_auxiliary(product, tmp_path, open_url=lambda request: Response(payload))
    assert not hit and path.read_bytes() == payload
    second, saved, hit = acquire_auxiliary(product, tmp_path, offline=True)
    assert hit and second == path and saved == record
    path.write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='integrity'):
        acquire_auxiliary(product, tmp_path, offline=True)


def test_download_failures_leave_no_usable_cache(tmp_path):
    product, _, _ = select_auxiliary(RECEIPT, 3)
    with pytest.raises(ValueError, match='size'):
        acquire_auxiliary(product, tmp_path, open_url=lambda request: Response(b'partial'))
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError, match='No verified'):
        acquire_auxiliary(product, tmp_path, offline=True)
    class Broken(Response):
        def read(self, size=-1):
            raise OSError('connection lost')
    with pytest.raises(OSError):
        acquire_auxiliary(product, tmp_path, open_url=lambda request: Broken(b'x'))
    assert list(tmp_path.iterdir()) == []


def test_scope_mismatch_before_output(tmp_path):
    with pytest.raises(ValueError, match='scope'):
        acquire_listobs(RECEIPT, 3, tmp_path / 'cache', tmp_path / 'out',
                        asdm_uid='uid://A002/X1/X2', source_name=SOURCE)
    assert not (tmp_path / 'out').exists()


def test_missing_cache_saves_failure(tmp_path):
    result = acquire_listobs(RECEIPT, 3, tmp_path / 'cache', tmp_path / 'out',
                             asdm_uid=ASDM, source_name=SOURCE, offline=True)
    assert result['status'] == 'FAILED'
    assert not (tmp_path / 'out/listobs.txt').exists()
    assert json.loads((tmp_path / 'out/acquisition.json').read_text())['status'] == 'FAILED'
    with pytest.raises(FileExistsError):
        acquire_listobs(RECEIPT, 3, tmp_path / 'cache', tmp_path / 'out',
                        asdm_uid=ASDM, source_name=SOURCE, offline=True)


def test_captured_listobs_matches_original_scientific_records():
    from hashlib import sha256
    from alma_duplicate.parsers.archive_listobs import parse_science_fields
    directory = ROOT / 'tests/fixtures/archive/mosaic_auxiliary_2026_10_23'
    raw = (directory / 'listobs.txt').read_bytes()
    record = json.loads((directory / 'acquisition.json').read_text())
    assert sha256(raw).hexdigest() == record['inspection']['selected']['sha256']
    kwargs = dict(asdm_uid=ASDM, target_name=SOURCE)
    assert parse_science_fields(raw, **kwargs).fields == parse_science_fields(RAW, **kwargs).fields
    assert len(parse_science_fields(raw, **kwargs).fields) == 19
    assert record['acquisition']['bytes'] == 56154112


def test_cli_offline_success(tmp_path, monkeypatch):
    from alma_duplicate.cli.archive_auxiliary import main
    import alma_duplicate.archive_auxiliary as module
    payload = archive_bytes([('listobs.txt', RAW)])
    archive = tmp_path / 'cached.tar'
    archive.write_bytes(payload)
    monkeypatch.setattr(module, 'acquire_auxiliary', lambda *args, **kwargs: (
        archive, {'url': 'recorded', 'bytes': len(payload)}, True))
    output = tmp_path / 'output'
    code = main(['--receipt', str(RECEIPT), '--product-row', '3', '--asdm', ASDM,
                 '--source', SOURCE, '--cache', str(tmp_path / 'cache'),
                 '--output-dir', str(output), '--offline'])
    assert code == 0
    assert (output / 'listobs.txt').read_bytes() == RAW
    assert (output / 'discovery.json').read_bytes() == RECEIPT.read_bytes()
    assert (output / 'response.xml').read_bytes() == (RECEIPT.parent / 'response.xml').read_bytes()
