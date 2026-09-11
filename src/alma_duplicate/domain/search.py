"""Offline search plans: planned operations are not execution records."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from alma_duplicate.clients.archive_queries import ArchiveQuerySpec
from alma_duplicate.domain.proposed_observation import CandidatePredicate, RequestValidationResult


class PredicateAction(StrEnum):
    PLANNED_SERVER = "PLANNED_SERVER"
    PLANNED_LOCAL = "PLANNED_LOCAL"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class PlannedPredicate:
    name: str
    action: PredicateAction
    source_field: str | None
    requested: CandidatePredicate | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SourceSearchPlan:
    source: str
    predicates: tuple[PlannedPredicate, ...]
    spatial_operation: str
    limitations: tuple[str, ...]
    archive_query: ArchiveQuerySpec | None = None


@dataclass(frozen=True, slots=True)
class SearchPlan:
    validation: RequestValidationResult
    sources: tuple[SourceSearchPlan, ...]
    result_limit: int | None
    version: str = "1"
    execution: str = "NOT_EXECUTED"
    beam_decision_ref: str | None = None
    retrieval_radius_deg: float | None = None
    # Opt-in Archive scalar filter semantics, e.g. "AQ_EQUIVALENT_1"; None = skipped.
    archive_filter_semantics: str | None = None

    def for_source(self, name: str) -> SourceSearchPlan | None:
        return next((s for s in self.sources if s.source == name), None)


@dataclass(frozen=True, slots=True)
class QueryPlanBinding:
    status: str  # MATCHED, MISMATCH, SOURCE_NOT_SELECTED
    query_run_id: str
    reasons: tuple[str, ...]
    version: str = "1"


@dataclass(frozen=True, slots=True)
class ScalarSelection:
    context_id: str
    status: str  # MATCH, NO_MATCH, NOT_EVALUATED
    value: float | None
    unit: str | None
    reasons: tuple[str, ...]
    method_version: str = "1"
    assessment: str = "NOT_EVALUATED"
