"""Criterion-level results for Appendix A rules; never an overall verdict.

A criterion result records one policy condition for one proposed request and
(when the criterion compares observations) one coherent candidate context. It
keeps the values, units, method version, approval status and reasons needed to
explain the outcome. Missing or unusable evidence yields
INSUFFICIENT_INFORMATION, never NOT_SATISFIED.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

POLICY_DOCUMENT = "ALMA Cycle 13 Users' Policies, Doc. 13.16 v1.0 (March 2026), Appendix A"


class CriterionOutcome(StrEnum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class MethodApproval(StrEnum):
    # Implemented from the policy text and reported feedback; written
    # supervisor confirmation of the method is still pending.
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
class CriterionResult:
    criterion_id: str
    policy_ref: str
    method_version: str
    approval: MethodApproval
    outcome: CriterionOutcome
    context_id: str | None
    proposed: CriterionValue | None
    candidate: CriterionValue | None
    derived: tuple[tuple[str, float], ...]
    reasons: tuple[str, ...]
    missing_side: EvidenceSide | None = None
    decision_refs: tuple[str, ...] = ()
    # Per-item explanation, e.g. one entry per proposed window.
    details: tuple[tuple[str, str], ...] = ()

    @property
    def is_definite(self) -> bool:
        return self.outcome in {CriterionOutcome.SATISFIED, CriterionOutcome.NOT_SATISFIED}
