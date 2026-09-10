"""Execution records for candidate discovery, never duplication verdicts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.domain.comparison import ComparisonContext, ComparisonSourceResult
from alma_duplicate.domain.queue import QueueCsvParseResult
from alma_duplicate.domain.search import QueryPlanBinding, ScalarSelection, SearchPlan, SourceSearchPlan
from alma_duplicate.domain.spatial import SpatialEvidence, SpatialSelection


class SearchSourceStatus(StrEnum):
    NOT_SELECTED = "NOT_SELECTED"
    NOT_PROVIDED = "NOT_PROVIDED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"
    COMPLETED = "COMPLETED"


class CandidateDisposition(StrEnum):
    MATCHED_FILTERS = "MATCHED_FILTERS"
    RETAINED_UNEVALUATED = "RETAINED_UNEVALUATED"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True, slots=True)
class FilterExecution:
    predicate_index: int
    name: str
    stage: str
    outcome: str  # MATCH, NO_MATCH, NOT_EVALUATED, SKIPPED
    reasons: tuple[str, ...] = ()
    spatial: SpatialSelection | None = None
    scalar: ScalarSelection | None = None


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    context: ComparisonContext
    disposition: CandidateDisposition
    filters: tuple[FilterExecution, ...]
    spatial_evidence: SpatialEvidence | None = None

    @property
    def has_unevaluated_filters(self) -> bool:
        return any(f.outcome in {"NOT_EVALUATED", "SKIPPED"} for f in self.filters)


@dataclass(frozen=True, slots=True)
class SourceSearchExecution:
    source: str
    status: SearchSourceStatus
    input_mode: str
    plan: SourceSearchPlan | None
    source_record: ArchiveQueryResult | QueueCsvParseResult | None = None
    comparison: ComparisonSourceResult | None = None
    query_binding: QueryPlanBinding | None = None
    rows: tuple[CandidateRecord, ...] = ()
    # Server predicates reported by a complete, plan-bound Archive retrieval.
    server_predicate_indices: tuple[int, ...] = ()
    reasons: tuple[str, ...] = ()
    omitted_candidate_ids: tuple[str, ...] = ()

    @property
    def retained_rows(self) -> tuple[CandidateRecord, ...]:
        return tuple(r for r in self.rows if r.disposition is not CandidateDisposition.EXCLUDED)

    @property
    def unevaluated_rows(self) -> tuple[CandidateRecord, ...]:
        """Includes excluded rows with another, unresolved condition."""
        return tuple(r for r in self.rows if r.has_unevaluated_filters)

    @property
    def requested_filters_fully_evaluated(self) -> bool:
        # A skipped plan predicate remains skipped even for an empty source result.
        return (
            self.status is SearchSourceStatus.COMPLETED
            and self.plan is not None
            and not any(p.action == "SKIPPED" for p in self.plan.predicates)
            and not self.unevaluated_rows
        )


@dataclass(frozen=True, slots=True)
class CandidateSearchResult:
    plan: SearchPlan
    archive: SourceSearchExecution
    queue: SourceSearchExecution
    candidates: tuple[CandidateRecord, ...]
    total_retained: int
    started_at: datetime
    finished_at: datetime
    unused_interpretation_ids: tuple[str, ...] = ()
    execution: str = "FINISHED"
    assessment: str = "NOT_EVALUATED"
    service_version: str = "1"

    @property
    def truncated(self) -> bool:
        return len(self.candidates) < self.total_retained
