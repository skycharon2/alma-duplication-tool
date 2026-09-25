"""Per-context criteria and branch results; no search-wide absence assessment."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from alma_duplicate.domain.candidate_search import CandidateRecord, CandidateSearchResult
from alma_duplicate.rules.model import CriterionResult
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.rules.aggregation import BranchAssessment
from alma_duplicate.domain.line_pairing import LinePairBuildResult
from alma_duplicate.rules.line import LinePairEvaluation

if TYPE_CHECKING:
    from alma_duplicate.queue_line_pairing import QueueLinePairBuildResult
    from alma_duplicate.rules.queue_line import QueueLinePairEvaluation


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextEvaluation:
    candidate: CandidateRecord
    criteria: tuple[CriterionResult, ...]
    branches: tuple[BranchAssessment, ...] = ()
    line_pairing: LinePairBuildResult | QueueLinePairBuildResult | None = None
    line_pairs: tuple[LinePairEvaluation | QueueLinePairEvaluation, ...] = ()

    def __post_init__(self):
        if ((self.line_pairing is None and self.line_pairs) or
                (self.line_pairing is not None and
                 tuple(p.attempt for p in self.line_pairs) != self.line_pairing.attempts)):
            raise ValueError("Line evaluations must match the prepared attempts in order")
        if self.line_pairing is not None and self.line_pairing.candidate_context_id != self.candidate.context.context_id:
            raise ValueError("Line pairing belongs to another candidate context")
        if any(b.context_id != self.candidate.context.context_id for b in self.branches):
            raise ValueError("Branch belongs to a different candidate context")
        if any(r.context_id != self.candidate.context.context_id for r in self.criteria):
            raise ValueError("Criterion result belongs to a different candidate context")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationReport:
    search_result: CandidateSearchResult
    request_criteria: tuple[CriterionResult, ...]
    context_evaluations: tuple[ContextEvaluation, ...]
    evaluation_version: str = field(default="5", init=False)
    execution: Literal["FINISHED"] = field(default="FINISHED", init=False)
    assessment: Literal["NOT_AGGREGATED"] = field(default="NOT_AGGREGATED", init=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class SolarExemptionReport:
    """Request-level exemption: no candidate search or source coverage claim."""
    validation: "RequestValidationResult"
    evaluation_version: str = field(default="5", init=False)
    execution: Literal["FINISHED"] = field(default="FINISHED", init=False)
    assessment: Literal["NOT_APPLICABLE"] = field(default="NOT_APPLICABLE", init=False)

    def __post_init__(self):
        if (not self.validation.is_valid or self.validation.request is None
                or self.validation.request.target_kind != "SUN"
                or self.validation.search_readiness != "NOT_APPLICABLE"):
            raise ValueError("Solar exemption requires a valid SUN request")
