"""Pipeline provenance and failure isolation without remote acquisition."""
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest

import alma_duplicate.archive_mosaic_pipeline as module
from alma_duplicate.cli.archive_mosaic_pipeline import main
from alma_duplicate.parsers.archive_listobs import parse_science_fields

ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / 'docs/research/mosaic/evidence/case_E_tap.xml'
RECEIPT = ROOT / 'tests/fixtures/archive/mosaic_products_2026_10_23/7m/discovery.json'
CAPTURE = ROOT / 'tests/fixtures/archive/mosaic_auxiliary_2026_10_23'
NS = module.NS


def fake_acquisition(receipt, row, cache, output, **kwargs):
    output.mkdir()
    for name in ('discovery.json', 'response.xml'):
        shutil.copyfile(receipt.parent / name, output / name)
    shutil.copyfile(CAPTURE / 'listobs.txt', output / 'listobs.txt')
    shutil.copyfile(CAPTURE / 'acquisition.json', output / 'acquisition.json')
    return json.loads((output / 'acquisition.json').read_text())


def run(tmp_path, monkeypatch, acquire=fake_acquisition):
    monkeypatch.setattr(module, 'acquire_listobs', acquire)
    return module.run_archive_mosaic_pipeline(metadata=METADATA, receipt=RECEIPT,
               row_index=3, cache=tmp_path / 'cache', output=tmp_path / 'out', offline=True)


def test_complete_pipeline_and_preserved_values(tmp_path, monkeypatch):
    result = run(tmp_path, monkeypatch)
    assert result['status'] == 'RECONSTRUCTED'
    output = tmp_path / 'out'
    document = json.loads((output / 'execution.json').read_text())
    execution = document['execution']
    assert execution['project_code'] == '2021.2.00176.S'
    assert execution['member_ous_uid'] == 'uid://A001/X15aa/Xe5'
    assert execution['metadata_status'] == 'SAVED_TAP_ROW_MEMBER_BOUND'
    assert execution['acquisition_status'] == 'VERIFIED_ACQUISITION_RECEIPT'
    assert execution['array_label'] is None
    assert execution['policy_status'] == 'NOT_EVALUATED'
    raw = (CAPTURE / 'listobs.txt').read_bytes()
    expected = parse_science_fields(raw, asdm_uid='uid://A002/Xfb8480/X4f37', target_name='SPT0303-59')
    assert execution['evidence'] == json.loads(json.dumps(asdict(expected)))
    assert (output / 'metadata.xml').read_bytes() == METADATA.read_bytes()
    from hashlib import sha256
    assert document['provenance']['acquisition_sha256'] == sha256((output / 'acquisition.json').read_bytes()).hexdigest()


@pytest.mark.parametrize('change', ['bytes', 'member', 'asdm', 'target', 'hash', 'count', 'ambiguous'])
def test_tampered_acquisition_cannot_produce_execution(tmp_path, monkeypatch, change):
    def acquire(*args, **kwargs):
        result = fake_acquisition(*args, **kwargs)
        output = args[3]
        if change == 'bytes':
            (output / 'listobs.txt').write_bytes(b'changed')
        elif change == 'member':
            result['product']['member_ous_uid'] = 'uid://A001/X1/X2'
        elif change == 'asdm':
            result['asdm_uid'] = 'uid://A002/X1/X2'
        elif change == 'target':
            result['source_name'] = 'wrong'
        elif change == 'hash':
            result['discovery_receipt_sha256'] = 'wrong'
        elif change == 'count':
            result['inspection']['selected']['science_field_count'] = 99
            result['inspection']['candidates'][0]['science_field_count'] = 99
        else:
            result['inspection']['candidates'].append(result['inspection']['selected'])
        (output / 'acquisition.json').write_text(json.dumps(result))
        return result
    assert run(tmp_path, monkeypatch, acquire)['status'] == 'RECONSTRUCTION_FAILED'
    assert not (tmp_path / 'out/execution.json').exists()


@pytest.mark.parametrize('status', ['NOT_FOUND', 'AMBIGUOUS', 'UNRESOLVED_CANDIDATES', 'FAILED'])
def test_acquisition_states_preserved(tmp_path, monkeypatch, status):
    def acquire(*args, **kwargs):
        result = fake_acquisition(*args, **kwargs)
        result['status'] = status
        (args[3] / 'acquisition.json').write_text(json.dumps(result))
        return result
    result = run(tmp_path, monkeypatch, acquire)
    assert result['status'] == status and result['execution_file'] is None
    assert not (tmp_path / 'out/execution.json').exists()


@pytest.mark.parametrize('change', ['rows', 'status', 'mosaic', 'empty', 'member'])
def test_metadata_preflight_before_acquisition(tmp_path, monkeypatch, change):
    root = ET.fromstring(METADATA.read_bytes())
    rows = root.find('.//' + NS + 'TABLEDATA')
    if change == 'rows':
        rows.append(ET.fromstring(ET.tostring(rows[0])))
    elif change == 'status':
        root.find(NS + 'RESOURCE').append(ET.Element(NS + 'INFO', name='QUERY_STATUS', value='OVERFLOW'))
    else:
        table = root.find('.//' + NS + 'TABLE')
        names = [f.get('name') for f in table.findall(NS + 'FIELD')]
        key = {'mosaic': 'is_mosaic', 'empty': 'proposal_id', 'member': 'member_ous_uid'}[change]
        rows[0][names.index(key)].text = {'mosaic': 'F', 'empty': '', 'member': 'uid://A001/X1/X2'}[change]
    metadata = tmp_path / 'tap.xml'
    metadata.write_bytes(ET.tostring(root))
    monkeypatch.setattr(module, 'acquire_listobs', lambda *a, **kw: pytest.fail('Unexpected acquisition'))
    with pytest.raises(ValueError):
        module.run_archive_mosaic_pipeline(metadata=metadata, receipt=RECEIPT, row_index=3,
                                           cache=tmp_path / 'cache', output=tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'acquire_listobs', fake_acquisition)
    args = ['--metadata', str(METADATA), '--receipt', str(RECEIPT), '--product-row', '3',
            '--cache', str(tmp_path / 'cache'), '--output-dir', str(tmp_path / 'out'), '--offline']
    assert main(args) == 0
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


def test_reserialized_historical_metadata_is_not_a_successful_tap_receipt():
    historical = ROOT / 'experiments/mosaic_footprint_ab/data/ngc5248_12m_tap.xml'
    with pytest.raises(ValueError, match='QUERY_STATUS'):
        module.read_mosaic_identity(historical.read_bytes())


def test_independent_12m_pipeline_replay(tmp_path, monkeypatch):
    from hashlib import sha256
    capture = ROOT / 'tests/fixtures/archive/mosaic_pipeline_12m_2026_10_23'
    discovery = ROOT / 'tests/fixtures/archive/mosaic_products_2026_10_23/12m/discovery.json'
    metadata = capture / 'metadata.xml'
    saved = json.loads((capture / 'metadata_receipt.json').read_text())
    assert sha256(metadata.read_bytes()).hexdigest() == saved['sha256']
    def acquire(receipt, row, cache, output, **kwargs):
        output.mkdir()
        for name in ('discovery.json', 'response.xml'):
            shutil.copyfile(receipt.parent / name, output / name)
        for name in ('listobs.txt', 'acquisition.json'):
            shutil.copyfile(capture / name, output / name)
        return json.loads((output / 'acquisition.json').read_text())
    monkeypatch.setattr(module, 'acquire_listobs', acquire)
    summary = module.run_archive_mosaic_pipeline(metadata=metadata, receipt=discovery,
                row_index=3, cache=tmp_path / 'cache', output=tmp_path / 'out', offline=True)
    assert summary['status'] == 'RECONSTRUCTED'
    result = json.loads((tmp_path / 'out/execution.json').read_text())['execution']
    expected = parse_science_fields(
        (ROOT / 'experiments/mosaic_footprint_ab/data/ngc5248_12m_listobs.txt').read_bytes(),
        asdm_uid='uid://A002/Xeaae1d/X1a2', target_name='NGC5248')
    assert result['evidence']['fields'] == json.loads(json.dumps([asdict(f) for f in expected.fields]))
    assert len(result['evidence']['fields']) == 11
    assert result['completeness'] == 'MEMBER_COMPLETENESS_NOT_ESTABLISHED'
