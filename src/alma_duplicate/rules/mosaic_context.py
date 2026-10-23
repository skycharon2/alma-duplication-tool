"""Evaluate Mosaic geometry with Archive metadata and existing non-position rules."""

from dataclasses import replace
from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.archive_mosaic_footprint import probe_footprint
from alma_duplicate.rules.position_mosaic import evaluate_mosaic_position
from alma_duplicate.rules.model import (
    CriterionOutcome as O,
    EvaluationStatus as E,
    MethodApplicability as A,
    MethodApproval,
)
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup
from alma_duplicate.rules.confirmed import approve_setup, DECISION_REF
from alma_duplicate.rules.continuum import (
    evaluate_continuum_frequency,
    evaluate_continuum_rms,
)
from alma_duplicate.rules.aggregation import aggregate_continuum
from alma_duplicate.rules.line import evaluate_line


def _metadata_signature(context):
    """Require identical non-position operands before sharing execution coverage."""
    raw = context.evidence.prepared.raw_row
    evidence = context.evidence.prepared.comparison_evidence
    quantities = (
        evidence.frequency.centre,
        evidence.frequency.bandwidth,
        evidence.angular_resolution.quantity,
        evidence.spectral_resolution.quantity,
        evidence.line_sensitivity.quantity,
        evidence.continuum_sensitivity.quantity,
    )
    return (
        tuple(
            raw.get(k)
            for k in (
                "proposal_id",
                "member_ous_uid",
                "target_name",
                "frequency_support",
                "em_xel",
                "antenna_arrays",
                "is_mosaic",
                "science_observation",
            )
        ),
        tuple((q.status, q.canonical_value, q.canonical_unit) for q in quantities),
    )


def evaluate_mosaic_context(
    request,
    context,
    proposed,
    *,
    executions=(),
    array_evidence=None,
    metadata_contexts=(),
    ready_asdm_uids=None,
    boundary_epsilon_arcsec=0.000001,
    nominal_conversion=None,
):
    """Union only executions explicitly bound to compatible Archive metadata rows.

    Package membership alone is not a spectral association. Unbound executions
    remain reported exclusions; listobs spectral diagnostics never select beams.
    """
    from alma_duplicate.rules.model import CriterionIssue, EvidenceSide

    if (
        request.geometry != "MOSAIC"
        or request.target_kind != "FIXED"
        or not isinstance(context.evidence, ArchiveContextEvidence)
    ):
        raise ValueError(
            "Fixed Mosaic proposal and Archive comparison context required"
        )
    if proposed["source_name"] != request.target_name:
        raise ValueError("Imported pointings belong to another proposed target")
    position, _ = evaluate_mosaic_position(proposed, context_id=context.context_id)
    raw = context.evidence.prepared.raw_row
    member, source, asdm = (
        raw.get(k) for k in ("member_ous_uid", "target_name", "asdm_uid")
    )
    bindings = {}
    for other in (context, *metadata_contexts):
        if not isinstance(other.evidence, ArchiveContextEvidence):
            raise ValueError("Archive metadata contexts required")
        if _metadata_signature(other) == _metadata_signature(context):
            uid = other.evidence.prepared.raw_row.get("asdm_uid")
            bindings.setdefault(uid, set()).add(other.context_id)
    selected, excluded, seen = [], [], set()
    for execution in executions:
        if execution["member_ous_uid"] != member or execution["source_name"] != source:
            raise ValueError("Pointings belong to another Archive candidate")
        uid = execution["asdm_uid"]
        if uid in seen:
            raise ValueError("Ambiguous execution evidence")
        seen.add(uid)
        if ready_asdm_uids is not None and uid not in ready_asdm_uids:
            excluded.append(
                dict(asdm_uid=uid, reason="EXECUTION_POSITION_READINESS_REQUIRED")
            )
        elif uid in bindings:
            selected.append(execution)
        else:
            excluded.append(
                dict(
                    asdm_uid=uid,
                    reason="COMPATIBLE_ARCHIVE_EXECUTION_METADATA_REQUIRED",
                )
            )
    q = context.evidence.prepared.comparison_evidence.frequency.centre
    if array_evidence is not None and (
        array_evidence.context_id != context.context_id
        or array_evidence.source_record_id != context.reference.source_record_id
    ):
        raise ValueError("Array evidence belongs to another context")
    diameters = () if array_evidence is None else array_evidence.diameters_m
    coverage = None
    reason = "ARCHIVE_MOSAIC_EVIDENCE_REQUIRED"
    side = EvidenceSide.CANDIDATE
    if executions and not selected:
        reason = (
            "EXECUTION_POSITION_READINESS_REQUIRED"
            if any(
                e["reason"] == "EXECUTION_POSITION_READINESS_REQUIRED" for e in excluded
            )
            else "COMPATIBLE_ARCHIVE_EXECUTION_METADATA_REQUIRED"
        )
    elif selected and (len(diameters) != 1 or diameters[0] not in (7.0, 12.0)):
        reason = "ARCHIVE_ARRAY_EVIDENCE_REQUIRED"
    elif selected and (not q.is_available or q.canonical_unit != "GHz"):
        reason = "ARCHIVE_FREQUENCY_EVIDENCE_REQUIRED"
    elif selected:
        diameter = diameters[0]
        if proposed["array"] != f"{int(diameter)}m":
            reason = "CROSS_ARRAY_POSITION_COMPARISON_UNSUPPORTED"
        else:
            radius = primary_beam_fwhm_deg(q.canonical_value, diameter) * 1800
            circles = []
            for execution in selected:
                fields = execution["evidence"]["fields"]
                if not fields:
                    raise ValueError("Empty execution pointings")
                seen_fields = set()
                for field in fields:
                    fid = field["field_id"]
                    if fid in seen_fields:
                        raise ValueError("Duplicate science field identity")
                    seen_fields.add(fid)
                    probe_footprint(
                        {"circles": []},
                        [
                            dict(
                                id=str(fid),
                                frame=field["frame"],
                                ra_deg=field["ra_deg"],
                                dec_deg=field["dec_deg"],
                            )
                        ],
                        boundary_epsilon_arcsec=boundary_epsilon_arcsec,
                    )
                    circles.append(
                        dict(
                            field_id=f"{execution['asdm_uid']}:{fid}",
                            asdm_uid=execution["asdm_uid"],
                            metadata_context_ids=sorted(
                                bindings[execution["asdm_uid"]]
                            ),
                            ra_deg=field["ra_deg"],
                            dec_deg=field["dec_deg"],
                            radius_arcsec=radius,
                        )
                    )
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
                probes=probes,
                circles=circles,
                frequency_ghz=q.canonical_value,
                frequency_source="ARCHIVE_CONTEXT_FREQUENCY",
                asdm_uid=asdm,
                diameter_m=diameter,
                included_asdm_uids=[e["asdm_uid"] for e in selected],
                excluded_executions=excluded,
                inside_count=inside,
                pointing_count=n,
                boundary_count=boundary,
            )
            position = replace(
                position,
                derived=(
                    ("inside_count", inside),
                    ("pointing_count", n),
                    ("boundary_count", boundary),
                ),
                method_version="archive_pos_mosaic_metadata_union_1",
            )
            if proposed["completeness"] != "USER_CONFIRMED_COMPLETE":
                reason, side = (
                    "PROPOSED_POINTING_COMPLETENESS_REQUIRED",
                    EvidenceSide.PROPOSED,
                )
            elif inside * 2 > n:
                reason = "STRICT_MAJORITY_WITHIN_VERIFIED_CANDIDATE_SUBSET"
                position = replace(
                    position,
                    outcome=O.SATISFIED,
                    evaluation=E.EVALUATED,
                    applicability=A.APPLICABLE,
                )
            elif (inside + boundary) * 2 > n:
                reason, side = "MOSAIC_BOUNDARY_COUNT_UNRESOLVED", EvidenceSide.METHOD
            else:
                reason = "ARCHIVE_MEMBER_COMPLETENESS_REQUIRED_FOR_NEGATIVE_RESULT"
    position = replace(
        position,
        reasons=(reason,),
        details=position.details + (("excluded_executions", tuple(excluded)),),
        issues=()
        if position.outcome
        else (CriterionIssue(side, reason, "mosaic.position", reason),),
    )
    angular = replace(
        evaluate_angular_resolution(request, context),
        approval=MethodApproval.APPROVED,
        decision_refs=(DECISION_REF,),
        method_version="archive_mosaic_angular_shared_1",
    )
    criteria = [angular, position]
    branches = []
    setup = None
    pairing = None
    pairs = ()
    if "CONTINUUM" in request.intents:
        setup = approve_setup(
            evaluate_continuum_setup(request, nominal_conversion=nominal_conversion),
            nominal_conversion=nominal_conversion,
        )
        criteria.extend(
            (
                evaluate_continuum_frequency(request, context),
                evaluate_continuum_rms(request, context),
            )
        )
        branches.append(aggregate_continuum(context, (setup, *criteria), mosaic=True))
    if "LINE" in request.intents:
        pairing, pairs, branch = evaluate_line(
            request, context, tuple(criteria[:2]), mosaic=True
        )
        branches.append(branch)
    return dict(
        context_id=context.context_id,
        criteria=tuple(criteria),
        request_criteria=() if setup is None else (setup,),
        branches=tuple(branches),
        line_pairing=pairing,
        line_pairs=pairs,
        coverage=coverage,
    )
