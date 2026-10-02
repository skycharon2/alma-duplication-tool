"""Confirmed candidate-frequency Archive half-power position criterion."""
from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.domain.spatial import SkyPosition, SpatialStatus, PositionInterpretation
from alma_duplicate.parsers.array_classification import classify_array_type
from alma_duplicate.geometry import angular_separation_deg, primary_beam_fwhm_deg
from alma_duplicate.spatial_evidence import adapt_spatial
from alma_duplicate.rules.confirmed import DECISION_REF
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionIssue, CriterionOutcome as O,
    MethodApproval, MethodApplicability as A, EvaluationStatus as E, EvidenceSide as S,
)


def evaluate_archive_position(request, context, spatial_evidence, *, array_evidence=None, beam_diameter_m=None):
    issues = []
    derived = ()
    details = ()
    outcome = None
    solar = request.target_kind == "SUN"
    scope_reasons = []
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
        if array_evidence is not None:
            if (array_evidence.context_id != context.context_id
                    or array_evidence.source_record_id != context.reference.source_record_id):
                raise ValueError("Array evidence belongs to another candidate")
            diameters = array_evidence.diameters_m
            if beam_diameter_m is not None and beam_diameter_m not in diameters:
                raise ValueError("Beam variant absent from bound official array evidence")
            diameter = beam_diameter_m if beam_diameter_m is not None else (diameters[0] if len(diameters) == 1 else None)
            if diameter is None:
                issue("UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED", "context.official_array")
                for reason in array_evidence.reasons:
                    issue(reason, "context.official_array")
            elif array_evidence.total_power_at(diameter):
                # Supervisor-confirmed physical beam interpretation: TP uses D=12 m.
                # Broader TP science applicability remains a separate branch gate.
                scope_reasons.append(
                    "ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED"
                )
        elif beam_diameter_m is not None:
            raise ValueError("Archive beam variants require bound official array evidence")
        elif (array.unrecognized_tokens or len(array.family_counts) > 1
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
        separation = None if evidence.center is None else angular_separation_deg(
            SkyPosition(request.position.ra_deg, request.position.dec_deg, "ICRS"), evidence.center)
        derived = (("separation_deg", separation), ("candidate_radius_deg", radius),
                   ("candidate_frequency_ghz", q.canonical_value), ("antenna_diameter_m", diameter))
        details = (("position_interpretation", "CONFIRMED_FIXED_CELESTIAL_ICRS_SCOPE"),
                   ("array_classification_version", array.method_version),
                   ("diameter_gate", "ALL_RECOGNIZED_TOKENS_ONE_FAMILY_OR_LEGACY_LABEL"))
        if array_evidence is not None:
            details = (("position_interpretation", "CONFIRMED_FIXED_CELESTIAL_ICRS_SCOPE"),
                       ("diameter_gate", "OFFICIAL_AQ_SOURCE_ARRAY_BOUND"),
                       ("array_evidence", array_evidence))
        if not issues:
            outcome = O.SATISFIED if separation <= radius else O.NOT_SATISFIED
    from alma_duplicate.archive_array_evidence import DECISION_REF as ARRAY_DECISION
    tp_position_decision = (
        "docs/evidence/archive_tp_d12_position_decision_2026-10-02.md"
    )
    if solar:
        reasons = ("SOLAR_EXEMPT",)
    elif issues:
        reasons = tuple(i.code for i in issues) + tuple(scope_reasons)
    else:
        reasons = (
            "WITHIN_INCLUSIVE_CANDIDATE_BEAM"
            if outcome is O.SATISFIED
            else "OUTSIDE_CANDIDATE_BEAM",
            *scope_reasons,
        )
    decision_refs = (DECISION_REF,)
    if array_evidence is not None:
        decision_refs += (ARRAY_DECISION,)
    if scope_reasons:
        decision_refs += (tp_position_decision,)
    return CriterionResult(
        criterion_id="POS-SINGLE", policy_ref=f"{POLICY_DOCUMENT}, Position",
        method_version="archive_pos_single_3" if array_evidence is not None else "archive_pos_single_1", approval=MethodApproval.APPROVED,
        applicability=A.NOT_APPLICABLE if solar else A.UNRESOLVED if issues else A.APPLICABLE,
        evaluation=E.NOT_APPLICABLE if solar else E.INSUFFICIENT_INFORMATION if issues else E.EVALUATED,
        outcome=outcome, context_id=context.context_id, proposed=None, candidate=None,
        derived=derived, details=details, issues=tuple(issues),
        reasons=reasons,
        decision_refs=decision_refs,
        numeric_method="SPHERICAL_FLOAT64_INCLUSIVE_NO_EQUALITY_BAND",
    )
