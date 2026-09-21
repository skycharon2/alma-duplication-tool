"""Per-context criteria and branch results; no search-wide absence assessment."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from alma_duplicate.domain.candidate_search import CandidateRecord, CandidateSearchResult
from alma_duplicate.rules.model import CriterionResult
from alma_duplicate.rules.aggregation import BranchAssessment


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextEvaluation:
    candidate: CandidateRecord
    criteria: tuple[CriterionResult, ...]
    branches: tuple[BranchAssessment, ...] = ()

    def __post_init__(self):
        if any(b.context_id != self.candidate.context.context_id for b in self.branches):
            raise ValueError("Branch belongs to a different candidate context")
        if any(r.context_id != self.candidate.context.context_id for r in self.criteria):
            raise ValueError("Criterion result belongs to a different candidate context")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationReport:
    search_result: CandidateSearchResult
    request_criteria: tuple[CriterionResult, ...]
    context_evaluations: tuple[ContextEvaluation, ...]
    evaluation_version: str = field(default="3", init=False)
    execution: Literal["FINISHED"] = field(default="FINISHED", init=False)
    assessment: Literal["NOT_AGGREGATED"] = field(default="NOT_AGGREGATED", init=False)
