"""Adapt the project s_region position policy to shared duplication criteria."""

from alma_duplicate.mosaic_region_position import assess_region_position
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT,
    CriterionResult,
    CriterionOutcome as O,
    EvaluationStatus as E,
    MethodApplicability as A,
    MethodApproval,
    CriterionIssue,
    EvidenceSide,
)


def evaluate_region_position(proposed, context, *, boundary_arcsec=0.001):
    region = context.evidence.prepared.raw_row.get("s_region")
    coverage = assess_region_position(
        proposed,
        region,
        candidate_id=context.context_id,
        boundary_arcsec=boundary_arcsec,
    )
    state = coverage["outcome"]
    outcome = None if state == "UNKNOWN" else O(state)
    reasons = tuple(coverage["reasons"]) or (
        "STRICT_MAJORITY_WITHIN_ARCHIVE_S_REGION"
        if outcome == O.SATISFIED
        else "NO_STRICT_MAJORITY_WITHIN_ARCHIVE_S_REGION",
    )
    criterion = CriterionResult(
        criterion_id="POS-MOSAIC",
        policy_ref=f"{POLICY_DOCUMENT}, Position",
        method_version="archive_pos_mosaic_s_region_1",
        approval=MethodApproval.APPROVED,
        applicability=A.APPLICABLE if outcome else A.UNRESOLVED,
        evaluation=E.EVALUATED if outcome else E.INSUFFICIENT_INFORMATION,
        outcome=outcome,
        context_id=context.context_id,
        proposed=None,
        candidate=None,
        derived=tuple(
            (k, coverage[k])
            for k in (
                "pointing_count",
                "inside_count",
                "outside_count",
                "boundary_count",
                "unknown_count",
                "covered_fraction_lower",
                "covered_fraction_upper",
            )
        ),
        reasons=reasons,
        decision_refs=("docs/mosaic_s_region_position.md",),
        issues=()
        if outcome
        else tuple(
            CriterionIssue(
                EvidenceSide.PROPOSED
                if r.startswith("PROPOSED_")
                else EvidenceSide.CANDIDATE,
                r,
                "mosaic.position",
                r,
            )
            for r in reasons
        ),
        details=(
            ("coverage_source", "ARCHIVE_S_REGION"),
            ("s_region_sha256", coverage["s_region_sha256"]),
        ),
        numeric_method="SPHERICAL_REGION_BOUNDARY_BAND_INTEGER_MAJORITY",
    )
    return criterion, coverage
