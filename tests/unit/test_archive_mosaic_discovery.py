"""Inventory capture limits, query binding, and offline reconciliation."""
import json
from pathlib import Path
from urllib.error import URLError
import xml.etree.ElementTree as ET

import pytest

from alma_duplicate import archive_mosaic_discovery as module
from alma_duplicate.archive_mosaic_inventory import reconcile_inventory
from alma_duplicate.archive_mosaic_pipeline import NS

ROOT = Path(__file__).resolve().parents[2]
RAW = (ROOT / 'docs/research/mosaic/evidence/case_E_tap.xml').read_bytes()
MEMBER = 'uid://A001/X15aa/Xe5'
SOURCE = 'SPT0303-59'


def capture(tmp_path, raw=RAW, code=200):
    output = tmp_path / 'capture'
    result = module.capture_inventory(output, member=MEMBER, source=SOURCE,
                                      fetch=lambda url: (code, raw))
    return output, result


def test_query_has_no_execution_or_top_restriction():
    query = module.inventory_request(MEMBER, "O'Brien")['query']
    assert "target_name='O''Brien'" in query
    assert 'TOP ' not in query
    assert 'asdm_uid=' not in query
    assert 'SELECT DISTINCT' in query


def test_capture_and_reconcile_missing(tmp_path):
    output, result = capture(tmp_path)
    assert result['status'] == 'CAPTURED'
    assert (output / 'metadata.xml').read_bytes() == RAW
    report = reconcile_inventory(output / 'metadata.xml', [], member=MEMBER, source=SOURCE,
                                 capture_receipt=output / 'inventory_receipt.json')
    assert report['inventory_scope'] == 'CAPTURED_VISIBLE_SCIENCE_MOSAIC_MEMBER_TARGET'
    assert report['coverage_status'] == 'MISSING_EXECUTIONS'
    assert report['completeness'] == 'MEMBER_COMPLETENESS_NOT_ESTABLISHED'
    assert report['capture_receipt_sha256']


@pytest.mark.parametrize('kind', ['overflow', 'empty', 'identity', 'malformed', 'oversize'])
def test_invalid_and_empty_responses(tmp_path, kind):
    root = ET.fromstring(RAW)
    if kind == 'overflow':
        ET.SubElement(root.find(NS + 'RESOURCE'), NS + 'INFO', name='QUERY_STATUS', value='OVERFLOW')
    if kind == 'empty':
        root.find('.//' + NS + 'TABLEDATA').clear()
    raw = ET.tostring(root)
    if kind == 'identity':
        raw = raw.replace(SOURCE.encode(), b'OTHER')
    if kind == 'malformed':
        raw = b'<invalid'
    if kind == 'oversize':
        raw = b' ' * (module.MAX_METADATA_BYTES + 1)
    output, result = capture(tmp_path, raw)
    assert result['status'] == ('EMPTY' if kind == 'empty' else 'INVALID_RESPONSE')
    with pytest.raises(ValueError):
        module.verify_inventory_capture(raw, output / 'inventory_receipt.json', member=MEMBER, source=SOURCE)


def test_at_row_limit_is_not_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'MAX_ROWS', 1)
    _, result = capture(tmp_path)
    assert result['status'] == 'INVALID_RESPONSE'


@pytest.mark.parametrize('code', [302, 403, 500])
def test_http_failure_not_inventory(tmp_path, code):
    _, result = capture(tmp_path, code=code)
    assert result['status'] == ('ACCESS_DENIED' if code == 403 else 'REQUEST_FAILED')


def test_network_failure_saved(tmp_path):
    def fail(url):
        raise URLError('offline')
    result = module.capture_inventory(tmp_path / 'run', member=MEMBER, source=SOURCE, fetch=fail)
    assert result['status'] == 'REQUEST_FAILED'
    assert not (tmp_path / 'run/metadata.xml').exists()


@pytest.mark.parametrize('change', ['query', 'maxrec', 'hash', 'count', 'asdm'])
def test_modified_capture_rejected(tmp_path, change):
    output, receipt = capture(tmp_path)
    if change == 'query':
        receipt['request']['query'] = receipt['request']['query'].replace('SELECT DISTINCT', 'SELECT TOP 1')
    elif change == 'maxrec':
        receipt['request']['maxrec'] = 1
    elif change == 'hash':
        receipt['response_sha256'] = 'wrong'
    elif change == 'count':
        receipt['row_count'] += 1
    else:
        receipt['asdm_uids'] = []
    path = output / 'inventory_receipt.json'
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        module.verify_inventory_capture(RAW, path, member=MEMBER, source=SOURCE)


def test_no_overwrite_or_fetch_on_existing_directory(tmp_path):
    output, _ = capture(tmp_path)
    with pytest.raises(FileExistsError):
        module.capture_inventory(output, member=MEMBER, source=SOURCE,
                                 fetch=lambda url: pytest.fail('Unexpected network call'))
