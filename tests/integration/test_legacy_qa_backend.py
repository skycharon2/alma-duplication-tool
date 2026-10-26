"""Unverified legacy QA cannot become coverage or hide a valid second candidate."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from alma_duplicate.assessment import assess_observation, AssessmentSources, ArchiveInput
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.mosaic_readiness_binding import load_candidate_catalog
from alma_duplicate.mosaic_pointing_diagnostics import alternative_diagnostics
from alma_duplicate.proposed_mosaic import import_proposed
from tests.integration import test_lmc_mosaic_acceptance as lmc

ROOT = Path('tests/fixtures/archive/legacy_qa_text_2026_10_26')
CANDIDATE = dict(member_ous_uid='uid://A001/X140/X6', source_name='RX_J1347.5-1145',
                 directory=str(ROOT), package_audit_dir=str(ROOT/'package'))


def test_qa_reparsed_not_trusted(tmp_path):
    import shutil
    shutil.copytree(ROOT/'package', tmp_path/'package')
    candidate = dict(CANDIDATE, package_audit_dir=str(tmp_path/'package'))
    p = tmp_path/'package/package_audit.json'
    audit = json.loads(p.read_text())
    # A stale or edited saved summary cannot declare coordinates ready.
    audit['inspection']['alternative_evidence'][0].update(position_status='EVIDENCE_BOUND', reasons=[])
    p.write_text(json.dumps(audit))
    result = alternative_diagnostics(candidate)
    assert result['status'] == 'UNVERIFIED_ALTERNATIVE_EVIDENCE'
    assert len(result['sources']) == 4
    assert all(s['science_field_count'] == 7 and s['position_status'] == 'NOT_READY' for s in result['sources'])
    assert 'INDEPENDENT_COORDINATE_REFERENCE_MISSING' in result['reasons']
    digest = audit['inspection']['alternative_evidence'][0]['sha256']
    (tmp_path/'package/listobs'/(digest+'.txt')).write_bytes(b'corrupted')
    assert alternative_diagnostics(candidate)['status'] == 'INVALID_ALTERNATIVE_EVIDENCE'


@pytest.mark.parametrize('variant', ['positive', 'angular', 'frequency', 'half'])
def test_main_entry_qa_unknown_and_valid_candidate_isolated(tmp_path, monkeypatch, variant):
    import alma_duplicate.mosaic_backend as backend
    lmc_metadata = lmc.captured_metadata()
    rx_metadata = lmc.captured_metadata(ROOT)
    good = dict(member_ous_uid=lmc.MEMBER, source_name='LMC0NT197', directory=str(lmc.ROOT),
                package_audit_dir=str(lmc.ROOT/'package'))
    readiness = build_readiness(lmc.ROOT/'package', catalog=load_candidate_catalog(good))
    ready_file = tmp_path/'readiness.json'
    ready_file.write_text(json.dumps(readiness))
    good['readiness_file'] = str(ready_file)
    fields = readiness['executions'][0]['fields']
    coords = [(f['ra_deg'], f['dec_deg']) for f in fields]
    if variant == 'half':
        coords = coords[:2] + [(180, 0), (181, 0)]
    text = 'RA,Dec,Coordinate Type,Coordinate Units\n--\n' + ''.join(
        f'{ra},{dec},Absolute,Degrees\n' for ra, dec in coords)
    proposed = import_proposed(text.encode(), source_name='CONSTRUCTED_ACCEPTANCE', array='7m',
                               confirm_fixed_icrs=True, confirm_complete=True)
    payload = json.loads(Path('examples/mosaic/case2/continuum-test-request.json').read_text())
    request = payload['request']
    row = lmc_metadata.rows[0]
    request['target_name'] = proposed['source_name']
    request['angular_resolution']['value'] = .01 if variant == 'angular' else row['spatial_resolution']
    request['representative_frequency']['value'] = 690 if variant == 'frequency' else row['frequency']
    for w in request['spectral_windows']:
        w['center']['value'] = row['frequency']
    request['sensitivities'][0]['rms']['value'] = row['cont_sensitivity_bandwidth']
    monkeypatch.setattr(backend, 'discover_candidates', lambda *a, **k: dict(status='COMPLETED',
        plan=dict(recall_status='NOT_ESTABLISHED')))
    monkeypatch.setattr(backend, 'prepare_candidates', lambda *a, **k: dict(status='INCOMPLETE',
        candidates=[deepcopy(CANDIDATE), good]))
    def search(spec):
        return rx_metadata if spec.member_ous_uid == CANDIDATE['member_ous_uid'] else lmc_metadata
    result = assess_observation(request, payload['search_options'],
        sources=AssessmentSources('LIVE', lambda: ArchiveInput(SimpleNamespace(search=search))),
        mosaic=legacy_mosaic_input(proposed, tmp_path/'run', tmp_path/'cache', 1.0))
    assert result.validation.is_valid
    report = json.loads((tmp_path/'run/assessment.json').read_text())
    rx, valid = report['candidates']
    assert rx['alternative_pointing_diagnostics']['status'] == 'UNVERIFIED_ALTERNATIVE_EVIDENCE'
    assert all(s['outcome'] is None and s['inside_count'] is None for s in rx['position_summary'])
    assert valid['status'] == 'EVALUATED'
    assert all(s['inside_count'] == (2 if variant == 'half' else 3) for s in valid['position_summary'])
    truth = [b['truth'] for c in valid['evaluation']['contexts'] for b in c['branches']]
    assert ('TRUE' in truth) == (variant == 'positive')
    assert report['assessment_status'] == 'INCOMPLETE'


def test_qa_candidate_identity_cannot_cross_sources():
    candidate = dict(CANDIDATE, source_name='another target')
    result = alternative_diagnostics(candidate)
    assert result['status'] == 'INVALID_ALTERNATIVE_EVIDENCE'
    assert result['sources'] == []


def legacy_mosaic_input(*args, **kwargs):
    return MosaicAssessmentInput(*args, coverage_model="RECONSTRUCTED", **kwargs)
