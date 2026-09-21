"""Dispatch confirmed Archive and provisional Queue single-field position methods."""
from alma_duplicate.domain.spatial import SpatialStatus as S
from alma_duplicate.primary_beam import BOUNDARY_TOLERANCE_DEG, covers
from alma_duplicate.queue_position import candidate_coverage, PROFILE, SOURCE_REF
from alma_duplicate.rules.model import (
    CriterionIssue, EvidenceSide as Side,
    POLICY_DOCUMENT, CriterionResult, CriterionOutcome as O,
    MethodApproval, MethodApplicability as A, EvaluationStatus as E,
)

METHOD_VERSION = "queue_pos_single_1"


def evaluate_position_single(request, context, spatial_evidence):
    """Consume typed position evidence, never search filter outcomes or raw CSV."""
    if context.reference.source == "ARCHIVE":
        from alma_duplicate.rules.archive_position import evaluate_archive_position
        return evaluate_archive_position(request, context, spatial_evidence)
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
    issues = []
    if not evaluated:
        if coverage is None:
            side, path = Side.METHOD, "position_profile"
            if reasons[0].startswith("PROPOSED_"):
                side = Side.PROPOSED
                path = ("request.target_kind" if request.target_kind != "FIXED" else
                        "request.geometry" if request.geometry != "SINGLE_POINTING" else
                        "request.position")
            issues.append(CriterionIssue(side, reasons[0], path, reasons[0]))
        else:
            # Scope and numeric boundary are method issues; missing source evidence
            # is candidate-side. Informational conventions are not missing fields.
            if "SPATIAL_BOUNDARY_TOLERANCE" in coverage.blockers:
                issues.append(CriterionIssue(Side.METHOD, "SPATIAL_BOUNDARY_TOLERANCE",
                                             "candidate_coverage.boundary", "Boundary outcome unresolved"))
            else:
                if spatial_evidence.center_status is not S.AVAILABLE:
                    issues.append(CriterionIssue(Side.CANDIDATE, "CENTER_UNAVAILABLE",
                                                 "context.spatial.center", "Candidate center unavailable"))
                if spatial_evidence.selection_status is not S.AVAILABLE:
                    issues.append(CriterionIssue(Side.METHOD, "POSITION_SCOPE_UNRESOLVED",
                                                 "context.spatial.selection_status", "Position profile cannot evaluate this geometry"))
                if coverage.frequency_ghz is None:
                    issues.append(CriterionIssue(Side.CANDIDATE, "CANDIDATE_FREQUENCY_UNAVAILABLE",
                                                 "context.spectral.sensitivity.reference_frequency_ghz", "No supported candidate frequency"))
                if coverage.diameter_m is None:
                    issues.append(CriterionIssue(Side.CANDIDATE, "CANDIDATE_DIAMETER_UNAVAILABLE",
                                                 "context.request.use_7m/use_tp", "Array evidence does not resolve diameter"))
    outcome = None
    if evaluated:
        outcome = O.SATISFIED if covers(coverage.separation_deg, coverage.radius_deg) else O.NOT_SATISFIED
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
        reasons=reasons, issues=tuple(issues), decision_refs=(SOURCE_REF, "docs/pos_single.md"),
        details=(() if coverage is None else (
            ("position_profile", PROFILE), ("frequency_source", coverage.frequency_source),
            ("diameter_source", coverage.diameter_source))),
        numeric_method="SPHERICAL_SEPARATION_FLOAT64_BOUNDARY_1E-10_DEG",
    )
