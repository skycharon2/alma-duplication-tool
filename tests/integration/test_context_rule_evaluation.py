"""Search-to-rule connection tests with offline source fixtures."""
from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
from alma_duplicate.domain.candidate_search import CandidateDisposition as D, SearchSourceStatus as S
from alma_duplicate.rules import CriterionOutcome as O, EvaluationStatus as E, EvidenceSide
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.evaluation_model import ContextEvaluation
from tests.integration.test_candidate_search import queue_rows, interpretations, SpyClient
from tests.integration.test_search_plan_spatial import validation, archive
from tests.integration.test_rules_angular import with_resolution
from alma_duplicate.search_plan import build_search_plan


def sample(*, limit=None, candidate_resolution=.5, proposed_resolution=.5, q=None):
    v = validation()
    v = replace(v, request=with_resolution(v.request, proposed_resolution),
                search_options=replace(v.search_options, result_limit=limit))
    a, _ = archive(build_search_plan(v), spatial_resolution=candidate_resolution)
    q = queue_rows({}) if q is None else q
    return search_candidates(v, archive_result=a, queue_result=q, interpretations=interpretations(q))


def test_both_sources_keep_candidate_identity_filters_and_provenance():
    search = sample()
    report = evaluate_candidate_search(search)
    assert report.search_result is search
    assert [r.criterion_id for r in report.request_criteria] == ['CONT-SETUP']
    assert len(report.context_evaluations) == 2
    for evaluation, candidate in zip(report.context_evaluations,
                                     search.archive.retained_rows + search.queue.retained_rows):
        assert evaluation.candidate is candidate
        assert evaluation.criteria[0].context_id == candidate.context.context_id
        assert evaluation.criteria[0].criterion_id == 'ANGULAR'
        assert not evaluation.criteria[0].eligible_for_formal_aggregation
    assert report.assessment == 'NOT_AGGREGATED'
    assert search.assessment == 'NOT_EVALUATED'


def test_setup_evaluated_once_independent_of_candidate_count(monkeypatch):
    import alma_duplicate.rules.evaluation as module
    original = module.evaluate_continuum_setup
    calls = []
    def counting(request, **kwargs):
        calls.append(request)
        return original(request, **kwargs)
    monkeypatch.setattr(module, 'evaluate_continuum_setup', counting)
    search = sample(q=queue_rows({}, {'RA': '.1'}))
    report = evaluate_candidate_search(search)
    assert len(report.context_evaluations) == 3
    assert calls == [search.plan.validation.request]


def test_display_limit_does_not_limit_evaluation():
    search = sample(limit=1, q=queue_rows({}, {'RA': '.1'}))
    assert search.truncated and len(search.candidates) == 1
    report = evaluate_candidate_search(search)
    assert len(report.context_evaluations) == search.total_retained == 3
    assert report.search_result.queue.omitted_candidate_ids == search.queue.omitted_candidate_ids


def test_both_missing_sides_remain_visible():
    report = evaluate_candidate_search(sample(candidate_resolution=None, proposed_resolution=None))
    angular = report.context_evaluations[0].criteria[0]
    assert angular.evaluation is E.INSUFFICIENT_INFORMATION and angular.outcome is None
    assert angular.issue_sides == (EvidenceSide.PROPOSED, EvidenceSide.CANDIDATE)


def test_original_plan_request_is_used():
    result = evaluate_candidate_search(sample(proposed_resolution=2., candidate_resolution=.5))
    assert result.context_evaluations[0].criteria[0].outcome is O.NOT_SATISFIED
    assert result.context_evaluations[0].criteria[0].proposed.value == 2.


def test_setup_negative_does_not_short_circuit_angular():
    v = validation(sources=('ARCHIVE',))
    v = replace(v, request=replace(with_resolution(v.request, .5),
                                   spectral_windows=(), setup_complete=True))
    a, _ = archive(build_search_plan(v), spatial_resolution=.5)
    report = evaluate_candidate_search(search_candidates(v, archive_result=a))
    assert report.request_criteria[0].outcome is O.NOT_SATISFIED
    assert report.context_evaluations[0].criteria[0].outcome is O.SATISFIED


def test_unresolved_spatial_filter_does_not_block_angular():
    v = validation(sources=('QUEUE',))
    q = queue_rows({})
    search = search_candidates(v, queue_result=q)  # No artificial position interpretation.
    assert search.queue.retained_rows[0].disposition is D.RETAINED_UNEVALUATED
    report = evaluate_candidate_search(search)
    assert report.context_evaluations[0].criteria[0].evaluation is E.EVALUATED
    assert report.context_evaluations[0].candidate.has_unevaluated_filters


def test_excluded_rows_remain_in_search_audit_only():
    search = sample(q=queue_rows({'RA': '100'}))
    assert search.queue.rows[0].disposition is D.EXCLUDED
    report = evaluate_candidate_search(search)
    assert len(report.context_evaluations) == 1
    assert report.search_result.queue.rows[0] is search.queue.rows[0]


@pytest.mark.parametrize('status', [ArchiveQueryStatus.OVERFLOW, ArchiveQueryStatus.COUNT_MISMATCH])
def test_incomplete_source_does_not_erase_other_source(status):
    v = validation()
    a, _ = archive(build_search_plan(v))
    search = search_candidates(v, archive_result=replace(a, status=status), queue_result=queue_rows({}))
    report = evaluate_candidate_search(search)
    assert report.search_result.archive.status is S.INCOMPLETE
    assert len(report.context_evaluations) == 1
    assert report.context_evaluations[0].candidate.context.reference.source == 'QUEUE'
    assert report.assessment == 'NOT_AGGREGATED'


def test_source_exception_remains_visible():
    search = search_candidates(validation(), archive_client=SpyClient(error=RuntimeError('offline failure')),
                               queue_result=queue_rows({}))
    report = evaluate_candidate_search(search)
    assert report.search_result.archive.status is S.FAILED
    assert len(report.context_evaluations) == 1


def test_binding_failure_remains_visible():
    a, _ = archive(build_search_plan(validation(ra=10)))
    search = search_candidates(validation(), archive_result=a, queue_result=queue_rows({}))
    report = evaluate_candidate_search(search)
    assert report.search_result.archive.query_binding.status == 'MISMATCH'
    assert len(report.context_evaluations) == 1


def test_empty_search_still_evaluates_request_without_absence_verdict():
    v = validation(sources=('QUEUE',))
    report = evaluate_candidate_search(search_candidates(v, queue_result=queue_rows()))
    assert len(report.request_criteria) == 1
    assert report.context_evaluations == ()
    assert report.assessment == 'NOT_AGGREGATED'
    assert report.search_result.archive.status is S.NOT_SELECTED


def test_missing_selected_sources_do_not_become_negative_results():
    report = evaluate_candidate_search(search_candidates(validation()))
    assert report.search_result.archive.status is S.NOT_PROVIDED
    assert report.search_result.queue.status is S.NOT_PROVIDED
    assert report.context_evaluations == ()
    assert report.assessment == 'NOT_AGGREGATED'


def test_conflicting_alternatives_evaluated_separately():
    v = validation(sources=('ARCHIVE',))
    v = replace(v, request=with_resolution(v.request, .5))
    a, _ = archive(build_search_plan(v), spatial_resolution=.5)
    second = dict(a.rows[0]) | {'spatial_resolution': .05}
    a = replace(a, rows=(a.rows[0], second), provenance=replace(a.provenance,
                                                              expected_count=2, retrieved_count=2))
    report = evaluate_candidate_search(search_candidates(v, archive_result=a))
    first, second = report.context_evaluations
    assert first.candidate.context.alternative_context_ids == (second.candidate.context.context_id,)
    assert first.criteria[0].outcome is O.SATISFIED
    assert second.criteria[0].outcome is O.NOT_SATISFIED


def test_duplicate_context_is_rejected_instead_of_overwritten():
    search = sample()
    broken = replace(search, archive=replace(search.archive, rows=search.archive.rows * 2),
                     total_retained=search.total_retained + 1)
    with pytest.raises(ValueError, match='Duplicate'):
        evaluate_candidate_search(broken)


def test_wrong_source_provenance_is_rejected():
    search = sample()
    row = search.archive.rows[0]
    context = replace(row.context, reference=replace(row.context.reference, source='QUEUE'))
    broken = replace(search, archive=replace(search.archive, rows=(replace(row, context=context),)))
    with pytest.raises(ValueError, match='provenance'):
        evaluate_candidate_search(broken)


@pytest.mark.parametrize('kind', ['execution', 'request', 'count', 'source_status'])
def test_inconsistent_search_contract_is_rejected(kind):
    search = sample()
    if kind == 'execution':
        search = replace(search, execution='RUNNING')
    elif kind == 'request':
        search = replace(search, plan=replace(search.plan,
                         validation=replace(search.plan.validation, request=None)))
    elif kind == 'count':
        search = replace(search, total_retained=99)
    else:
        search = replace(search, archive=replace(search.archive, status=S.FAILED))
    with pytest.raises(ValueError):
        evaluate_candidate_search(search)


def test_context_model_rejects_wrong_result_association():
    report = evaluate_candidate_search(sample())
    first, second = report.context_evaluations
    with pytest.raises(ValueError, match='different candidate'):
        ContextEvaluation(candidate=first.candidate, criteria=second.criteria)


def test_programming_error_is_not_silently_missing_evidence(monkeypatch):
    import alma_duplicate.rules.evaluation as module
    def broken(*args):
        raise RuntimeError('implementation bug')
    monkeypatch.setattr(module, 'evaluate_angular_resolution', broken)
    with pytest.raises(RuntimeError, match='implementation bug'):
        evaluate_candidate_search(sample())


def test_invalid_conversion_is_rejected_without_scientific_result():
    with pytest.raises(ValueError, match='conversion'):
        evaluate_candidate_search(sample(), nominal_conversion='GUESS')
