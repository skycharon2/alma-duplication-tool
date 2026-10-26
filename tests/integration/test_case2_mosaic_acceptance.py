"""Actual OT export and captured CASE2 evidence; proposals variants are synthetic."""
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path

import pytest
from alma_duplicate.clients import archive_contract as contract
from alma_duplicate.comparison import build_archive_contexts
from alma_duplicate.assessment import assess_archive_mosaic_contexts
from alma_duplicate.mosaic_readiness_binding import load_candidate_catalog
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.proposed_mosaic import import_proposed
from tests.integration.test_mosaic_context import data

ROOT = Path('tests/fixtures/archive/case2_mosaic_2026_10_26')


def captured_metadata(member):
    saved = json.loads((ROOT / member / 'metadata.json').read_text())
    p = saved['provenance']
    for name in ('started_at', 'finished_at'):
        p[name] = datetime.fromisoformat(p[name])
    p['normalized_parameters'] = tuple(tuple(v) for v in p['normalized_parameters'])
    projection = p['projection']
    projection['optional_columns'] = tuple(contract.ArchiveOptionalColumnEvidence(**v)
                                            for v in projection['optional_columns'])
    p['projection'] = contract.ArchiveProjectionEvidence(**projection)
    return contract.ArchiveQueryResult(
        status=contract.ArchiveQueryStatus(saved['status']), rows=tuple(saved['rows']),
        provenance=contract.ArchiveQueryProvenance(**p),
        field_metadata=tuple(contract.TapFieldMetadata(**f) for f in saved['field_metadata']))


def assess_case(member, variant='original'):
    proposed = import_proposed((ROOT / 'ot-12m.txt').read_bytes(),
        source_name='NGC253_CASE2_TEST', array='12m',
        confirm_fixed_icrs=True, confirm_complete=True)
    if variant != 'original':
        points = proposed['points']
        outside = dict(points[0], id='outside', ra_deg=180.0)
        proposed['points'] = ({'two_inside': points[:2] + [outside],
                               'one_inside': points[:1] + [outside, dict(outside, id='outside2')],
                               'half': points[:2] + [outside, dict(outside, id='outside2')]}[variant])
    metadata = captured_metadata(member)
    contexts = build_archive_contexts(metadata).contexts
    directory = ROOT / member
    catalog = load_candidate_catalog({'directory': str(directory)})
    readiness = build_readiness(directory / 'package', catalog=catalog)
    ready = {e['asdm_uid'] for e in readiness['executions']
             if e['fields'] and all(f['position_status'] == 'EVIDENCE_BOUND' for f in e['fields'])}
    request = replace(data()[0], target_name=proposed['source_name'])
    key = ('uid://A001/X133d/' + member, 'NGC253')
    return assess_archive_mosaic_contexts(request, proposed, contexts,
        package_directories={key: directory / 'package'}, array_catalog=catalog,
        ready_executions={key: ready}, archive_result=metadata)


@pytest.mark.parametrize('member', ['X9c3', 'X9c5'])
@pytest.mark.parametrize('variant,inside,total,outcome', [
    ('original', 3, 3, 'SATISFIED'), ('two_inside', 2, 3, 'SATISFIED'),
    ('one_inside', 1, 3, None), ('half', 2, 4, None)])
def test_case2_position_with_actual_ot_export(member, variant, inside, total, outcome):
    report = assess_case(member, variant)
    assert len(report['contexts']) == 4
    for context in report['contexts']:
        position = next(c for c in context['criteria'] if c['criterion_id'] == 'POS-MOSAIC')
        assert position['outcome'] == outcome
        assert context['coverage']['inside_count'] == inside
        assert context['coverage']['pointing_count'] == total
        assert len(context['coverage']['included_asdm_uids']) == 1
        assert context['coverage']['excluded_executions']


def test_actual_ot_export_preserves_source_positions():
    from alma_duplicate.parsers.ot_pointings import parse_ot_pointings
    original = parse_ot_pointings(Path('examples/mosaic/case2/ngc253-X9c3-pointings.txt').read_bytes())
    exported = parse_ot_pointings((ROOT / 'ot-12m.txt').read_bytes())
    assert [(p['ra_deg'], p['dec_deg']) for p in exported['points']] == [
        (p['ra_deg'], p['dec_deg']) for p in original['points']]


@pytest.mark.parametrize('member', ['X9c3', 'X9c5'])
def test_common_entry_with_captured_case2(tmp_path, monkeypatch, member):
    from types import SimpleNamespace
    from alma_duplicate.assessment import assess_observation, AssessmentSources, ArchiveInput
    from alma_duplicate.mosaic_resource_limits import MosaicResourceLimits
    import alma_duplicate.mosaic_backend as backend
    directory = ROOT / member
    catalog = load_candidate_catalog({'directory': str(directory)})
    readiness = build_readiness(directory / 'package', catalog=catalog)
    readiness_file = tmp_path / 'readiness.json'
    readiness_file.write_text(json.dumps(readiness))
    limits = MosaicResourceLimits(1_000_000_000, 1_000_000_000, 10_000_000_000)
    def discovery(*args, **kwargs):
        return dict(status='COMPLETED', plan=dict(recall_status='NOT_ESTABLISHED'))
    def preparation(discovery, **kwargs):
        assert kwargs['resource_limits'] == limits
        return dict(status='COMPLETED', candidates=[dict(
            member_ous_uid='uid://A001/X133d/' + member, source_name='NGC253',
            directory=str(directory), package_audit_dir=str(directory / 'package'),
            readiness_file=str(readiness_file))])
    monkeypatch.setattr(backend, 'discover_candidates', discovery)
    monkeypatch.setattr(backend, 'prepare_candidates', preparation)
    proposed = import_proposed((ROOT / 'ot-12m.txt').read_bytes(), source_name='NGC253_CASE2_TEST',
        array='12m', confirm_fixed_icrs=True, confirm_complete=True)
    payload = json.loads(Path('examples/proposed_observation.json').read_text())
    payload['request'].update(geometry='MOSAIC', target_name=proposed['source_name'])
    payload['request'].pop('position')
    payload['search_options'].update(sources=['ARCHIVE'], predicates=[])
    def search(spec):
        assert (spec.member_ous_uid, spec.target_name) == ('uid://A001/X133d/' + member, 'NGC253')
        return captured_metadata(member)
    assess_observation(payload['request'], payload['search_options'],
        sources=AssessmentSources('LIVE', lambda: ArchiveInput(client=SimpleNamespace(search=search))),
        mosaic=legacy_mosaic_input(proposed, tmp_path / 'run', tmp_path / 'cache', 1.0, limits))
    report = json.loads((tmp_path / 'run/assessment.json').read_text())
    assert report['assessment_status'] == 'COMPLETED'
    for context in report['candidates'][0]['evaluation']['contexts']:
        assert next(c for c in context['criteria'] if c['criterion_id'] == 'POS-MOSAIC')['outcome'] == 'SATISFIED'


def legacy_mosaic_input(*args, **kwargs):
    from alma_duplicate.mosaic_backend import MosaicAssessmentInput
    return MosaicAssessmentInput(*args, coverage_model="RECONSTRUCTED", **kwargs)
