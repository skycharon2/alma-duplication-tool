"""Constructed proposals against unmodified CASE2 captures through the main entry."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from alma_duplicate.assessment import assess_observation, AssessmentSources, ArchiveInput
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.mosaic_readiness_binding import load_candidate_catalog
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.proposed_mosaic import import_proposed
from tests.integration.test_case2_mosaic_acceptance import ROOT, captured_metadata


def run_case(tmp_path, monkeypatch, mode, variant='positive'):
    import alma_duplicate.mosaic_backend as backend
    payload = json.loads(Path(f'examples/mosaic/case2/{mode}-test-request.json').read_text())
    request = payload['request']
    if variant == 'angular':
        request['angular_resolution']['value'] = 1.0
    elif variant == 'frequency':
        if mode == 'continuum':
            request['representative_frequency']['value'] = 100
        else:
            request['spectral_windows'][0]['center']['value'] = 100
    elif variant == 'sensitivity':
        request['sensitivities'][0]['rms']['value'] = 0.001
    elif variant == 'missing_proposed_rms':
        request['sensitivities'][0].pop('rms')
    elif variant == 'resolution':
        request['sensitivities'][0]['smoothing_resolution']['value'] = 0.1
    members = ['X9c3', 'X9c5']
    candidates = []
    for member in members:
        directory = ROOT / member
        catalog = load_candidate_catalog({'directory': str(directory)})
        readiness = build_readiness(directory / 'package', catalog=catalog)
        filename = tmp_path / f'{member}-readiness.json'
        filename.write_text(json.dumps(readiness))
        candidates.append(dict(member_ous_uid='uid://A001/X133d/' + member, source_name='NGC253',
            directory=str(directory), package_audit_dir=str(directory / 'package'), readiness_file=str(filename)))
    monkeypatch.setattr(backend, 'discover_candidates', lambda *a, **k: dict(
        status='COMPLETED', plan=dict(recall_status='NOT_ESTABLISHED')))
    monkeypatch.setattr(backend, 'prepare_candidates', lambda *a, **k: dict(
        status='COMPLETED', candidates=candidates))
    def search(spec):
        member = spec.member_ous_uid.split('/')[-1]
        metadata = captured_metadata(member)
        if variant in ('missing_candidate_rms', 'split_candidates'):
            rows = deepcopy([dict(r) for r in metadata.rows])
            for row in rows:
                if variant == 'split_candidates':
                    # X9c3 passes angular but fails frequency; X9c5 does the reverse.
                    if member == 'X9c3':
                        row['frequency'] = 100.0
                    continue
                if mode == 'continuum':
                    row['cont_sensitivity_bandwidth'] = None
                else:
                    row['frequency_support'] = None
                    row['sensitivity_10kms'] = None
            metadata = replace(metadata, rows=tuple(rows))
        return metadata
    proposed = import_proposed((ROOT / 'ot-12m.txt').read_bytes(),source_name=request['target_name'],
        array='12m',confirm_fixed_icrs=True,confirm_complete=True)
    result = assess_observation(request,payload['search_options'],
        sources=AssessmentSources('LIVE',lambda:ArchiveInput(SimpleNamespace(search=search))),
        mosaic=legacy_mosaic_input(proposed,tmp_path/'run',tmp_path/'cache',1.0))
    assert result.validation.is_valid
    return json.loads((tmp_path/'run/assessment.json').read_text())


@pytest.mark.parametrize('mode', ['continuum','line'])
@pytest.mark.parametrize('variant', ['positive','angular','frequency','sensitivity',
                                     'missing_proposed_rms','missing_candidate_rms'])
def test_joint_criteria_main_entry(tmp_path,monkeypatch,mode,variant):
    report=run_case(tmp_path,monkeypatch,mode,variant)
    candidates=report['candidates']
    first=candidates[0]['evaluation']['contexts']
    outcomes=[b['truth'] for c in first for b in c['branches']]
    if variant=='positive':
        assert 'TRUE' in outcomes
    elif variant.startswith('missing'):
        assert 'TRUE' not in outcomes and 'UNKNOWN' in outcomes
    else:
        assert set(outcomes)=={'FALSE'}
    for c in first:
        pos=next(x for x in c['criteria'] if x['criterion_id']=='POS-MOSAIC')
        assert pos['outcome']=='SATISFIED'
    # The same proposal's angular resolution does not match the second Member.
    if variant=='positive':
        assert all(b['truth']=='FALSE' for c in candidates[1]['evaluation']['contexts'] for b in c['branches'])


def test_line_spectral_resolution_failure(tmp_path,monkeypatch):
    report=run_case(tmp_path,monkeypatch,'line','resolution')
    assert all(b['truth']=='FALSE' for c in report['candidates'][0]['evaluation']['contexts'] for b in c['branches'])


def test_conditions_are_not_pooled_across_members(tmp_path,monkeypatch):
    report=run_case(tmp_path,monkeypatch,'continuum','split_candidates')
    contexts=[c for candidate in report['candidates'] for c in candidate['evaluation']['contexts']]
    assert all(b['truth']=='FALSE' for c in contexts for b in c['branches'])
    rules=[{x['criterion_id']:x['outcome'] for x in c['criteria']} for c in contexts]
    assert any(r['ANGULAR']=='SATISFIED' for r in rules)
    assert any(r['CONT-FREQ']=='SATISFIED' for r in rules)
    assert not any(r['ANGULAR']==r['CONT-FREQ']=='SATISFIED' for r in rules)


def legacy_mosaic_input(*args, **kwargs):
    return MosaicAssessmentInput(*args, coverage_model="RECONSTRUCTED", **kwargs)
