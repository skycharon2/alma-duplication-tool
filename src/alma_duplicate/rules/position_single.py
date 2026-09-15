"""Provisional Queue candidate-side single-field coverage; see docs/pos_single.md."""
from alma_duplicate.queue_position import (
    candidate_coverage, PROFILE, SOURCE_REF, BOUNDARY_TOLERANCE_DEG,
)
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionOutcome as O,
    MethodApproval, MethodApplicability as A, EvaluationStatus as E,
)

METHOD_VERSION = "queue_pos_single_1"


def evaluate_position_single(request, context, spatial_evidence):
    """Consume typed position evidence, never search filter outcomes or raw CSV."""
    reasons = ()
    coverage = None
    if request.target_kind != "FIXED" or request.geometry != "SINGLE_POINTING" or request.position is None:
        reasons = ("PROPOSED_FIXED_SINGLE_POINT_POSITION_REQUIRED",)
    elif context.reference.source != "QUEUE":
        reasons = ("POS_SINGLE_SOURCE_UNSUPPORTED",)
    elif spatial_evidence is None or spatial_evidence.adapter_version != PROFILE:
        reasons = ("QUEUE_CANDIDATE_POSITION_PROFILE_REQUIRED",)
    else:
        if spatial_evidence.context.context_id != context.context_id:
            raise ValueError("Position evidence belongs to a different context")
        coverage = candidate_coverage(request, spatial_evidence)
        reasons = coverage.reasons
    evaluated = coverage is not None and not coverage.blockers
    outcome = None
    if evaluated:
        outcome = O.SATISFIED if coverage.separation_deg < coverage.radius_deg else O.NOT_SATISFIED
    return CriterionResult(
        criterion_id="POS-SINGLE", policy_ref=f"{POLICY_DOCUMENT}, Position",
        method_version=METHOD_VERSION, approval=MethodApproval.PROVISIONAL,
        applicability=A.APPLICABLE if evaluated else A.UNRESOLVED,
        evaluation=E.EVALUATED if evaluated else E.INSUFFICIENT_INFORMATION,
        outcome=outcome, context_id=context.context_id, proposed=None, candidate=None,
        derived=(() if coverage is None else (
            ("separation_deg", coverage.separation_deg), ("candidate_radius_deg", coverage.radius_deg),
            ("candidate_frequency_ghz", coverage.frequency_ghz),
            ("antenna_diameter_m", coverage.diameter_m),
            ("boundary_tolerance_deg", BOUNDARY_TOLERANCE_DEG))),
        reasons=reasons, decision_refs=(SOURCE_REF, "docs/pos_single.md"),
        details=(() if coverage is None else (
            ("position_profile", PROFILE), ("frequency_source", coverage.frequency_source),
            ("diameter_source", coverage.diameter_source))),
        numeric_method="SPHERICAL_SEPARATION_FLOAT64_BOUNDARY_1E-10_DEG",
    )
