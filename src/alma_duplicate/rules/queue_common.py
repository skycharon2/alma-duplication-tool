"""Project-adopted Queue common rules; retrieval and old methods stay unchanged."""

from dataclasses import replace

from alma_duplicate.domain.comparison import QueueContextEvidence
from alma_duplicate.domain.queue import QueueMosaicKind, RegularSpwEvidence
from alma_duplicate.domain.spatial import SkyPosition, SpatialStatus
from alma_duplicate.primary_beam import primary_beam_fwhm_deg
from alma_duplicate.queue_position import (
    adapt_queue_position,
    candidate_frequency,
    SOURCE_REF,
)
from alma_duplicate.queue_row_beam import (
    resolve_queue_primary_beam_diameter, PROFILE, DECISION_REF as ROW_DECISION_REF,
)
from alma_duplicate.spatial import _separation
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT,
    CriterionResult,
    CriterionIssue,
    CriterionOutcome as O,
    MethodApproval,
    MethodApplicability as A,
    EvaluationStatus as E,
    EvidenceSide as S,
)

DECISION_REF = "docs/evidence/queue_row_continuum_decision_2026-09-24.md"


def queue_common_scope_supported(common):
    return (
        len(common) == 2
        and {r.method_version for r in common}
        == {"queue_angular_factor_7", "queue_pos_single_5"}
        and all(dict(r.details).get("common_scope") == "SUPPORTED" for r in common)
    )


def evaluate_queue_common(request, context, spatial_evidence):
    """Return ANGULAR and POS-SINGLE for one source-bound retained context.

    Selecting this workflow adopts the recorded fixed-celestial Portal position
    interpretation, not inferred source telemetry. Placeholder coordinates block it.
    """
    if not isinstance(context.evidence, QueueContextEvidence):
        raise TypeError("Queue common methods require a Queue context")
    row = context.evidence.row
    issues = []

    def issue(code, path, side=S.CANDIDATE):
        issues.append(CriterionIssue(side, code, path, code))

    if (
        request.target_kind != "FIXED"
        or request.geometry != "SINGLE_POINTING"
        or request.position is None
    ):
        issue("FIXED_SINGLE_POINT_REQUEST_REQUIRED", "request", S.PROPOSED)
    if row.spatial.mosaic_kind is not QueueMosaicKind.SINGLE_FIELD:
        issue("QUEUE_SINGLE_FIELD_REQUIRED", "context.spatial.mosaic_kind")
    if not isinstance(row.spectral, RegularSpwEvidence):
        issue("REGULAR_QUEUE_SETUP_REQUIRED", "context.spectral")
    beam = resolve_queue_primary_beam_diameter(row)
    if beam.diameter_m is None:
        issue("INVALID_STANDALONE_VALUE", "context.raw_row.standAlone_ACA")
    evidence = None
    if spatial_evidence is None:
        issue("QUEUE_SPATIAL_SOURCE_REQUIRED", "context.spatial")
    else:
        if spatial_evidence.context != context:
            raise ValueError("Queue common evidence belongs to another context")
        old = spatial_evidence.interpretation
        if old is not None and (
            old.frame != "ICRS"
            or old.target_kind != "FIXED"
            or old.antenna_diameter_m not in (None, beam.diameter_m)
        ):
            issue(
                "CONFLICTING_POSITION_INTERPRETATION", "context.spatial.interpretation"
            )
        # Reuse source binding, offset transport and placeholder checks.
        evidence = adapt_queue_position(context, spatial_evidence.source_record, row_beam=True)
        if (
            evidence.center_status is not SpatialStatus.AVAILABLE
            or evidence.center is None
        ):
            issue("QUEUE_CENTER_OR_FIXED_TARGET_UNRESOLVED", "context.spatial.center")
        if evidence.selection_status is not SpatialStatus.AVAILABLE:
            issue("QUEUE_POSITION_SCOPE_UNRESOLVED", "context.spatial.selection_status")
    details = (
        ("common_scope", "SUPPORTED" if not issues else "UNRESOLVED"),
        ("source_row_id", row.raw_row.row_id.value),
        ("snapshot_sha256", row.raw_row.row_id.snapshot_sha256),
        ("queue_geometry", row.spatial.mosaic_kind.value),
        ("position_profile", PROFILE),
        (
            "target_interpretation",
            "PROJECT_FIXED_CELESTIAL_WORKFLOW_NOT_SOURCE_TELEMETRY",
        ),
        ("frame_interpretation", "PORTAL_EQUATORIAL_CONVENTION_NOT_MEASURED_FRAME"),
        ("offset_frame_raw", row.spatial.coordinate_system_raw),
        ("array_scope", "ROW_BEAM_NOT_COMPONENT_MEMBERSHIP"),
        ("array_evidence_method", "QUEUE_OPERATIONAL_STANDALONE_OR_PORTAL_FALLBACK_1"),
    ) + beam.details(row)
    # ANGULAR has its own missing-value/unit diagnostics. Beam frequency is not
    # its dependency; a missing candidate beam must not erase a valid ratio.
    angular = evaluate_angular_resolution(request, context)
    angular = replace(
        angular,
        method_version="queue_angular_factor_7",
        approval=MethodApproval.APPROVED,
        decision_refs=angular.decision_refs + (DECISION_REF, ROW_DECISION_REF,),
        details=angular.details + details,
    )
    angular_issues = issues
    if angular_issues:
        angular = replace(
            angular,
            outcome=None,
            applicability=A.UNRESOLVED,
            evaluation=E.INSUFFICIENT_INFORMATION,
            issues=angular.issues + tuple(angular_issues),
            reasons=(() if angular.outcome is not None else angular.reasons)
            + tuple(i.code for i in angular_issues),
        )
    position_issues = list(issues)
    frequency, frequency_source, frequency_notes = candidate_frequency(row)
    diameter, diameter_notes = beam.diameter_m, (beam.source,)
    if frequency is None:
        position_issues.append(
            CriterionIssue(
                S.CANDIDATE,
                "CANDIDATE_FREQUENCY_UNAVAILABLE",
                "context.sensitivity.reference_frequency",
                ";".join(frequency_notes),
            )
        )
    if diameter is None:
        position_issues.append(
            CriterionIssue(
                S.CANDIDATE,
                "CANDIDATE_DIAMETER_UNAVAILABLE",
                "context.request.arrays",
                ";".join(diameter_notes),
            )
        )
    separation, fwhm, radius = None, None, None
    if (
        evidence is not None
        and evidence.center is not None
        and request.position is not None
    ):
        separation = _separation(
            SkyPosition(request.position.ra_deg, request.position.dec_deg, "ICRS"),
            evidence.center,
        )
    if frequency is not None and diameter is not None:
        try:
            fwhm = primary_beam_fwhm_deg(frequency, diameter)
            radius = fwhm / 2
        except ValueError:
            position_issues.append(
                CriterionIssue(
                    S.CANDIDATE,
                    "CANDIDATE_BEAM_UNREPRESENTABLE",
                    "context.sensitivity.reference_frequency",
                    "Candidate beam is outside numeric domain",
                )
            )
    outcome = None
    if not position_issues:
        outcome = O.SATISFIED if separation <= radius else O.NOT_SATISFIED
    center = None if evidence is None else evidence.center
    notes = tuple(
        dict.fromkeys(
            (() if evidence is None else evidence.reasons)
            + frequency_notes
            + diameter_notes
        )
    )
    position = CriterionResult(
        criterion_id="POS-SINGLE",
        policy_ref=f"{POLICY_DOCUMENT}, Position",
        method_version="queue_pos_single_5",
        approval=MethodApproval.APPROVED,
        applicability=A.UNRESOLVED if position_issues else A.APPLICABLE,
        evaluation=E.INSUFFICIENT_INFORMATION if position_issues else E.EVALUATED,
        outcome=outcome,
        context_id=context.context_id,
        proposed=None,
        candidate=None,
        derived=(
            ("separation_deg", separation),
            ("candidate_radius_deg", radius),
            ("candidate_fwhm_deg", fwhm),
            ("candidate_frequency_ghz", frequency),
            ("antenna_diameter_m", diameter),
            ("candidate_ra_deg", None if center is None else center.ra_deg),
            ("candidate_dec_deg", None if center is None else center.dec_deg),
            (
                "proposal_ra_deg",
                None if request.position is None else request.position.ra_deg,
            ),
            (
                "proposal_dec_deg",
                None if request.position is None else request.position.dec_deg,
            ),
        ),
        details=details
        + (
            ("frequency_source", frequency_source),
            ("frequency_role", "POSITION_ONLY_NOT_CONT_FREQ"),
        ),
        issues=tuple(position_issues),
        decision_refs=(ROW_DECISION_REF, SOURCE_REF),
        reasons=tuple(i.code for i in position_issues)
        + notes
        + (
            ()
            if outcome is None
            else (
                "WITHIN_INCLUSIVE_CANDIDATE_BEAM"
                if outcome is O.SATISFIED
                else "OUTSIDE_CANDIDATE_BEAM",
            )
        ),
        numeric_method="SPHERICAL_FLOAT64_INCLUSIVE_NO_EQUALITY_BAND",
    )
    return angular, position
