"""Saved inventory coverage, identity boundaries, and execution integrity."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest

from alma_duplicate.archive_mosaic_inventory import reconcile_inventory
from alma_duplicate import archive_mosaic_pipeline as pipeline
from alma_duplicate.cli.archive_mosaic_inventory import main

ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / 'docs/research/mosaic/evidence/case_E_tap.xml'
PRODUCTS = ROOT / 'tests/fixtures/archive/mosaic_products_2026_10_23/7m'
CAPTURE = ROOT / 'tests/fixtures/archive/mosaic_auxiliary_2026_10_23'
MEMBER = 'uid://A001/X15aa/Xe5'
SOURCE = 'SPT0303-59'
NS = pipeline.NS


@pytest.fixture
def execution(tmp_path, monkeypatch):
    def acquire(receipt, row, cache, output, **kwargs):
        output.mkdir()
        for name in ('discovery.json', 'response.xml'):
            shutil.copyfile(PRODUCTS / name, output / name)
        for name in ('listobs.txt', 'acquisition.json'):
            shutil.copyfile(CAPTURE / name, output / name)
        return json.loads((output / 'acquisition.json').read_text())
    monkeypatch.setattr(pipeline, 'acquire_listobs', acquire)
    output = tmp_path / 'execution'
    assert pipeline.run_archive_mosaic_pipeline(metadata=METADATA,
        receipt=PRODUCTS / 'discovery.json', row_index=3, cache=tmp_path / 'cache',
        output=output, offline=True)['status'] == 'RECONSTRUCTED'
    return output


def inventory(tmp_path, *, extra=None, empty=False, overflow=False):
    root = ET.fromstring(METADATA.read_bytes())
    table = root.find('.//' + NS + 'TABLE')
    data = table.find(NS + 'DATA/' + NS + 'TABLEDATA')
    if extra is not None:
        row = deepcopy(data[0])
        names = [f.get('name') for f in table.findall(NS + 'FIELD')]
        for key, value in extra.items():
            row[names.index(key)].text = value
        data.append(row)
    if empty:
        data.clear()
    if overflow:
        resource = root.find(NS + 'RESOURCE')
        ET.SubElement(resource, NS + 'INFO', name='QUERY_STATUS', value='OVERFLOW')
    path = tmp_path / 'inventory.xml'
    path.write_bytes(ET.tostring(root))
    return path


def check(metadata, dirs):
    return reconcile_inventory(metadata, dirs, member=MEMBER, source=SOURCE)


def test_covered_is_not_member_complete(execution):
    report = check(METADATA, [execution])
    assert report['coverage_status'] == 'SUPPLIED_INVENTORY_COVERED'
    assert report['completeness'] == 'MEMBER_COMPLETENESS_NOT_ESTABLISHED'
    assert report['missing_asdm_uids'] == []
    assert next(iter(report['acquired'].values()))['science_field_count'] == 19


def test_missing_execution_is_explicit(tmp_path, execution):
    report = check(inventory(tmp_path, extra={'asdm_uid': 'uid://A002/X1/X2'}), [execution])
    assert report['missing_asdm_uids'] == ['uid://A002/X1/X2']
    assert report['coverage_status'] == 'MISSING_EXECUTIONS'


def test_repeated_spectral_rows_do_not_duplicate_execution(tmp_path, execution):
    report = check(inventory(tmp_path, extra={}), [execution])
    assert report['input_row_count'] == 2
    assert len(report['expected_asdm_uids']) == 1


@pytest.mark.parametrize('options', [dict(empty=True), dict(overflow=True),
    dict(extra={'member_ous_uid': 'uid://A001/X1/X2'}),
    dict(extra={'target_name': 'OTHER'}), dict(extra={'proposal_id': 'OTHER'})])
def test_invalid_inventory_rejected(tmp_path, options):
    with pytest.raises(ValueError):
        check(inventory(tmp_path, **options), [])


def test_duplicate_input_rejected(execution):
    with pytest.raises(ValueError, match='Duplicate execution'):
        check(METADATA, [execution, execution])


@pytest.mark.parametrize('filename', ['execution.json', 'listobs.txt', 'acquisition.json'])
def test_modified_evidence_rejected(execution, filename):
    path = execution / filename
    if filename == 'listobs.txt':
        path.write_bytes(path.read_bytes() + b'changed')
    else:
        doc = json.loads(path.read_text())
        if filename == 'execution.json':
            doc['execution']['evidence']['fields'][0]['ra_deg'] = 0
        else:
            doc['source_name'] = 'OTHER'
        path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        check(METADATA, [execution])


def test_unexpected_execution_rejected(tmp_path, execution):
    root = METADATA.read_bytes().replace(b'uid://A002/Xfb8480/X4f37', b'uid://A002/X1/X2')
    path = tmp_path / 'other.xml'
    path.write_bytes(root)
    with pytest.raises(ValueError, match='outside'):
        check(path, [execution])


def test_cli_missing_and_no_overwrite(tmp_path):
    output = tmp_path / 'report.json'
    args = ['--metadata', str(METADATA), '--member', MEMBER, '--source', SOURCE,
            '--output', str(output)]
    assert main(args) == 3
    original = output.read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert output.read_bytes() == original
