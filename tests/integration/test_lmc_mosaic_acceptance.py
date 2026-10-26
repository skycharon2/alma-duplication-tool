"""Captured multi-target LMC evidence through the common assessment entry.

Proposal inputs are constructed test cases, not an observed proposal.
Network discovery/preparation are replay boundaries; readiness is rebuilt.
"""
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from alma_duplicate.assessment import assess_observation, AssessmentSources, ArchiveInput
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.clients import archive_contract as contract
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.mosaic_readiness_binding import load_candidate_catalog
from alma_duplicate.parsers.archive_listobs import parse_science_fields
from alma_duplicate.proposed_mosaic import import_proposed

ROOT = Path('tests/fixtures/archive/lmc_mosaic_2026_10_26')
MEMBER = 'uid://A001/X879/X6e7'
ASDM = 'uid://A002/Xb8f857/X3977'


def captured_metadata(root=ROOT):
    saved = json.loads((root / 'metadata.json').read_text())
    p = saved['provenance']
    for name in ('started_at', 'finished_at'):
        p[name] = datetime.fromisoformat(p[name])
    p['normalized_parameters'] = tuple(tuple(v) for v in p['normalized_parameters'])
    projection = p['projection']
    projection['optional_columns'] = tuple(contract.ArchiveOptionalColumnEvidence(**v)
                                           for v in projection['optional_columns'])
    p['projection'] = contract.ArchiveProjectionEvidence(**projection)
    return contract.ArchiveQueryResult(status=contract.ArchiveQueryStatus(saved['status']),
        rows=tuple(saved['rows']), provenance=contract.ArchiveQueryProvenance(**p),
        field_metadata=tuple(contract.TapFieldMetadata(**f) for f in saved['field_metadata']))


def run_case(tmp_path, monkeypatch, variant):
    import alma_duplicate.mosaic_backend as backend
    catalog = load_candidate_catalog({'directory': str(ROOT)})
    readiness = build_readiness(ROOT / 'package', catalog=catalog)
    assert [f['field_id'] for f in readiness['executions'][0]['fields']] == [2, 3, 4]
    assert all(f['position_status'] == 'EVIDENCE_BOUND' for f in readiness['executions'][0]['fields'])
    raw = Path('tests/fixtures/archive/mosaic_target_selection_2026_10_26/lmc-listobs.txt').read_bytes()
    target = 'LMC1N127' if variant == 'other_target' else 'LMC0NT197'
    fields = parse_science_fields(raw, asdm_uid=ASDM, target_name=target).fields
    coordinates = [(f.ra_deg, f.dec_deg) for f in fields]
    if variant == 'half':
        coordinates = coordinates[:2] + [(180, 0), (181, 0)]
    text = 'RA,Dec,Coordinate Type,Coordinate Units\n--\n' + ''.join(
        f'{ra},{dec},Absolute,Degrees\n' for ra, dec in coordinates)
    proposed = import_proposed(text.encode(), source_name='LMC_CONSTRUCTED_TEST', array='7m',
                               confirm_fixed_icrs=True, confirm_complete=True)
    ready_file = tmp_path / 'readiness.json'
    ready_file.write_text(json.dumps(readiness))
    monkeypatch.setattr(backend, 'discover_candidates', lambda *a, **k: dict(
        status='COMPLETED', plan=dict(recall_status='NOT_ESTABLISHED')))
    monkeypatch.setattr(backend, 'prepare_candidates', lambda *a, **k: dict(status='COMPLETED',
        candidates=[dict(member_ous_uid=MEMBER, source_name='LMC0NT197', directory=str(ROOT),
                        package_audit_dir=str(ROOT/'package'), readiness_file=str(ready_file))]))
    metadata = captured_metadata()
    row = metadata.rows[0]
    payload = json.loads(Path('examples/mosaic/case2/continuum-test-request.json').read_text())
    request = payload['request']
    request['target_name'] = proposed['source_name']
    request['angular_resolution']['value'] = row['spatial_resolution']
    request['representative_frequency']['value'] = row['frequency']
    for window in request['spectral_windows']:
        window['center']['value'] = row['frequency']
    request['sensitivities'][0]['rms']['value'] = row['cont_sensitivity_bandwidth']
    if variant == 'angular':
        request['angular_resolution']['value'] = 0.01
    elif variant == 'frequency':
        request['representative_frequency']['value'] = 690
    def search(spec):
        assert (spec.member_ous_uid, spec.target_name) == (MEMBER, 'LMC0NT197')
        return metadata
    result = assess_observation(request, payload['search_options'],
        sources=AssessmentSources('LIVE', lambda: ArchiveInput(SimpleNamespace(search=search))),
        mosaic=legacy_mosaic_input(proposed, tmp_path/'run', tmp_path/'cache', 1.0))
    assert result.validation.is_valid
    return json.loads((tmp_path/'run/assessment.json').read_text())


@pytest.mark.parametrize('variant', ['positive', 'other_target', 'half', 'angular', 'frequency'])
def test_multitarget_main_entry(tmp_path, monkeypatch, variant):
    report = run_case(tmp_path, monkeypatch, variant)
    candidate = report['candidates'][0]
    assert candidate['status'] == 'EVALUATED'
    contexts = candidate['evaluation']['contexts']
    assert len(contexts) == 4
    for context in contexts:
        position = next(c for c in context['criteria'] if c['criterion_id'] == 'POS-MOSAIC')
        if variant in ('positive', 'angular', 'frequency'):
            assert position['outcome'] == 'SATISFIED'
            assert context['coverage']['inside_count'] == 3
        else:
            assert position['outcome'] != 'SATISFIED'
            assert context['coverage']['inside_count'] == (2 if variant == 'half' else 0)
    outcomes = [b['truth'] for c in contexts for b in c['branches']]
    if variant == 'positive':
        assert 'TRUE' in outcomes
    else:
        assert 'TRUE' not in outcomes
    assert report['discovery_recall_status'] == 'NOT_ESTABLISHED'


def legacy_mosaic_input(*args, **kwargs):
    return MosaicAssessmentInput(*args, coverage_model="RECONSTRUCTED", **kwargs)
