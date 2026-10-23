"""Spherical diagnostics and saved-evidence verification boundaries."""
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from alma_duplicate.archive_mosaic import reconstruct_archive_mosaic
from alma_duplicate.archive_mosaic_pointings import compare_pointings, separation_arcsec, load_package_executions
from alma_duplicate.cli.archive_mosaic_pointings import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/archive/mosaic_multi_execution_2026_10_23'


def execution(uid, coordinates):
    return dict(project_code='P', member_ous_uid='M', source_name='S', asdm_uid=uid,
        evidence=dict(fields=[dict(field_id=i, source_id=0, target_name='S', frame='ICRS',
            ra_deg=ra, dec_deg=dec, ra_original=str(ra), dec_original=str(dec), scans=[])
            for i, ra, dec in coordinates]))


def compare(a, b, tolerance=0.1):
    return compare_pointings([a, b], tolerance_arcsec=tolerance)['pairs'][0]


def test_field_identity_is_execution_local_and_inputs_unchanged():
    a = execution('A', [(4, 10, 0), (5, 20, 0)])
    b = execution('B', [(9, 10, 0), (4, 21, 0)])
    before = deepcopy([a, b])
    result = compare(a, b)
    assert result['matches'] == [dict(left_field_id=4, right_field_id=9, separation_arcsec=0.0)]
    assert result['left_fields'][1]['status'] == 'UNMATCHED'
    assert [a, b] == before


def test_wraparound_and_pole():
    assert separation_arcsec(dict(ra_deg=359.99999, dec_deg=0), dict(ra_deg=0.00001, dec_deg=0)) == pytest.approx(0.072, abs=1e-8)
    assert separation_arcsec(dict(ra_deg=0, dec_deg=90), dict(ra_deg=180, dec_deg=90)) < 1e-9
    assert separation_arcsec(dict(ra_deg=0, dec_deg=0), dict(ra_deg=180, dec_deg=0)) == pytest.approx(648000)


def test_known_offset_and_tolerance_sensitivity():
    a, b = execution('A', [(1, 0, 0)]), execution('B', [(2, 1/3600, 0)])
    assert compare(a, b, 0.9)['matched_count'] == 0
    assert compare(a, b, 1.1)['matches'][0]['separation_arcsec'] == pytest.approx(1)


def test_many_to_one_is_ambiguous_even_when_one_is_closer():
    a = execution('A', [(1, 0, 0), (2, 0.01/3600, 0)])
    b = execution('B', [(7, 0, 0)])
    result = compare(a, b)
    assert result['matched_count'] == 0
    assert all(f['status'] == 'AMBIGUOUS' for f in result['left_fields'] + result['right_fields'])


def test_tied_candidates_are_reported():
    a = execution('A', [(1, 10, 0)])
    b = execution('B', [(2, 10, 0), (3, 10, 0)])
    assert compare(a, b)['left_fields'][0]['nearest_field_ids'] == [2, 3]


@pytest.mark.parametrize('tolerance', [0, -1, float('nan'), float('inf'), True])
def test_invalid_tolerance(tolerance):
    with pytest.raises(ValueError):
        compare(execution('A', [(1, 0, 0)]), execution('B', [(2, 0, 0)]), tolerance)


@pytest.mark.parametrize('kind', ['frame', 'nan', 'dec', 'duplicate', 'source', 'asdm'])
def test_invalid_inputs(kind):
    a, b = execution('A', [(1, 0, 0)]), execution('B', [(2, 0, 0)])
    f = b['evidence']['fields'][0]
    if kind == 'frame': f['frame'] = 'FK5'
    if kind == 'nan': f['ra_deg'] = float('nan')
    if kind == 'dec': f['dec_deg'] = 91
    if kind == 'duplicate': b['evidence']['fields'].append(deepcopy(f))
    if kind == 'source': b['source_name'] = 'OTHER'
    if kind == 'asdm': b['asdm_uid'] = 'A'
    with pytest.raises(ValueError): compare(a, b)


@pytest.fixture
def package(tmp_path):
    output = tmp_path / 'audit'
    shutil.copytree(FIXTURE, output)
    audit = json.loads((output / 'package_audit.json').read_text())
    for uid, entry in audit['executions'].items():
        candidate = next(c for c in audit['inspection']['candidates']
                         if c.get('reported_asdm_uid') == uid and c.get('measurement_set_variant') == 'ORIGINAL')
        filename = 'listobs/' + candidate['sha256'] + '.txt'
        e = reconstruct_archive_mosaic((output / filename).read_bytes(), project_code='2017.1.00886.L',
            member_ous_uid=audit['member_ous_uid'], asdm_uid=uid, source_name='IC1954', metadata_reference='discovery.json')
        e = replace(e, metadata_status='MEMBER_PACKAGE_BOUND_NOT_TAP_EXECUTION_BOUND', acquisition_status='VERIFIED_PACKAGE_LISTOBS')
        doc = dict(schema_version='archive_mosaic_package_execution_1', execution=asdict(e),
                   provenance=dict(listobs_file=filename, candidate=candidate,
                       archive_sha256=audit['download']['sha256'], discovery_receipt_sha256=audit['discovery_receipt_sha256']))
        raw = (json.dumps(doc, indent=2) + '\n').encode()
        assert sha256(raw).hexdigest() == entry['sha256']
        (output / entry['execution_file']).write_bytes(raw)
    return output


def test_real_ic1954_keeps_66_records(package):
    executions, provenance = load_package_executions(package)
    report = compare_pointings(executions, tolerance_arcsec=0.1)
    assert report['field_record_count'] == 66
    assert len(report['pairs']) == 3
    assert all(p['matched_count'] == 22 and p['maximum_matched_separation_arcsec'] == 0 for p in report['pairs'])
    assert report['deduplication_status'] == 'NOT_PERFORMED'
    assert len(provenance['execution_evidence']) == 3


@pytest.mark.parametrize('kind', ['execution', 'listobs', 'audit_path', 'inventory'])
def test_tampered_sources_rejected(package, kind):
    audit = json.loads((package / 'package_audit.json').read_text())
    entry = next(iter(audit['executions'].values()))
    if kind == 'execution':
        (package / entry['execution_file']).write_text('{}')
    elif kind == 'listobs':
        doc = json.loads((package / entry['execution_file']).read_text())
        (package / doc['provenance']['listobs_file']).write_bytes(b'changed')
    elif kind == 'audit_path':
        entry['execution_file'] = '../outside.json'
        (package / 'package_audit.json').write_text(json.dumps(audit))
    else:
        (package / 'metadata.xml').write_bytes(b'<broken')
    with pytest.raises((ValueError, KeyError)):
        load_package_executions(package)


def test_cli_no_overwrite(package, tmp_path):
    path = tmp_path / 'report.json'
    args = ['--package-audit-dir', str(package), '--tolerance-arcsec', '0.1', '--output', str(path)]
    assert main(args) == 0
    original = path.read_bytes()
    with pytest.raises(SystemExit): main(args)
    assert path.read_bytes() == original
