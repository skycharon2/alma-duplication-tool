"""Evaluate the request and all retained contexts from a finished search.

This explicit offline step neither repeats retrieval nor changes filter results.
The request is taken from the original plan; no substitute request is accepted.
"""
from __future__ import annotations

from alma_duplicate.domain.candidate_search import CandidateSearchResult, SearchSourceStatus
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup
from alma_duplicate.rules.evaluation_model import ContextEvaluation, EvaluationReport


def _check_search(result: CandidateSearchResult) -> None:
    validation = result.plan.validation
    if (result.execution != "FINISHED" or not validation.is_valid
            or not validation.can_search or validation.request is None):
        raise ValueError("Evaluation requires a finished search with its valid search-ready request")
    seen = set()
    retained_count = 0
    for name, source in (("ARCHIVE", result.archive), ("QUEUE", result.queue)):
        if source.source != name:
            raise ValueError("Source execution is in the wrong source slot")
        if source.rows and source.status is not SearchSourceStatus.COMPLETED:
            raise ValueError("Strict source contract does not allow rows from unsuccessful sources")
        for row in source.rows:
            context = row.context
            if context.reference.source != name:
                raise ValueError("Candidate provenance disagrees with its source execution")
            key = (name, context.context_id)
            if key in seen:
                raise ValueError("Duplicate candidate context identity")
            seen.add(key)
        retained_count += len(source.retained_rows)
    if retained_count != result.total_retained:
        raise ValueError("Retained source rows disagree with total_retained")


def evaluate_candidate_search(
    search_result: CandidateSearchResult, *, nominal_conversion: str | None = None,
) -> EvaluationReport:
    """CONT-SETUP once; ANGULAR for each retained context, including hidden rows.

Failed/incomplete sources remain in the original report. Their absence never
becomes a negative criterion result. All current evaluators remain provisional.
Programming/contract errors propagate; they are not scientific missing evidence.
"""
    _check_search(search_result)
    request = search_result.plan.validation.request
    setup = evaluate_continuum_setup(request, nominal_conversion=nominal_conversion)
    contexts = tuple(
        ContextEvaluation(candidate=row, criteria=(evaluate_angular_resolution(request, row.context),))
        for source in (search_result.archive, search_result.queue)
        for row in source.retained_rows
    )
    return EvaluationReport(search_result=search_result, request_criteria=(setup,),
                            context_evaluations=contexts)
