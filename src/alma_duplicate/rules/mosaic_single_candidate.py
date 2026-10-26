"""Proposed Mosaic pointing count against one Archive single-field context."""

from dataclasses import replace

from alma_duplicate.archive_mosaic_footprint import probe_footprint
from alma_duplicate.domain.spatial import PositionInterpretation
from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.rules.position_mosaic import evaluate_mosaic_position, DECISION
from alma_duplicate.rules.model import (
    CriterionIssue,
    EvidenceSide,
    CriterionOutcome as O,
    EvaluationStatus as E,
    MethodApplicability as A,
)
from alma_duplicate.spatial_evidence import adapt_spatial


def evaluate_single_candidate(
    proposed, context, *, archive_result, array_evidence, boundary_epsilon_arcsec
):
    """Use validated TAP centre units and AQ diameter; never require listobs."""
    criterion, _ = evaluate_mosaic_position(proposed, context_id=context.context_id)
    reason = "ARCHIVE_COORDINATE_SOURCE_REQUIRED"
    coverage = None
    side = EvidenceSide.CANDIDATE
    outcome = None
    if archive_result is not None:
        spatial = adapt_spatial(
            context,
            archive_result,
            interpretation=PositionInterpretation(
                context.context_id, "ICRS", "FIXED", "IVOA_OBSCORE_S_RA_S_DEC_ICRS"
            ),
        )
        q = context.evidence.prepared.comparison_evidence.frequency.centre
        diameters = () if array_evidence is None else array_evidence.diameters_m
        if array_evidence is not None and (
            array_evidence.context_id != context.context_id
            or array_evidence.source_record_id != context.reference.source_record_id
        ):
            raise ValueError("Array evidence belongs to another context")
        if spatial.geometry != "SINGLE_FIELD":
            reason = "ARCHIVE_CANDIDATE_GEOMETRY_UNRESOLVED"
        elif spatial.center_status != "AVAILABLE":
            reason = "ARCHIVE_COORDINATE_EVIDENCE_REQUIRED"
        elif len(diameters) != 1 or diameters[0] not in (7.0, 12.0):
            reason = "ARCHIVE_ARRAY_EVIDENCE_REQUIRED"
        elif proposed["array"] != f"{int(diameters[0])}m":
            reason = "CROSS_ARRAY_POSITION_COMPARISON_UNSUPPORTED"
        elif not q.is_available or q.canonical_unit != "GHz":
            reason = "ARCHIVE_FREQUENCY_EVIDENCE_REQUIRED"
        else:
            radius = primary_beam_fwhm_deg(q.canonical_value, diameters[0]) * 1800
            circles = [
                dict(
                    field_id=context.context_id,
                    ra_deg=spatial.center.ra_deg,
                    dec_deg=spatial.center.dec_deg,
                    radius_arcsec=radius,
                    metadata_context_ids=[context.context_id],
                )
            ]
            probes = probe_footprint(
                dict(circles=circles),
                proposed["points"],
                boundary_epsilon_arcsec=boundary_epsilon_arcsec,
            )
            n = len(probes["points"])
            if not n:
                raise ValueError("Empty proposed pointings")
            inside = sum(p["status"] == "INSIDE" for p in probes["points"])
            boundary = sum(p["status"] == "BOUNDARY" for p in probes["points"])
            coverage = dict(
                candidate_geometry="SINGLE_POINTING",
                circles=circles,
                probes=probes,
                inside_count=inside,
                pointing_count=n,
                boundary_count=boundary,
                frequency_ghz=q.canonical_value,
                frequency_source="ARCHIVE_CONTEXT_FREQUENCY",
                diameter_m=diameters[0],
                coverage_scope="SINGLE_ARCHIVE_CONTEXT_NOT_WHOLE_MEMBER",
            )
            criterion = replace(
                criterion,
                derived=(
                    ("inside_count", inside),
                    ("pointing_count", n),
                    ("boundary_count", boundary),
                ),
            )
            if proposed["completeness"] != "USER_CONFIRMED_COMPLETE":
                reason, side = (
                    "PROPOSED_POINTING_COMPLETENESS_REQUIRED",
                    EvidenceSide.PROPOSED,
                )
            elif inside * 2 > n:
                outcome, reason = (
                    O.SATISFIED,
                    "STRICT_MAJORITY_WITHIN_SINGLE_CANDIDATE_BEAM",
                )
            elif (inside + boundary) * 2 <= n:
                outcome, reason = (
                    O.NOT_SATISFIED,
                    "NO_STRICT_MAJORITY_WITHIN_SINGLE_CANDIDATE_BEAM",
                )
            else:
                reason, side = "MOSAIC_BOUNDARY_COUNT_UNRESOLVED", EvidenceSide.METHOD
    criterion = replace(
        criterion,
        outcome=outcome,
        evaluation=E.EVALUATED if outcome else E.INSUFFICIENT_INFORMATION,
        applicability=A.APPLICABLE if outcome else A.UNRESOLVED,
        method_version="archive_pos_mosaic_single_candidate_1",
        decision_refs=(DECISION,),
        reasons=(reason,),
        issues=()
        if outcome
        else (CriterionIssue(side, reason, "mosaic.position", reason),),
        details=(("scope", "SINGLE_ARCHIVE_CONTEXT_NOT_WHOLE_MEMBER"),),
    )
    return criterion, coverage
