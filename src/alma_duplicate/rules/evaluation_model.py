"""Per-context rule execution reports; no cross-criterion aggregation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from alma_duplicate.domain.candidate_search import CandidateRecord, CandidateSearchResult
from alma_duplicate.rules.model import CriterionResult


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextEvaluation:
    candidate: CandidateRecord
    criteria: tuple[CriterionResult, ...]

    def __post_init__(self):
        if any(r.context_id != self.candidate.context.context_id for r in self.criteria):
            raise ValueError("Criterion result belongs to a different candidate context")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationReport:
    search_result: CandidateSearchResult
    request_criteria: tuple[CriterionResult, ...]
    context_evaluations: tuple[ContextEvaluation, ...]
    evaluation_version: str = field(default="1", init=False)
    execution: Literal["FINISHED"] = field(default="FINISHED", init=False)
    assessment: Literal["NOT_AGGREGATED"] = field(default="NOT_AGGREGATED", init=False)
