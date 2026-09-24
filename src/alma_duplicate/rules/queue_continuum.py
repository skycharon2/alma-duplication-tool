"""Scoped Queue continuum: source reference frequency and usable interval union.

Classification never changes raw quantities. Fractions decide thresholds; floats
are display values only. This method does not consume mode-classifier evidence.
"""

import json
import math
from fractions import Fraction

from alma_duplicate.domain.comparison import QueueContextEvidence
from alma_duplicate.queue_normalization import QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION
from alma_duplicate.rules.continuum import prepare_aggregate_rms, _quantity_issue
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT,
    CriterionResult,
    CriterionValue,
    CriterionIssue,
    CriterionOutcome as O,
    MethodApproval,
    MethodApplicability as A,
    EvaluationStatus as E,
    EvidenceSide as S,
)
from alma_duplicate.rules.numeric import positive_canonical

DECISION_REF = "docs/evidence/queue_row_continuum_decision_2026-09-24.md"


def scope_supported(common):
    return (
        len(common) == 2
        and {r.method_version for r in common}
        == {"queue_angular_factor_7", "queue_pos_single_5"}
        and all(dict(r.details).get("common_scope") == "SUPPORTED" for r in common)
    )


def merge_intervals(intervals):
    """Exact union of ordered endpoints, including touching intervals."""
    merged = []
    for lo, hi in sorted(intervals):
        if lo >= hi:
            raise ValueError("Positive interval width required")
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return tuple(merged)


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (OverflowError, ValueError):
        return None


def _issue(code, path, side=S.CANDIDATE):
    return CriterionIssue(side, code, path, code)


def _quantity(q, unit, path, issues):
    if q is None or q.canonical_unit != unit:
        issues.append(_issue("QUEUE_QUANTITY_UNIT_UNRESOLVED", path))
        return None
    try:
        return positive_canonical(q.value)
    except ValueError:
        issues.append(_issue("QUEUE_POSITIVE_QUANTITY_REQUIRED", path))
        return None


def _result(name, context, proposed, candidate, issues, passed, derived, details):
    outcome = None if issues else O.SATISFIED if passed else O.NOT_SATISFIED
    return CriterionResult(
        criterion_id=name,
        policy_ref=f"{POLICY_DOCUMENT}, Spectral windows",
        method_version="queue_cont_freq_2"
        if name == "CONT-FREQ"
        else "queue_cont_rms_portal_2",
        approval=MethodApproval.APPROVED,
        applicability=A.UNRESOLVED if issues else A.APPLICABLE,
        evaluation=E.INSUFFICIENT_INFORMATION if issues else E.EVALUATED,
        outcome=outcome,
        context_id=context.context_id,
        proposed=proposed,
        candidate=candidate,
        issues=tuple(issues),
        reasons=tuple(i.code for i in issues)
        if issues
        else ("WITHIN_INCLUSIVE_LIMIT" if passed else "EXCEEDS_LIMIT",),
        derived=tuple(derived),
        details=tuple(details),
        decision_refs=(DECISION_REF,),
    )


def evaluate_queue_continuum(request, context, common):
    """Evaluate one coherent retained Queue row, using validated common scope."""
    if not isinstance(context.evidence, QueueContextEvidence):
        raise TypeError("Queue context required")
    if any(r.context_id != context.context_id for r in common):
        raise ValueError("Common evidence belongs to another context")
    row = context.evidence.row
    if context.evidence.association.raw_row_id != row.raw_row.row_id:
        raise ValueError("Queue association belongs to another source row")
    base = (
        []
        if scope_supported(common)
        else [_issue("QUEUE_CONTINUUM_SCOPE_UNSUPPORTED", "context")]
    )
    details = [
        ("source_row_id", row.raw_row.row_id.value),
        ("spectral_setup_id", context.evidence.association.spectral_setup_id),
        ("snapshot_sha256", row.raw_row.row_id.snapshot_sha256),
    ]
    # Unsupported spectral scans have no regular-SPW sensitivity triplet.
    sensitivity = getattr(row.spectral, "sensitivity", None)
    fissues = list(base)
    fq = None if sensitivity is None else sensitivity.reference_frequency_ghz
    cf = _quantity(fq, "GHz", "Ref.Frequency", fissues)
    f = request.representative_frequency
    proposed = (
        None
        if f is None
        else CriterionValue(
            f.quantity.value,
            f.quantity.unit,
            "representative_frequency",
            "USER_SETUP_REPRESENTATIVE_SKY",
        )
    )
    if f is not None and f.kind != "SKY":
        fissues.append(
            _issue(
                "REPRESENTATIVE_SKY_FREQUENCY_REQUIRED",
                "request.representative_frequency",
                S.PROPOSED,
            )
        )
    issue = _quantity_issue(
        proposed, "GHz", S.PROPOSED, "request.representative_frequency"
    )
    if issue:
        fissues.append(issue)
    pf = None if fissues else positive_canonical(proposed.value)
    ratio = None if fissues else max(pf, cf) / min(pf, cf)
    candidate = (
        None
        if fq is None
        else CriterionValue(
            fq.value,
            fq.canonical_unit,
            "Ref.Frequency",
            "QUEUE_REQUESTED_REFERENCE_SKY",
        )
    )
    frequency = _result(
        "CONT-FREQ",
        context,
        proposed,
        candidate,
        fissues,
        ratio is not None and ratio <= Fraction(13, 10),
        [("factor", None if ratio is None else _number(ratio)), ("max_factor", 1.3)],
        details + [("frequency_fallback", "NONE")],
    )

    proposed, pissues, declarations = prepare_aggregate_rms(request)
    issues = list(base) + pissues
    issue = _quantity_issue(proposed, "mJy/beam", S.PROPOSED, "request.sensitivities")
    if issue:
        issues.append(issue)
    sr = None if sensitivity is None else sensitivity.requested_sensitivity_mjy
    bw = None if sensitivity is None else sensitivity.reference_width_mhz
    sigma = _quantity(sr, "mJy", "Req.Sensitivity", issues)
    reference_bw = _quantity(bw, "MHz", "Ref.Freq.Width", issues)
    _quantity(fq, "GHz", "Ref.Frequency", issues)
    intervals, records = [], []
    spws = getattr(row.spectral, "spws", ())
    if not spws:
        issues.append(_issue("REGULAR_SPW_UNION_REQUIRED", "context.spectral"))
    for spw in spws:
        d = spw.frequency_derivation
        records.append(
            dict(
                spw_number=spw.number,
                nominal_bandwidth_mhz=spw.bandwidth_mhz.value,
                raw_bandwidth=spw.bandwidth_mhz.raw_text,
                raw_frequency=spw.frequency_ghz.raw_text,
                bandwidth_derivation=spw.usable_bandwidth_derivation_kind.value,
                usable_bandwidth_ghz=spw.usable_bandwidth_ghz,
                sky_frequency_ghz=d.sky_frequency_ghz,
                frequency_derivation=d.kind.value
                if hasattr(d.kind, "value")
                else d.kind,
                frequency_version=d.derivation_version,
                velocity_frame=d.velocity_frame_raw,
                velocity_convention=d.velocity_convention_raw,
                doppler_factor=d.doppler_factor,
                bandwidth_version=spw.usable_bandwidth_derivation_version,
            )
        )
        try:
            if (
                spw.usable_bandwidth_derivation_version
                != QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION
            ):
                raise ValueError("Unapproved width version")
            centre = positive_canonical(d.sky_frequency_ghz)
            width = positive_canonical(spw.usable_bandwidth_ghz)
            lo, hi = centre - width / 2, centre + width / 2
            if lo <= 0:
                raise ValueError("Nonpositive sky interval")
            intervals.append((lo, hi))
            records[-1]["usable_interval_ghz_exact"] = [str(lo), str(hi)]
        except (ValueError, TypeError):
            issues.append(
                _issue("QUEUE_USABLE_SPW_INTERVAL_UNAVAILABLE", f"spw.{spw.number}")
            )
    merged = merge_intervals(intervals)
    # Never calculate a partial union when any contributing SPW is unresolved.
    complete = len(intervals) == len(spws) and bool(spws)
    aggregate_bw = (
        sum((hi - lo for lo, hi in merged), Fraction()) * 1000 if complete else None
    )
    squared, aggregate_rms, passed = None, None, False
    if not issues:
        squared = sigma**2 * reference_bw / aggregate_bw
        aggregate_rms = (
            math.sqrt(_number(squared)) if _number(squared) is not None else None
        )
        if aggregate_rms is None or aggregate_rms <= 0:
            issues.append(
                _issue("QUEUE_AGGREGATE_RMS_UNREPRESENTABLE", "context.sensitivity")
            )
        else:
            passed = squared <= 4 * positive_canonical(proposed.value) ** 2
    details += [
        ("raw_requested_sensitivity", "" if sr is None else sr.raw_text),
        ("source_sensitivity_unit", "mJy"),
        ("raw_reference_width_mhz", "" if bw is None else bw.raw_text),
        ("raw_reference_frequency_ghz", "" if fq is None else fq.raw_text),
        (
            "comparison_interpretation",
            "REQUESTED_FLUX_DENSITY_RMS_AT_REQUESTED_ANGULAR_RESOLUTION",
        ),
        ("angular_correction", "NONE"),
        ("tsys_variation", "NOT_MODELLED"),
        ("spw_evidence_json", json.dumps(records, allow_nan=False, sort_keys=True)),
        (
            "merged_intervals_ghz_exact_json",
            json.dumps([[str(lo), str(hi)] for lo, hi in merged]),
        ),
        ("aggregate_bandwidth_complete", str(complete)),
        ("aggregate_rms_squared_exact", "" if squared is None else str(squared)),
    ]
    if len(declarations) == 1:
        details.extend(
            ("contributing_window_id", wid) for wid in declarations[0].window_ids
        )
    candidate = (
        None
        if sr is None
        else CriterionValue(
            sr.value,
            sr.canonical_unit,
            "Req.Sensitivity",
            "QUEUE_REQUESTED_RMS_AT_REFERENCE_WIDTH",
        )
    )
    rms = _result(
        "CONT-RMS",
        context,
        proposed,
        candidate,
        issues,
        passed,
        [
            (
                "reference_bandwidth_mhz",
                None if reference_bw is None else _number(reference_bw),
            ),
            (
                "aggregate_bandwidth_mhz",
                None if aggregate_bw is None else _number(aggregate_bw),
            ),
            ("aggregate_rms_mjy", aggregate_rms),
            ("max_factor", 2.0),
        ],
        details,
    )
    return frequency, rms
