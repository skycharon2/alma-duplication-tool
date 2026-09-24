"""Evaluate the request and all retained contexts from a finished search.

This explicit offline step neither repeats retrieval nor changes filter results.
The request is taken from the original plan; no substitute request is accepted.
"""
from __future__ import annotations

from alma_duplicate.domain.candidate_search import CandidateSearchResult, SearchSourceStatus
from alma_duplicate.rules.line import evaluate_line
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup
from alma_duplicate.rules.evaluation_model import ContextEvaluation, EvaluationReport
from alma_duplicate.rules.confirmed import approve_angular, approve_setup, archive_scope
from alma_duplicate.rules.continuum import evaluate_continuum_frequency, evaluate_continuum_rms
from alma_duplicate.rules.aggregation import aggregate_continuum


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
    queue_common: bool = False, queue_continuum: bool = False,
) -> EvaluationReport:
    """Evaluate selected branches for every retained context, including hidden rows.

Failed/incomplete sources remain in the original report. Their absence never
becomes a negative criterion result. Queue mappings keep their legacy approval
unless the explicit common-method option selects its versioned project adoption.
Programming/contract errors propagate; they are not scientific missing evidence.
"""
    queue_common = queue_common or queue_continuum
    _check_search(search_result)
    request = search_result.plan.validation.request

    continuum = "CONTINUUM" in request.intents
    setup = (approve_setup(evaluate_continuum_setup(request, nominal_conversion=nominal_conversion),
                           nominal_conversion=nominal_conversion) if continuum else None)
    contexts = []
    for source in (search_result.archive, search_result.queue):
        for row in source.retained_rows:
            context = row.context
            criteria = []
            branches = []
            if request.intents and queue_common and context.reference.source == "QUEUE":
                from alma_duplicate.rules.queue_common import evaluate_queue_common
                criteria.extend(evaluate_queue_common(request, context, row.spatial_evidence))
            elif request.intents:
                criteria.extend((approve_angular(evaluate_angular_resolution(request, context), request, context),
                                 evaluate_position_single(request, context, row.spatial_evidence)))
            if continuum:
                if queue_continuum and context.reference.source == "QUEUE":
                    from alma_duplicate.rules.queue_continuum import evaluate_queue_continuum, scope_supported
                    supported = scope_supported(criteria)
                    criteria.extend(evaluate_queue_continuum(request, context, criteria))
                    branches.append(aggregate_continuum(context, (setup, *criteria),
                                                       supported=supported, queue_method=True))
                else:
                    criteria.extend((evaluate_continuum_frequency(request, context),
                                     evaluate_continuum_rms(request, context)))
                    supported = (archive_scope(request, context) and
                        context.evidence.prepared.normalized_metadata.is_mosaic.value is False and
                        not {"UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED",
                             "CONFLICTING_POSITION_INTERPRETATION"}.intersection(criteria[1].reasons))
                    branches.append(aggregate_continuum(context, (setup, *criteria), supported=supported))
            pairing, pairs = None, ()
            if "LINE" in request.intents:
                pairing, pairs, branch = evaluate_line(request, context, tuple(criteria[:2]))
                branches.append(branch)
            contexts.append(ContextEvaluation(candidate=row, criteria=tuple(criteria), branches=tuple(branches),
                                              line_pairing=pairing, line_pairs=pairs))
    return EvaluationReport(search_result=search_result, request_criteria=() if setup is None else (setup,),
                            context_evaluations=tuple(contexts))
