"""Request-driven orchestration over the existing Archive and Queue layers."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Callable, Iterable, Protocol

from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.clients.archive_queries import ArchiveQuerySpec
from alma_duplicate.comparison import build_archive_contexts, build_queue_contexts
from alma_duplicate.domain.candidate_search import (
    CandidateDisposition as D, CandidateRecord, CandidateSearchResult, FilterExecution,
    SearchSourceStatus as S, SourceSearchExecution,
)
from alma_duplicate.domain.comparison import ComparisonContext, SourceStatus
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.domain.queue import QueueCsvParseResult
from alma_duplicate.domain.search import SearchPlan
from alma_duplicate.domain.spatial import PositionInterpretation
from alma_duplicate.search_plan import build_search_plan, bind_archive_query, evaluate_angular_filter
from alma_duplicate.spatial import adapt_spatial, evaluate_spatial


class ArchiveSearcher(Protocol):
    def search(self, spec: ArchiveQuerySpec) -> ArchiveQueryResult:
        """Execute the provided spec; ArchiveClient implements this interface."""
        ...


def _evaluate_row(
    plan: SearchPlan, context: ComparisonContext, source_record, interpretations,
) -> CandidateRecord:
    source = plan.for_source(context.reference.source)
    assert source is not None
    spatial_evidence = None
    spatial_error = None
    try:
        spatial_evidence = adapt_spatial(
            context, source_record, interpretation=interpretations.get(context.context_id),
        )
    except Exception as exc:
        # Keep this row and continue evaluating independent evidence.
        spatial_error = (type(exc).__name__, str(exc))
    records = []
    for index, predicate in enumerate(source.predicates):
        if predicate.action == "SKIPPED":
            records.append(FilterExecution(index, predicate.name, "NONE", "SKIPPED",
                                           (predicate.reason or "FILTER_NOT_IMPLEMENTED",)))
            continue
        try:
            if predicate.name == "spatial":
                if spatial_evidence is None:
                    records.append(FilterExecution(index, predicate.name, "LOCAL", "NOT_EVALUATED",
                                                   ("SPATIAL_ADAPTATION_FAILED", *(spatial_error or ()))))
                    continue
                check = evaluate_spatial(plan, spatial_evidence)
                outcome = {"INSIDE": "MATCH", "OUTSIDE": "NO_MATCH",
                           "NOT_EVALUATED": "NOT_EVALUATED"}[check.status]
                reasons = check.reasons
                if (plan.beam_decision_ref is None and context.reference.source == "ARCHIVE"
                        and check.status == "OUTSIDE"):
                    # A bound complete server query reported intersection. Do not
                    # turn disagreeing local interpretation into a definite exclusion.
                    outcome = "NOT_EVALUATED"
                    reasons += ("SERVER_LOCAL_SPATIAL_DISAGREEMENT",)
                records.append(FilterExecution(index, predicate.name, "LOCAL", outcome,
                                               reasons, spatial=check))
            elif predicate.name == "retrieval_scope":
                records.append(FilterExecution(index, predicate.name, "SERVER", "MATCH",
                                               ("BOUND_QUERY_REPORTED_CENTER_IN_SCOPE",)))
            elif predicate.name == "science_only" and predicate.action == "PLANNED_SERVER":
                value = context.evidence.prepared.normalized_metadata.science_observation.value
                records.append(FilterExecution(
                    index, predicate.name, "SERVER",
                    "MATCH" if value is True else "NOT_EVALUATED",
                    ("SERVER_REPORTED_MATCH",) if value is True
                    else ("SERVER_LOCAL_SCIENCE_UNVERIFIED_OR_INCONSISTENT",),
                ))
            elif predicate.name == "angular_resolution":
                check = evaluate_angular_filter(plan, context, index)
                records.append(FilterExecution(index, predicate.name, "LOCAL", check.status,
                                               check.reasons, scalar=check))
            else:
                records.append(FilterExecution(index, predicate.name, "NONE", "NOT_EVALUATED",
                                               ("FILTER_NOT_IMPLEMENTED",)))
        except Exception as exc:
            records.append(FilterExecution(index, predicate.name, "LOCAL", "NOT_EVALUATED",
                                           ("FILTER_EXECUTION_FAILED", type(exc).__name__, str(exc))))
    disposition = (
        D.EXCLUDED if any(r.outcome == "NO_MATCH" for r in records)
        else D.RETAINED_UNEVALUATED if any(r.outcome in {"NOT_EVALUATED", "SKIPPED"} for r in records)
        else D.MATCHED_FILTERS
    )
    return CandidateRecord(context, disposition, tuple(records), spatial_evidence)


def _run_source(plan, name, *, archive_client, queue_loader, supplied, interpretations):
    source_plan = plan.for_source(name)
    if source_plan is None:
        return SourceSearchExecution(name, S.NOT_SELECTED, "NONE", None)
    mode = "CLIENT" if name == "ARCHIVE" and archive_client is not None else "SUPPLIED_RESULT"
    if name == "QUEUE" and queue_loader is not None:
        mode = "LOADER"
    result = supplied
    binding = None
    comparison = None
    stage = "ACQUIRE"
    try:
        if name == "ARCHIVE" and archive_client is not None:
            assert source_plan.archive_query is not None
            result = archive_client.search(source_plan.archive_query)
        if name == "QUEUE" and queue_loader is not None:
            result = queue_loader()
        if result is None:
            if mode in {"CLIENT", "LOADER"}:
                raise TypeError("Source provider returned None instead of a result")
            return SourceSearchExecution(name, S.NOT_PROVIDED, mode, source_plan,
                                         reasons=("SELECTED_SOURCE_INPUT_MISSING",))
        if name == "ARCHIVE":
            if not isinstance(result, ArchiveQueryResult):
                raise TypeError("Archive search must return ArchiveQueryResult")
            stage = "BIND"
            binding = bind_archive_query(plan, result)
            if binding.status != "MATCHED":
                return SourceSearchExecution(name, S.FAILED, mode, source_plan, result,
                                             query_binding=binding, reasons=("QUERY_BINDING_FAILED", *binding.reasons))
        elif not isinstance(result, QueueCsvParseResult):
            raise TypeError("Queue input must be QueueCsvParseResult")
        stage = "CONSTRUCT"
        comparison = build_archive_contexts(result) if name == "ARCHIVE" else build_queue_contexts(result)
        if comparison.status is not SourceStatus.COMPLETE:
            status = S.INCOMPLETE if comparison.status is SourceStatus.INCOMPLETE else S.FAILED
            return SourceSearchExecution(name, status, mode, source_plan, result, comparison,
                                         binding, reasons=comparison.reasons)
        stage = "FILTER"
        rows = tuple(_evaluate_row(plan, context, result, interpretations)
                     for context in sorted(comparison.contexts, key=lambda c: c.context_id))
        server = tuple(i for i, p in enumerate(source_plan.predicates)
                       if p.action == "PLANNED_SERVER") if name == "ARCHIVE" else ()
        return SourceSearchExecution(name, S.COMPLETED, mode, source_plan, result, comparison,
                                     binding, rows, server, source_plan.limitations)
    except Exception as exc:
        # Failure isolation is deliberate only at the source execution boundary.
        # KeyboardInterrupt/SystemExit are not caught.
        record = result if isinstance(result, (ArchiveQueryResult, QueueCsvParseResult)) else None
        return SourceSearchExecution(name, S.FAILED, mode, source_plan, record, comparison, binding,
                                     reasons=(f"{stage}_FAILED", type(exc).__name__, str(exc)))


def search_candidates(
    validation: RequestValidationResult,
    *,
    archive_client: ArchiveSearcher | None = None,
    archive_result: ArchiveQueryResult | None = None,
    queue_result: QueueCsvParseResult | None = None,
    queue_loader: Callable[[], QueueCsvParseResult] | None = None,
    interpretations: Iterable[PositionInterpretation] = (),
    archive_science_only: bool = False,
    beam_decision_ref: str | None = None,
) -> CandidateSearchResult:
    """Execute a bounded plan, retaining all row decisions before display limits.

    ArchiveClient is injected explicitly; no default network client is created.
    Queue accepts a parsed snapshot or a loader (e.g. QueueCsvClient.load wrapped
    with its path). Store acquisition/run binding remains the caller's
    responsibility. Conflicting provider/result inputs are errors.
    """
    if archive_client is not None and archive_result is not None:
        raise ValueError("Supply Archive client or result, not both")
    if queue_loader is not None and queue_result is not None:
        raise ValueError("Supply Queue loader or result, not both")
    interpretation_map = {}
    for item in interpretations:
        if not isinstance(item, PositionInterpretation):
            raise TypeError("Expected PositionInterpretation")
        if item.context_id in interpretation_map:
            raise ValueError("Duplicate context interpretation")
        interpretation_map[item.context_id] = item
    # Invalid requests fail before any client is called.
    plan = build_search_plan(validation, archive_science_only=archive_science_only,
                             beam_decision_ref=beam_decision_ref)
    started = datetime.now(UTC)
    results = {
        name: _run_source(plan, name, archive_client=archive_client, queue_loader=queue_loader,
                          supplied=archive_result if name == "ARCHIVE" else queue_result,
                          interpretations=interpretation_map)
        for name in ("ARCHIVE", "QUEUE")
    }
    # Deterministic display order: requested source order, then context ID.
    retained = tuple(row for source in plan.sources for row in results[source.source].retained_rows)
    shown = retained if plan.result_limit is None else retained[:plan.result_limit]
    shown_ids = {row.context.context_id for row in shown}
    for name, result in results.items():
        omitted = tuple(r.context.context_id for r in result.retained_rows
                        if r.context.context_id not in shown_ids)
        results[name] = replace(result, omitted_candidate_ids=omitted)
    known_ids = {row.context.context_id for result in results.values() for row in result.rows}
    unused = tuple(sorted(set(interpretation_map) - known_ids))
    return CandidateSearchResult(plan, results["ARCHIVE"], results["QUEUE"], shown, len(retained),
                                 started, datetime.now(UTC), unused)
