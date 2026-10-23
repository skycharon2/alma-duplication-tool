"""Real captured listobs replay and adversarial execution binding checks."""
import csv
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import pytest
from astropy.io.votable import parse_single_table

from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic
from alma_duplicate.cli.archive_mosaic import main

DATA = Path(__file__).resolve().parents[2] / 'experiments/mosaic_footprint_ab/data'


def sample(kind='12m'):
    tap, raw, expected = (
        ('ngc5248_12m_tap.xml', 'ngc5248_12m_listobs.txt', 'ngc5248_12m_pointings.csv')
        if kind == '12m' else ('case_E_tap.xml', 'source_listobs.md', 'science_pointings.csv')
    )
    table = parse_single_table(DATA / tap).to_table()
    row = table[0]
    kwargs = dict(project_code=str(row['proposal_id']), member_ous_uid=str(row['member_ous_uid']),
                  asdm_uid=str(row['asdm_uid']), source_name=str(row['target_name']),
                  metadata_reference=tap)
    return (DATA / raw).read_bytes(), kwargs, DATA / expected


@pytest.mark.parametrize('kind,count', [('7m', 19), ('12m', 11)])
def test_captured_fields_match_preserved_reference(kind, count):
    raw, kwargs, reference = sample(kind)
    result = reconstruct_archive_mosaic(raw, **kwargs)
    with reference.open(newline='') as stream:
        expected = list(csv.DictReader(stream))
    assert len(result.evidence.fields) == len(expected) == count
    assert result.evidence.source_sha256 == sha256(raw).hexdigest()
    for actual, row in zip(result.evidence.fields, expected):
        assert actual.field_id == int(row['field_id'])
        assert actual.source_id == int(row['source_id'])
        assert actual.ra_deg == pytest.approx(float(row['ra_deg']), abs=1e-12, rel=0)
        assert actual.dec_deg == pytest.approx(float(row['dec_deg']), abs=1e-12, rel=0)
        assert actual.ra_original == row['ra_hms']
        assert actual.dec_original == row['dec_dms']
        assert [s.scan_id for s in actual.scans] == list(map(int, row['science_scan_ids'].split(';')))
    assert result.array_label is None
    assert result.completeness == 'MEMBER_COMPLETENESS_NOT_ESTABLISHED'
    assert result.execution_inventory_status == 'UNKNOWN'
    assert result.policy_status == 'NOT_EVALUATED'
    assert asdict(reconstruct_archive_mosaic(raw, **kwargs)) == asdict(result)


@pytest.mark.parametrize('mutation', ['missing_header', 'wrong_ms', 'duplicate', 'frame', 'truncated', 'target'])
def test_rejects_unsupported_or_mismatched_evidence(mutation):
    raw, kwargs, _ = sample()
    text = raw.decode()
    if mutation == 'missing_header':
        text = text.replace('MeasurementSet Name:', 'Missing header:')
    elif mutation == 'wrong_ms':
        text = text.replace('uid___A002_Xeaae1d_X1a2.ms', 'uid___A002_Xeaae1d_X1a2.ms.backup')
    elif mutation == 'duplicate':
        text += text
    elif mutation == 'frame':
        text = text.replace('ICRS', 'J2000')
    elif mutation == 'truncated':
        text = text.split('Spectral Windows:')[0]
    else:
        kwargs['source_name'] = 'another_source'
    with pytest.raises(ValueError):
        reconstruct_archive_mosaic(text.encode(), **kwargs)


def test_retains_scan_to_spw_pairs_and_coordinate_duplicates():
    raw = b'''MeasurementSet Name: uid___A002_Xabc_X1.ms MS Version 2
 1 0 target 10 [1,2] OBSERVE_TARGET#ON_SOURCE
 2 0 target 10 [3,4] OBSERVE_TARGET#ON_SOURCE
 3 1 target 10 [1,2] OBSERVE_TARGET#ON_SOURCE
Fields: 2
 0 none target 12:00:00.000 -00.30.00.00 ICRS 0 10
 1 none target 12:00:00.000 -00.30.00.00 ICRS 0 10
Spectral Windows:
'''
    kwargs = dict(project_code='test', member_ous_uid='uid://A001/Xabc/X2',
                  asdm_uid='uid://A002/Xabc/X1', source_name='target', metadata_reference='test')
    result = reconstruct_archive_mosaic(raw, **kwargs)
    assert len(result.evidence.fields) == 2
    field = result.evidence.fields[0]
    assert field.dec_deg == -0.5
    assert [(s.scan_id, s.spw_ids) for s in field.scans] == [(1, (1, 2)), (2, (3, 4))]
    with pytest.raises(ValueError, match='Conflicting science scan'):
        reconstruct_archive_mosaic(raw.replace(b' 2 0 target', b' 1 0 target'), **kwargs)
    with pytest.raises(ValueError, match='missing FIELD_ID'):
        reconstruct_archive_mosaic(raw.replace(b' 3 1 target', b' 3 2 target'), **kwargs)
    with pytest.raises(ValueError, match='FIELD table incomplete'):
        reconstruct_archive_mosaic(raw.replace(b'Fields: 2', b'Fields: 3'), **kwargs)


def test_array_label_requires_explicit_evidence():
    raw, kwargs, _ = sample()
    with pytest.raises(ValueError, match='supplied together'):
        reconstruct_archive_mosaic(raw, **kwargs, array_label='12m')
    result = reconstruct_archive_mosaic(raw, **kwargs, array_label='12m',
                                       array_evidence_reference='caller-supplied-catalog-entry')
    assert result.array_evidence_reference == 'caller-supplied-catalog-entry'


def test_cli_exports_and_refuses_overwrite(tmp_path):
    _, kwargs, _ = sample()
    output = tmp_path / 'result.json'
    args = ['--listobs', str(DATA / 'ngc5248_12m_listobs.txt'),
            '--project', kwargs['project_code'], '--member', kwargs['member_ous_uid'],
            '--asdm', kwargs['asdm_uid'], '--source', kwargs['source_name'],
            '--metadata-reference', kwargs['metadata_reference'], '--output', str(output)]
    assert main(args) == 0
    saved = output.read_bytes()
    assert len(json.loads(saved)['execution']['evidence']['fields']) == 11
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert output.read_bytes() == saved
