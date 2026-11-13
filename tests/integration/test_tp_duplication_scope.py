"""TP flags retain provenance without creating duplication decisions."""
import pytest

from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.queue_line_pairing import build_queue_line_pairs
from tests.integration.test_archive_array_adapter import synthetic
from tests.integration.test_queue_line_pairing import request, contexts


def test_tp_only_never_invokes_scientific_context_evaluator(monkeypatch):
    import alma_duplicate.rules.evaluation as evaluation
    search, catalog = synthetic('TP', intents=('CONTINUUM', 'LINE'))
    def forbidden(*args, **kwargs):
        pytest.fail('TP must be excluded before scientific evaluation')
    monkeypatch.setattr(evaluation, '_evaluate_context', forbidden)
    result = evaluate_candidate_search(search, archive_arrays=catalog)
    item = result.context_evaluations[0]
    assert item.exclusion_reason == 'TP_IGNORED_FOR_DUPLICATION'
    assert not item.criteria and not item.branches and not item.line_pairs


@pytest.mark.parametrize('polarization', ['DOUBLE', 'FULL'])
def test_queue_line_tp_never_requests_tp_processor_mapping(monkeypatch, polarization):
    import alma_duplicate.queue_mode_adapter as modes
    def forbidden(*args, **kwargs):
        pytest.fail('Duplication must not evaluate a TP processor counterpart')
    monkeypatch.setattr(modes, 'map_tp_counterpart', forbidden)
    clean, mixed = [build_queue_line_pairs(request(), contexts({
        'Polarization': polarization, 'Use TP?': flag})[0]) for flag in ('False', 'True')]
    assert len(clean.attempts) == len(mixed.attempts)
    for a, b in zip(clean.attempts, mixed.attempts):
        assert a.candidate.mode['mode_evidence'] == b.candidate.mode['mode_evidence']
        assert a.reasons == b.reasons
        assert b.candidate.mode['source']['use_tp'] is True


def test_tp_only_mosaic_is_not_a_review_or_match_result(tmp_path, monkeypatch):
    from tests.integration.test_s_region_backend import run_case
    from alma_duplicate.ui.mosaic_report_view import mosaic_report_projection
    document = run_case(tmp_path, monkeypatch, 'continuum', 'tp')
    index = mosaic_report_projection(document)
    counts = index['mosaic_overview']['candidate_buckets']
    assert counts['IGNORED'] > 0
    assert all(c['bucket'] == 'IGNORED' for c in index['candidate_summaries']
               if c['contexts'] and all(x['ignored_tp'] for x in c['contexts']))


def test_v2_mosaic_tp_exclusion_precedes_angular_and_line_calculations(monkeypatch):
    from tests.integration.test_submitted_line_assessment_step04c import _wire
    from tests.integration.test_mosaic_scientific_acceptance import _line_case
    from alma_duplicate.submitted_line_assessment import assess_submitted_line_mosaic_v2
    import alma_duplicate.rules.mosaic_context as mosaic
    _, context, pointings, execution, evidence = _line_case()
    evidence.components = ('TOTAL_POWER',)
    evidence.diameters_m = ()
    def forbidden(*args, **kwargs):
        pytest.fail('TP-only Mosaic must not calculate angular or spectral criteria')
    monkeypatch.setattr(mosaic, 'evaluate_angular_resolution', forbidden)
    document = _wire(geometry='MOSAIC')
    result = assess_submitted_line_mosaic_v2(document['request'], (context,), pointings,
        use_s_region=False, executions=(execution,), array_evidence=evidence)
    item = result['contexts'][0]
    assert item['exclusion_reason'] == 'TP_IGNORED_FOR_DUPLICATION'
    assert not item['criteria'] and not item['branches'] and not item['line_pairs']


def test_queue_legacy_candidate_position_tp_flag_is_not_a_blocker():
    from tests.integration.test_position_single import search, criterion
    clean = criterion(search({'Use TP?': 'False'}))
    mixed = criterion(search({'Use TP?': 'True'}))
    assert clean.outcome == mixed.outcome == 'SATISFIED'
    assert 'TP_GEOMETRY_UNSUPPORTED' not in mixed.reasons
