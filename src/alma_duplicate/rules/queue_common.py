"""Project-adopted Queue common rules; retrieval and old methods stay unchanged."""

from dataclasses import dataclass, replace

from alma_duplicate.domain.comparison import QueueContextEvidence
from alma_duplicate.domain.queue import QueueMosaicKind, RegularSpwEvidence
from alma_duplicate.domain.spatial import SkyPosition, SpatialStatus
from alma_duplicate.primary_beam import primary_beam_fwhm_deg
from alma_duplicate.queue_position import (
    adapt_queue_position,
    candidate_frequency,
    PROFILE,
    SOURCE_REF,
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

DECISION_REF = "docs/evidence/queue_common_decision_2026-09-24.md#common-rules"


@dataclass(frozen=True)
class QueueArrayDeclaration:
    """Explicit owner interpretation, bound to a snapshot-qualified raw row ID."""

    source_row_id: str
    array: str
    decision_ref: str

    def __post_init__(self):
        if self.array not in {"7M_ONLY", "TP_ONLY"}:
            raise ValueError("Array declaration must be 7M_ONLY or TP_ONLY")
        if not self.source_row_id.strip() or not self.decision_ref.strip():
            raise ValueError("Array declaration requires row ID and decision reference")


def evaluate_queue_common(request, context, spatial_evidence, *, array_declaration=None):
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
    diameter, array_scope = None, "UNRESOLVED"
    diameter_source = "Use 7-m?/Use TP? with optional explicit row declaration"
    diameter_notes = ()
    flags = (row.request.use_7m, row.request.use_tp)
    if array_declaration is not None:
        if array_declaration.source_row_id != row.raw_row.row_id.value:
            raise ValueError("Array declaration belongs to another source row")
    if any(type(flag) is not bool for flag in flags):
        issue("QUEUE_ARRAY_FLAGS_UNRESOLVED", "context.request.arrays")
    elif flags == (True, True):
        issue("MIXED_7M_TP_UNSUPPORTED", "context.request.arrays")
    elif array_declaration is not None:
        expected = (True, False) if array_declaration.array == "7M_ONLY" else (False, True)
        if flags != expected:
            issue("ARRAY_DECLARATION_CONFLICTS_WITH_FLAGS", "context.request.arrays")
        else:
            diameter = 7.0 if array_declaration.array == "7M_ONLY" else 12.0
            array_scope = array_declaration.array
            diameter_source = "EXPLICIT_ROW_ARRAY_DECLARATION_NOT_CSV_ONLY_INFERENCE"
    elif flags == (False, False):
        diameter, array_scope = 12.0, "MAIN_12M_FROM_EXPLICIT_NEGATIVE_AUXILIARY_FLAGS"
    else:
        issue("EXCLUSIVE_ARRAY_DECLARATION_REQUIRED", "context.request.arrays")
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
            or old.antenna_diameter_m not in (None, diameter)
        ):
            issue(
                "CONFLICTING_POSITION_INTERPRETATION", "context.spatial.interpretation"
            )
        # Reuse source binding, offset transport and placeholder checks.
        evidence = adapt_queue_position(context, spatial_evidence.source_record)
        # Lift only the legacy TP selection gate for an explicitly declared TP
        # row. Preserve all geometry, frame, placeholder and offset-domain gates.
        if (
            array_scope == "TP_ONLY"
            and evidence.center_status is SpatialStatus.AVAILABLE
            and evidence.center is not None
            and row.spatial.mosaic_kind is QueueMosaicKind.SINGLE_FIELD
            and isinstance(row.spectral, RegularSpwEvidence)
            and row.spatial.coordinate_system_raw.strip().lower()
            in ("", "icrs", "j2000", "galactic")
            and "QUEUE_OFFSET_OUTSIDE_LOCAL_DOMAIN" not in evidence.reasons
        ):
            evidence = replace(
                evidence, selection_status=SpatialStatus.AVAILABLE,
                reasons=tuple(r for r in evidence.reasons if r != "TP_GEOMETRY_UNSUPPORTED"),
            )
        if diameter is not None:
            evidence = replace(
                evidence,
                interpretation=replace(evidence.interpretation, antenna_diameter_m=diameter),
                reasons=tuple(r for r in evidence.reasons
                              if r != "QUEUE_ARRAY_COMBINATION_UNRESOLVED"),
            )
        if (
            evidence.center_status is not SpatialStatus.AVAILABLE
            or evidence.center is None
        ):
            issue("QUEUE_CENTER_OR_FIXED_TARGET_UNRESOLVED", "context.spatial.center")
        if evidence.selection_status is not SpatialStatus.AVAILABLE:
            issue("QUEUE_POSITION_SCOPE_UNRESOLVED", "context.spatial.selection_status")
    details = (
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
        ("array_scope", array_scope),
        ("array_declaration_ref", None if array_declaration is None else array_declaration.decision_ref),
    )
    # ANGULAR has its own missing-value/unit diagnostics. Beam frequency is not
    # its dependency; a missing candidate beam must not erase a valid ratio.
    angular = evaluate_angular_resolution(request, context)
    angular = replace(
        angular,
        method_version="queue_angular_factor_4",
        approval=MethodApproval.APPROVED,
        decision_refs=angular.decision_refs + (DECISION_REF,) + (() if array_declaration is None else (array_declaration.decision_ref,)),
        details=angular.details + details,
    )
    if issues:
        angular = replace(
            angular,
            outcome=None,
            applicability=A.UNRESOLVED,
            evaluation=E.INSUFFICIENT_INFORMATION,
            issues=angular.issues + tuple(issues),
            reasons=(() if angular.outcome is not None else angular.reasons)
            + tuple(i.code for i in issues),
        )
    position_issues = list(issues)
    frequency, frequency_source, frequency_notes = candidate_frequency(row)
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
        method_version="queue_pos_single_3",
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
            ("diameter_source", diameter_source),
            ("frequency_role", "POSITION_ONLY_NOT_CONT_FREQ"),
        ),
        issues=tuple(position_issues),
        decision_refs=(DECISION_REF, SOURCE_REF) + (() if array_declaration is None else (array_declaration.decision_ref,)),
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
