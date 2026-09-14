"""Criterion result schema 2: computation, outcome and method gates are separate."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

from alma_duplicate.rules.numeric import NUMERIC_METHOD

POLICY_DOCUMENT = "ALMA Cycle 13 Users' Policies, Doc. 13.16 v1.0 (March 2026), Appendix A"


class CriterionOutcome(StrEnum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"


class EvaluationStatus(StrEnum):
    EVALUATED = "EVALUATED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class MethodApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MethodApproval(StrEnum):
    PROVISIONAL = "PROVISIONAL"
    APPROVED = "APPROVED"


class EvidenceSide(StrEnum):
    PROPOSED = "PROPOSED"
    CANDIDATE = "CANDIDATE"
    METHOD = "METHOD"


@dataclass(frozen=True, slots=True)
class CriterionValue:
    value: float | None
    unit: str | None
    source_field: str
    semantics: str


@dataclass(frozen=True, slots=True)
class CriterionIssue:
    side: EvidenceSide
    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CriterionResult:
    criterion_id: str
    policy_ref: str
    method_version: str
    approval: MethodApproval
    applicability: MethodApplicability
    evaluation: EvaluationStatus
    outcome: CriterionOutcome | None
    context_id: str | None
    proposed: CriterionValue | None
    candidate: CriterionValue | None
    derived: tuple[tuple[str, float | None], ...] = ()
    reasons: tuple[str, ...] = ()
    issues: tuple[CriterionIssue, ...] = ()
    decision_refs: tuple[str, ...] = ()
    details: tuple[tuple[str, str], ...] = ()
    result_version: str = "2"
    numeric_method: str = NUMERIC_METHOD

    def __post_init__(self):
        for value, enum in ((self.evaluation, EvaluationStatus),
                            (self.approval, MethodApproval),
                            (self.applicability, MethodApplicability)):
            if not isinstance(value, enum):
                raise TypeError(f"Expected {enum.__name__}")
        if self.outcome is not None and not isinstance(self.outcome, CriterionOutcome):
            raise TypeError("Expected CriterionOutcome or None")
        if (self.evaluation is EvaluationStatus.EVALUATED) != (self.outcome is not None):
            raise ValueError("Only evaluated results have a condition outcome")
        if self.outcome is not None and self.applicability is not MethodApplicability.APPLICABLE:
            raise ValueError("A condition outcome requires an applicable method")
        if (self.evaluation is EvaluationStatus.NOT_APPLICABLE
                and self.applicability is not MethodApplicability.NOT_APPLICABLE):
            raise ValueError("NOT_APPLICABLE requires an explicit method-scope exclusion")
        if self.approval is MethodApproval.APPROVED and (
                not self.decision_refs or any(not isinstance(ref, str) or not ref.strip()
                                              for ref in self.decision_refs)):
            raise ValueError("Approved methods require a decision reference")

    @property
    def has_computed_outcome(self) -> bool:
        return self.evaluation is EvaluationStatus.EVALUATED and self.outcome is not None

    @property
    def eligible_for_formal_aggregation(self) -> bool:
        """Necessary per-criterion gate, not a complete search/branch verdict."""
        return (self.has_computed_outcome
                and self.applicability is MethodApplicability.APPLICABLE
                and self.approval is MethodApproval.APPROVED)

    @property
    def issue_sides(self) -> tuple[EvidenceSide, ...]:
        return tuple(dict.fromkeys(issue.side for issue in self.issues))
