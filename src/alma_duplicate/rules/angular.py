"""ANGULAR criterion: angular resolutions differ by a factor of at most two.

Appendix A, "Angular Resolution": "The proposed angular resolution differs by a
factor of <=2 from the other observation." The factor is symmetric
(max/min <= 2) and the boundary is inclusive.

Candidate evidence: Archive ``spatial_resolution`` (canonical arcsec; the week 1
feedback selected it over ``s_resolution`` for angular filtering) and Queue
``Req. Ang. Res.``. Archive values are estimates and Queue values are requests;
both semantics are recorded. The method is PROVISIONAL until the field mapping
is confirmed in writing.
"""
from __future__ import annotations

import math

from alma_duplicate.domain.comparison import (
    ArchiveContextEvidence, ComparisonContext, QueueContextEvidence,
)
from alma_duplicate.domain.proposed_observation import ProposedObservationRequest
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionOutcome as O, CriterionResult, CriterionValue,
    EvidenceSide, MethodApproval, CriterionIssue, EvaluationStatus as E, MethodApplicability as A,
)

from alma_duplicate.rules.numeric import symmetric_factor, positive_canonical

CRITERION_ID = "ANGULAR"
METHOD_VERSION = "angular_factor_2"
POLICY_REF = f"{POLICY_DOCUMENT}, Angular Resolution"
MAX_FACTOR = 2.0
DECISION_REFS = ("weekly-report-week1-Q4:spatial_resolution-for-angular-resolution",)


def _usable(value) -> bool:
    return (value is not None and not isinstance(value, bool)
            and isinstance(value, (int, float)) and math.isfinite(value) and value > 0)


def _candidate_value(context: ComparisonContext) -> tuple[CriterionValue, str | None]:
    evidence = context.evidence
    if isinstance(evidence, ArchiveContextEvidence):
        quantity = evidence.prepared.comparison_evidence.angular_resolution.quantity
        value = quantity.canonical_value
        problem = None if quantity.is_available else quantity.status.value
        return (CriterionValue(value, quantity.canonical_unit, "spatial_resolution",
                               "ARCHIVE_ESTIMATED_ROBUST_0.5"), problem)
    if isinstance(evidence, QueueContextEvidence):
        quantity = evidence.row.request.requested_angular_resolution_arcsec
        problem = None if quantity.canonical_unit == "arcsec" else "QUEUE_UNIT_NOT_ARCSEC"
        return CriterionValue(quantity.value, quantity.canonical_unit, "Req. Ang. Res.",
                              "QUEUE_REQUESTED"), problem
    raise TypeError("Unsupported comparison context")


def evaluate_angular_resolution(
    request: ProposedObservationRequest, context: ComparisonContext,
) -> CriterionResult:
    """Evaluate ANGULAR for one proposed request and one coherent candidate context."""
    proposed_q = request.angular_resolution
    proposed = None
    if proposed_q is not None:
        proposed = CriterionValue(proposed_q.value, proposed_q.unit, "angular_resolution",
                                  "PROPOSED_REQUESTED")
    candidate, candidate_problem = _candidate_value(context)

    issues = []
    for side, value, problem, path in (
        (EvidenceSide.PROPOSED, proposed, None, "request.angular_resolution"),
        (EvidenceSide.CANDIDATE, candidate, candidate_problem, "context.angular_resolution"),
    ):
        if problem == "INVALID_VALUE":
            code = "INVALID_EVIDENCE"
        elif problem in ("INCOMPATIBLE_SOURCE_UNIT", "QUEUE_UNIT_NOT_ARCSEC"):
            code = "INCOMPATIBLE_UNIT"
        elif value is None or value.value is None:
            code = "MISSING_EVIDENCE"
        elif not _usable(value.value):
            code = "INVALID_EVIDENCE"
        elif value.unit != "arcsec":
            code = "INCOMPATIBLE_UNIT"
        elif problem:
            code = "UNUSABLE_EVIDENCE"
        else:
            continue
        issues.append(CriterionIssue(side, code, path, problem or "Angular resolution is unavailable"))

    def result(outcome, reasons, *, derived=(), details=()):
        return CriterionResult(
            criterion_id=CRITERION_ID, policy_ref=POLICY_REF, method_version=METHOD_VERSION,
            approval=MethodApproval.PROVISIONAL,
            applicability=A.UNRESOLVED if issues else A.APPLICABLE,
            evaluation=E.INSUFFICIENT_INFORMATION if issues else E.EVALUATED,
            outcome=outcome, context_id=context.context_id, proposed=proposed, candidate=candidate,
            derived=derived, reasons=tuple(reasons), issues=tuple(issues),
            decision_refs=DECISION_REFS, details=details,
        )

    if issues:
        return result(None, tuple(f"{i.side.value}_ANGULAR_RESOLUTION_UNAVAILABLE" for i in issues))
    exact = symmetric_factor(proposed.value, candidate.value)
    limit = positive_canonical(MAX_FACTOR)
    try:
        ratio = float(exact)
    except OverflowError:
        ratio = None
    derived = (("factor", ratio), ("max_factor", MAX_FACTOR))
    details = (("factor_exact", str(exact)),)
    if exact == limit:
        return result(O.SATISFIED, ("FACTOR_AT_INCLUSIVE_BOUNDARY",), derived=derived, details=details)
    if exact < limit:
        return result(O.SATISFIED, ("FACTOR_WITHIN_LIMIT",), derived=derived, details=details)
    return result(O.NOT_SATISFIED, ("FACTOR_EXCEEDS_LIMIT",), derived=derived, details=details)
