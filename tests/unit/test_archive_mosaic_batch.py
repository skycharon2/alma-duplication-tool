"""Batch failure isolation and verified reuse with execution-local field identities."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest

from alma_duplicate import archive_mosaic_batch as batch
from alma_duplicate import archive_mosaic_pipeline as pipeline
from alma_duplicate.archive_auxiliary import select_auxiliary
from alma_duplicate.archive_mosaic_discovery import capture_inventory

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / 'tests/fixtures/archive/mosaic_auxiliary_2026_10_23'
RAW = (ROOT / 'docs/research/mosaic/evidence/case_E_tap.xml').read_bytes()
RESPONSE = ROOT / 'tests/fixtures/archive/mosaic_products_2026_10_23/7m/response.xml'
MEMBER, SOURCE = 'uid://A001/X15aa/Xe5', 'SPT0303-59'
SECOND = 'uid://A002/Xzz/X99'


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = ET.fromstring(RAW)
    table = root.find('.//' + pipeline.NS + 'TABLE')
    rows = table.find('.//' + pipeline.NS + 'TABLEDATA')
    row = deepcopy(rows[0])
    names = [f.get('name') for f in table.findall(pipeline.NS + 'FIELD')]
    row[names.index('asdm_uid')].text = SECOND
    rows.append(row)
    capture_inventory(tmp_path / 'inventory', member=MEMBER, source=SOURCE,
                      fetch=lambda url: (200, ET.tostring(root)))

    def acquire(receipt, row, cache, output, *, asdm_uid, source_name, **kwargs):
        output.mkdir()
        for name in ('discovery.json', 'response.xml'):
            shutil.copyfile(receipt.parent / name, output / name)
        raw = (CAPTURE / 'listobs.txt').read_bytes().replace(b'uid___A002_Xfb8480_X4f37',
            asdm_uid.replace('://', '___').replace('/', '_').encode())
        acquisition = json.loads((CAPTURE / 'acquisition.json').read_text())
        product, digest, _ = select_auxiliary(receipt, row)
        acquisition.update(asdm_uid=asdm_uid, product=asdict(product), discovery_receipt_sha256=digest)
        selected = acquisition['inspection']['selected']
        old = selected['sha256']
        for candidate in acquisition['inspection']['candidates']:
            if candidate.get('sha256') == old:
                candidate.update(sha256=sha256(raw).hexdigest(), bytes=len(raw))
        selected.update(sha256=sha256(raw).hexdigest(), bytes=len(raw))
        (output / 'listobs.txt').write_bytes(raw)
        (output / 'acquisition.json').write_text(json.dumps(acquisition))
        return acquisition
    monkeypatch.setattr(pipeline, 'acquire_listobs', acquire)
    return dict(metadata=tmp_path / 'inventory/metadata.xml',
                capture_receipt=tmp_path / 'inventory/inventory_receipt.json', member=MEMBER,
                source=SOURCE, cache=tmp_path / 'cache', datalink_response=RESPONSE, offline=True)


def test_two_executions_keep_identical_field_ids_separate(inputs, tmp_path):
    report = batch.run_batch(**inputs, output=tmp_path / 'batch')
    assert report['status'] == 'VISIBLE_INVENTORY_COVERED'
    docs = [json.loads((Path(e['directory']) / 'execution.json').read_text())['execution']
            for e in report['executions'].values()]
    assert len(docs) == 2
    assert docs[0]['asdm_uid'] != docs[1]['asdm_uid']
    assert docs[0]['evidence']['fields'] == docs[1]['evidence']['fields']
    assert len(docs[0]['evidence']['fields']) == 19


def test_partial_failure_continues(inputs, tmp_path, monkeypatch):
    original = pipeline.acquire_listobs
    def acquire(*args, **kwargs):
        if kwargs['asdm_uid'] != SECOND:
            raise OSError('unavailable')
        return original(*args, **kwargs)
    monkeypatch.setattr(pipeline, 'acquire_listobs', acquire)
    report = batch.run_batch(**inputs, output=tmp_path / 'batch')
    assert report['status'] == 'INCOMPLETE'
    assert report['executions'][SECOND]['status'] == 'RECONSTRUCTED'
    assert len(report['missing_asdm_uids']) == 1


def test_reuse_revalidates_without_fetch_or_reconstruction(inputs, tmp_path, monkeypatch):
    first = batch.run_batch(**inputs, output=tmp_path / 'batch')
    dirs = [Path(e['directory']) for e in first['executions'].values()]
    def unexpected(*args, **kwargs):
        pytest.fail('Reuse must not acquire products or reconstruct via pipeline')
    monkeypatch.setattr(batch, 'discover_archive_products', unexpected)
    monkeypatch.setattr(batch, 'run_archive_mosaic_pipeline', unexpected)
    inputs['datalink_response'] = None
    result = batch.run_batch(**inputs, output=tmp_path / 'reuse', reuse_dirs=dirs)
    assert {e['status'] for e in result['executions'].values()} == {'REUSED'}
    (dirs[0] / 'listobs.txt').write_bytes(b'changed')
    result = batch.run_batch(**inputs, output=tmp_path / 'tampered', reuse_dirs=dirs)
    assert result['status'] == 'INCOMPLETE'
    assert sum(e['status'] == 'FAILED' for e in result['executions'].values()) == 1


def test_no_overwrite(inputs, tmp_path):
    output = tmp_path / 'existing'
    output.mkdir()
    with pytest.raises(FileExistsError):
        batch.run_batch(**inputs, output=output)


def test_no_auxiliary_is_per_execution_failure(inputs, tmp_path):
    path = tmp_path / 'links.xml'
    path.write_bytes(RESPONSE.read_bytes().replace(b'#auxiliary', b'#documentation'))
    inputs['datalink_response'] = path
    report = batch.run_batch(**inputs, output=tmp_path / 'batch')
    assert report['status'] == 'INCOMPLETE'
    assert len(report['missing_asdm_uids']) == 2


def test_multiple_auxiliary_products_are_not_guessed(inputs, tmp_path):
    root = ET.fromstring(RESPONSE.read_bytes())
    rows = root.find('.//' + pipeline.NS + 'TABLEDATA')
    row = next(r for r in rows if any(c.text == '#auxiliary' for c in r))
    rows.append(deepcopy(row))
    path = tmp_path / 'ambiguous.xml'
    path.write_bytes(ET.tostring(root))
    inputs['datalink_response'] = path
    result = batch.run_batch(**inputs, output=tmp_path / 'batch')
    assert result['status'] == 'INCOMPLETE'
    assert all('found 2' in e['error'] for e in result['executions'].values())


def test_extra_package_asdm_requires_audit(inputs, tmp_path, monkeypatch):
    original = pipeline.acquire_listobs
    def acquire(*args, **kwargs):
        result = original(*args, **kwargs)
        result['inspection']['candidates'].append(dict(status='OTHER_MEASUREMENT_SET',
            reported_asdm_uid='uid://A002/Xextra/X1', measurement_set_variant='ORIGINAL'))
        (args[3] / 'acquisition.json').write_text(json.dumps(result))
        return result
    monkeypatch.setattr(pipeline, 'acquire_listobs', acquire)
    report = batch.run_batch(**inputs, output=tmp_path / 'batch')
    assert report['status'] == 'PACKAGE_AUDIT_REQUIRED'
    assert report['missing_asdm_uids'] == []
    assert report['additional_package_asdm_uids'] == ['uid://A002/Xextra/X1']
