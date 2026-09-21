"""Confirmed candidate-frequency Archive half-power position criterion."""
from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.domain.spatial import SkyPosition, SpatialStatus, PositionInterpretation
from alma_duplicate.parsers.array_classification import classify_array_type
from alma_duplicate.primary_beam import primary_beam_fwhm_deg
from alma_duplicate.spatial import adapt_spatial, _separation
from alma_duplicate.rules.confirmed import DECISION_REF
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionIssue, CriterionOutcome as O,
    MethodApproval, MethodApplicability as A, EvaluationStatus as E, EvidenceSide as S,
)


def evaluate_archive_position(request, context, spatial_evidence):
    issues = []
    derived = ()
    details = ()
    outcome = None
    solar = request.target_kind == "SUN"
    def issue(code, path, side=S.CANDIDATE):
        issues.append(CriterionIssue(side, code, path, code))
    if request.target_kind != "FIXED" or request.geometry != "SINGLE_POINTING" or request.position is None:
        issue("FIXED_SINGLE_POINT_REQUEST_REQUIRED", "request", S.PROPOSED)
    elif not isinstance(context.evidence, ArchiveContextEvidence):
        issue("ARCHIVE_SOURCE_REQUIRED", "context")
    elif spatial_evidence is None:
        issue("ARCHIVE_POSITION_EVIDENCE_REQUIRED", "context.spatial")
    else:
        if spatial_evidence.context.context_id != context.context_id:
            raise ValueError("Position evidence belongs to a different context")
        # The confirmation defines the fixed celestial ICRS interpretation for this
        # restricted Archive workflow. This is recorded, never inferred from names.
        old = spatial_evidence.interpretation
        if old is not None and (old.frame != "ICRS" or old.target_kind != "FIXED"):
            issue("CONFLICTING_POSITION_INTERPRETATION", "context.spatial.interpretation")
        evidence = adapt_spatial(context, spatial_evidence.source_record, interpretation=
            PositionInterpretation(context.context_id, "ICRS", "FIXED", DECISION_REF))
        if evidence.geometry != "SINGLE_FIELD":
            issue("MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED", "context.is_mosaic")
        if evidence.center_status is not SpatialStatus.AVAILABLE or evidence.center is None:
            issue("CENTER_UNAVAILABLE", "context.s_ra/s_dec")
        array = classify_array_type(context.evidence.prepared.raw_row.get("antenna_arrays"))
        diameter = array.interferometric_diameter_m
        # A majority label is suitable for retrieval, not a unique policy diameter.
        if (array.unrecognized_tokens or len(array.family_counts) > 1
                or diameter is None):
            diameter = None
            issue("UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED", "context.antenna_arrays")
        q = context.evidence.prepared.comparison_evidence.frequency.centre
        if not q.is_available or q.canonical_unit != "GHz":
            issue("CANDIDATE_FREQUENCY_UNAVAILABLE", "context.frequency")
        radius = None
        if q.is_available and q.canonical_unit == "GHz" and diameter is not None:
            try:
                radius = primary_beam_fwhm_deg(q.canonical_value, diameter) / 2
            except ValueError:
                issue("CANDIDATE_BEAM_UNREPRESENTABLE", "context.frequency")
        separation = None if evidence.center is None else _separation(
            SkyPosition(request.position.ra_deg, request.position.dec_deg, "ICRS"), evidence.center)
        derived = (("separation_deg", separation), ("candidate_radius_deg", radius),
                   ("candidate_frequency_ghz", q.canonical_value), ("antenna_diameter_m", diameter))
        details = (("position_interpretation", "CONFIRMED_FIXED_CELESTIAL_ICRS_SCOPE"),
                   ("array_classification_version", array.method_version),
                   ("diameter_gate", "ALL_RECOGNIZED_TOKENS_ONE_FAMILY_OR_LEGACY_LABEL"))
        if not issues:
            outcome = O.SATISFIED if separation <= radius else O.NOT_SATISFIED
    return CriterionResult(
        criterion_id="POS-SINGLE", policy_ref=f"{POLICY_DOCUMENT}, Position",
        method_version="archive_pos_single_1", approval=MethodApproval.APPROVED,
        applicability=A.NOT_APPLICABLE if solar else A.UNRESOLVED if issues else A.APPLICABLE,
        evaluation=E.NOT_APPLICABLE if solar else E.INSUFFICIENT_INFORMATION if issues else E.EVALUATED,
        outcome=outcome, context_id=context.context_id, proposed=None, candidate=None,
        derived=derived, details=details, issues=tuple(issues),
        reasons=("SOLAR_EXEMPT",) if solar else tuple(i.code for i in issues) if issues else
        ("WITHIN_INCLUSIVE_CANDIDATE_BEAM" if outcome is O.SATISFIED else "OUTSIDE_CANDIDATE_BEAM",),
        decision_refs=(DECISION_REF,), numeric_method="SPHERICAL_FLOAT64_INCLUSIVE_NO_EQUALITY_BAND",
    )
