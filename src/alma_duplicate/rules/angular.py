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
    EvidenceSide, MethodApproval,
)

CRITERION_ID = "ANGULAR"
METHOD_VERSION = "angular_factor_1"
POLICY_REF = f"{POLICY_DOCUMENT}, Angular Resolution"
MAX_FACTOR = 2.0
# Relative band treated as the inclusive policy boundary (floating-point noise only).
BOUNDARY_RELATIVE_TOLERANCE = 1e-9
DECISION_REFS = ("weekly-report-week1-Q4:spatial_resolution-for-angular-resolution",)


def _usable(value) -> bool:
    return (value is not None and not isinstance(value, bool)
            and isinstance(value, (int, float)) and math.isfinite(value) and value > 0)


def _candidate_value(context: ComparisonContext) -> tuple[CriterionValue, str | None]:
    evidence = context.evidence
    if isinstance(evidence, ArchiveContextEvidence):
        quantity = evidence.prepared.comparison_evidence.angular_resolution.quantity
        value = quantity.canonical_value if quantity.is_available else None
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

    def result(outcome, reasons, *, derived=(), side=None):
        return CriterionResult(CRITERION_ID, POLICY_REF, METHOD_VERSION, MethodApproval.PROVISIONAL,
                               outcome, context.context_id, proposed, candidate, derived,
                               tuple(reasons), side, DECISION_REFS)

    if proposed is None or not _usable(proposed.value) or proposed.unit != "arcsec":
        return result(O.INSUFFICIENT_INFORMATION, ("PROPOSED_ANGULAR_RESOLUTION_UNAVAILABLE",),
                      side=EvidenceSide.PROPOSED)
    if candidate_problem or not _usable(candidate.value) or candidate.unit != "arcsec":
        return result(O.INSUFFICIENT_INFORMATION,
                      ("CANDIDATE_ANGULAR_RESOLUTION_UNAVAILABLE", *filter(None, (candidate_problem,))),
                      side=EvidenceSide.CANDIDATE)
    ratio = max(proposed.value, candidate.value) / min(proposed.value, candidate.value)
    derived = (("factor", ratio), ("max_factor", MAX_FACTOR))
    if abs(ratio - MAX_FACTOR) <= BOUNDARY_RELATIVE_TOLERANCE * MAX_FACTOR:
        return result(O.SATISFIED, ("FACTOR_AT_INCLUSIVE_BOUNDARY",), derived=derived)
    if ratio < MAX_FACTOR:
        return result(O.SATISFIED, ("FACTOR_WITHIN_LIMIT",), derived=derived)
    return result(O.NOT_SATISFIED, ("FACTOR_EXCEEDS_LIMIT",), derived=derived)
