"""SPW links, signed frequency grids and conservative array binding."""
from dataclasses import asdict
from pathlib import Path
import json

import pytest

from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic
from alma_duplicate.archive_mosaic_readiness import execution_readiness, bind_array
from alma_duplicate.archive_array_evidence import ArchiveArrayCatalog, ArchiveArrayCatalogMode, ArchiveArrayCatalogProvenance, ArrayRecord
from alma_duplicate.parsers.archive_listobs_setup import parse_spectral_windows, parse_antennas

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/archive/mosaic_multi_execution_2026_10_23'
AUDIT = json.loads((FIXTURE / 'package_audit.json').read_text())
CANDIDATE = next(c for c in AUDIT['inspection']['candidates'] if c.get('measurement_set_variant') == 'ORIGINAL')
RAW = (FIXTURE / 'listobs' / (CANDIDATE['sha256'] + '.txt')).read_bytes()
MEMBER = AUDIT['member_ous_uid']


def execution(raw=RAW):
    return asdict(reconstruct_archive_mosaic(raw, project_code='2017.1.00886.L', member_ous_uid=MEMBER,
        asdm_uid=CANDIDATE['reported_asdm_uid'], source_name='IC1954', metadata_reference='discovery.json'))


def catalog(label='7m', source='IC1954', duplicates=False):
    record = ArrayRecord(f'{MEMBER}.source.{source}', MEMBER, source, label, 'sha',
                         '2026-10-23T00:00:00+00:00', 'https://almascience.eso.org/aq/service/api/search/observations/_search')
    return ArchiveArrayCatalog((record, record) if duplicates else (record,),
        ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.CAPTURED, 'manifest'))


def test_real_spw_binding_and_array_evidence():
    e = execution()
    result = execution_readiness(e, RAW, catalog())
    assert result['spectral_window_count'] == 24
    assert result['antenna_evidence']['diameters_m'] == [7.0]
    assert result['array_evidence']['status'] == 'BOUND'
    assert len(result['fields']) == 22
    for field in result['fields']:
        assert field['explicit_full_res_spw_ids'] == [16, 18, 20, 22]
        assert {w['spw_id'] for w in field['spectral_windows']} == {s for scan in field['scans'] for s in scan['spw_ids']}
        assert field['input_status'] == 'EVIDENCE_BOUND'
        assert field['footprint_status'] == 'NOT_EVALUATED'


def test_signed_width_units_and_original_preservation():
    windows = parse_spectral_windows(RAW)
    negative = windows[20]
    assert negative['signed_channel_width_hz'] < 0
    assert negative['approximate_frequency_range_hz'][0] < negative['first_channel_hz'] < negative['approximate_frequency_range_hz'][1]
    assert negative['raw_row']
    assert negative['exact_channel_edges_status'] == 'NOT_AVAILABLE'


@pytest.mark.parametrize('change', ['unit', 'count', 'duplicate', 'nan'])
def test_spw_bad_layout_rejected(change):
    raw = RAW
    if change == 'unit': raw = raw.replace(b'Ch0(MHz)', b'Ch0(GHz)')
    if change == 'count': raw = raw.replace(b'24 unique spectral windows', b'25 unique spectral windows')
    if change == 'duplicate':
        text = raw.decode(); row = next(l for l in text.splitlines() if l.strip().startswith('16 ') and '#FULL_RES' in l)
        raw = text.replace(row, row + '\n' + row).encode()
    if change == 'nan':
        text = raw.decode(); row = next(l for l in text.splitlines() if l.strip().startswith('16 ') and '#FULL_RES' in l)
        cells = row.split(); cells[4] = 'nan'; raw = text.replace(row, ' '.join(cells)).encode()
    with pytest.raises(ValueError): parse_spectral_windows(raw)


@pytest.mark.parametrize('label,status', [('12m','CONFLICT'), ('7m 12m','MIXED'), ('tp','UNSUPPORTED'), ('unknown','UNKNOWN')])
def test_array_labels_do_not_override_execution_dishes(label, status):
    result = bind_array(catalog(label), member=MEMBER, source='IC1954', antennas=parse_antennas(RAW))
    assert result['status'] == status
    assert result['reasons']


def test_missing_and_ambiguous_aq_not_inferred_from_dishes():
    for c in (None, catalog(source='OTHER'), catalog(duplicates=True)):
        result = execution_readiness(execution(), RAW, c)
        assert result['array_evidence']['status'] == 'UNKNOWN'
        assert all(f['input_status'] == 'NOT_READY' for f in result['fields'])


def test_missing_spw_reference_keeps_field_not_ready():
    e = execution()
    e['evidence']['fields'][0]['scans'][0]['spw_ids'] = (999,)
    result = execution_readiness(e, RAW, catalog())
    assert result['fields'][0]['missing_spw_ids'] == [999]
    assert result['fields'][0]['input_status'] == 'NOT_READY'


def test_mixed_dish_table_and_bad_unit():
    text = RAW.decode()
    line = next(l for l in text.splitlines() if 'CM01' in l and '7.0  m' in l)
    raw = text.replace(line, line.replace('7.0  m', '12.0  m')).encode()
    assert parse_antennas(raw)['dish_class'] == 'MIXED'
    with pytest.raises(ValueError): parse_antennas(RAW.replace(b'7.0  m', b'7.0  ft'))


def test_setup_read_rechecks_hash():
    with pytest.raises(ValueError): execution_readiness(execution(), RAW + b'changed', catalog())


def test_spw_ids_remain_local_and_different_frequency_preserved():
    first = parse_spectral_windows(RAW)
    text = RAW.decode(); row = next(l for l in text.splitlines() if l.strip().startswith('16 ') and '#FULL_RES' in l)
    cells = row.split(); cells[4] = str(float(cells[4]) + 10); cells[7] = str(float(cells[7]) + 10)
    second = parse_spectral_windows(text.replace(row, ' '.join(cells)).encode())
    assert first[16]['spw_id'] == second[16]['spw_id']
    assert first[16]['first_channel_hz'] != second[16]['first_channel_hz']
