"""Formal Queue spectral-line rules evaluated without crossing row/SPW boundaries."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import math

from astropy import units as u

from alma_duplicate.proposed_line import C_KMS
from alma_duplicate.queue_line_pairing import QueueLinePairAttempt, build_queue_line_pairs
from alma_duplicate.queue_normalization import QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION
from alma_duplicate.rules.aggregation import BranchAssessment, Truth, three_and, three_or
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT,
    CriterionIssue,
    CriterionOutcome as O,
    CriterionResult,
    CriterionValue,
    EvaluationStatus as E,
    EvidenceSide as S,
    MethodApplicability as A,
    MethodApproval,
)
from alma_duplicate.rules.numeric import positive_canonical
from alma_duplicate.rules.queue_common import queue_common_scope_supported

DECISION_REF = "docs/evidence/queue_line_decision_2026-09-25.md"
LINE_CRITERIA = (
    "POS-SINGLE",
    "ANGULAR",
    "LINE-FDM",
    "LINE-COVERAGE",
    "LINE-RESOLUTION-COMPATIBILITY",
    "LINE-RMS",
)
STATUS = {
    Truth.TRUE: "CRITERIA_MET",
    Truth.FALSE: "CRITERIA_NOT_MET",
    Truth.UNKNOWN: "INDETERMINATE",
}
METHODS = {
    "LINE-FDM": "queue_line_fdm_1",
    "LINE-COVERAGE": "queue_line_coverage_1",
    "LINE-RESOLUTION-COMPATIBILITY": "queue_line_resolution_compatibility_1",
    "LINE-RMS": "queue_line_rms_portal_1",
}


def _truth(result):
    if not result.eligible_for_formal_aggregation:
        return Truth.UNKNOWN
    return Truth.TRUE if result.outcome is O.SATISFIED else Truth.FALSE


@dataclass(frozen=True, slots=True)
class QueueLinePairEvaluation:
    """All six conditions refer to one proposed window and one Queue row/SPW."""

    attempt: QueueLinePairAttempt
    criteria: tuple[CriterionResult, ...]
    truth: Truth
    status: str
    reasons: tuple[str, ...] = ()
    method_version: str = "queue_line_pair_and_1"
    decision_refs: tuple[str, ...] = (DECISION_REF,)
    scope: str = "ONE_PROPOSED_WINDOW_ONE_QUEUE_ROW_SPW"

    def __post_init__(self):
        if tuple(r.criterion_id for r in self.criteria) != LINE_CRITERIA:
            raise ValueError("A Queue line pair requires all six criteria exactly once in order")
        if any(
            r.context_id != self.attempt.reference.candidate_context_id
            for r in self.criteria
        ):
            raise ValueError("Queue pair criterion belongs to another context")
        if self.status != STATUS[self.truth]:
            raise ValueError("Queue pair status disagrees with truth")
        expected = (
            Truth.UNKNOWN
            if "BRANCH_SCOPE_UNSUPPORTED" in self.reasons
            else three_and(_truth(r) for r in self.criteria)
        )
        if self.truth is not expected:
            raise ValueError("Queue pair truth disagrees with its gated criteria")


def _number(value, *, sqrt=False):
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 40
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        result = float(decimal.sqrt() if sqrt else decimal)
    return result if math.isfinite(result) and (result != 0 or value == 0) else None


def _quantity(value, unit, target):
    """Convert explicit units only, using the repository's exact decimal scale."""
    if value is None or unit is None:
        return None
    try:
        return positive_canonical(value) * positive_canonical(
            u.Unit(unit).to(u.Unit(target))
        )
    except (ValueError, TypeError):
        return None


def _result(
    name,
    context,
    passed,
    reasons=(),
    *,
    proposed=None,
    candidate=None,
    derived=(),
    details=(),
):
    unknown = passed is None
    if not unknown and any(value is None for _, value in derived):
        reasons = (*reasons, "NUMERIC_DISPLAY_UNREPRESENTABLE")

    def issue(reason):
        side = S.METHOD
        path = name
        if reason.startswith(("PROPOSED_", "PLANNED_")):
            side, path = S.PROPOSED, "request.spectral_windows/sensitivities"
        elif reason.startswith("QUEUE_"):
            side, path = S.CANDIDATE, "context.queue_row_spw"
        return CriterionIssue(side, reason, path, reason.replace("_", " ").capitalize())

    return CriterionResult(
        criterion_id=name,
        policy_ref=f"{POLICY_DOCUMENT}, Spectral windows",
        method_version=METHODS[name],
        approval=MethodApproval.APPROVED,
        applicability=A.UNRESOLVED if unknown else A.APPLICABLE,
        evaluation=E.INSUFFICIENT_INFORMATION if unknown else E.EVALUATED,
        outcome=None if unknown else (O.SATISFIED if passed else O.NOT_SATISFIED),
        context_id=context.context_id,
        proposed=proposed,
        candidate=candidate,
        reasons=tuple(reasons)
        or ("CONDITION_SATISFIED" if passed else "CONDITION_NOT_SATISFIED",),
        issues=tuple(issue(reason) for reason in reasons) if unknown else (),
        derived=tuple(derived),
        details=tuple(details),
        decision_refs=(DECISION_REF,),
        numeric_method="canonical_decimal_unit_scale_squared_rms_1",
    )


def _value(value, unit, field, semantics):
    return CriterionValue(_number(value), unit, field, semantics)


def _window(request, window_id):
    matches = [w for w in request.spectral_windows if w.window_id == window_id]
    if len(matches) != 1:
        raise ValueError("PAIR_PROPOSED_WINDOW_NOT_UNIQUE")
    return matches[0]


def _sensitivity(request, sensitivity_id):
    matches = [s for s in request.sensitivities if s.sensitivity_id == sensitivity_id]
    return matches[0] if len(matches) == 1 else None


def _numerical(request, context, attempt):
    """Resolve one row-bound reference once and evaluate only that Queue SPW."""
    planned, candidate = attempt.reference.resolve(request, context)
    window = _window(request, attempt.reference.proposed_window_id)
    spw = candidate.spw
    sky = _quantity(planned.sky_frequency_ghz, "GHz", "GHz")
    dv_plan = _quantity(planned.planned_resolution_kms, "km/s", "km/s")
    details = (
        ("proposed_window_id", attempt.reference.proposed_window_id),
        ("source_row_id", attempt.reference.source_row_id),
        ("snapshot_sha256", attempt.reference.snapshot_sha256),
        ("queue_spw_number", str(attempt.reference.spw_number)),
        ("frequency_derivation_version", spw.frequency_derivation.derivation_version),
        ("usable_bandwidth_version", spw.usable_bandwidth_derivation_version),
        ("mode_method_version", candidate.mode["mode_evidence"]["method_version"]),
    )

    # LINE-FDM: a known TDM is a definite failure; unknown mode is not a false result.
    qmode = candidate.mode["mode_evidence"]["mode"]
    modes = (window.correlator_mode, qmode)
    fdm = False if "TDM" in modes else (True if modes == ("FDM", "FDM") else None)
    mode_reasons = tuple(
        f"{side}_FDM_MODE_REQUIRED"
        for side, value in zip(("PROPOSED", "QUEUE"), modes)
        if value not in {"FDM", "TDM"}
    )
    results = [
        _result(
            "LINE-FDM",
            context,
            fdm,
            mode_reasons if fdm is None else (),
            details=details + (("proposed_mode", modes[0]), ("queue_mode", modes[1])),
        )
    ]

    # LINE-COVERAGE: exact usable interval from this same SPW.
    low = _quantity(spw.usable_lower_sky_frequency_ghz, "GHz", "GHz")
    high = _quantity(spw.usable_upper_sky_frequency_ghz, "GHz", "GHz")
    coverage_reasons = []
    if sky is None:
        coverage_reasons.append("PROPOSED_SKY_FREQUENCY_REQUIRED")
    if (
        spw.usable_bandwidth_derivation_version
        != QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION
        or low is None
        or high is None
        or low > high
    ):
        coverage_reasons.append("QUEUE_USABLE_INTERVAL_REQUIRED")
    results.append(
        _result(
            "LINE-COVERAGE",
            context,
            None if coverage_reasons else low <= sky <= high,
            coverage_reasons,
            proposed=_value(sky, "GHz", window.window_id, "PREPARED_SKY_CENTER"),
            derived=(
                ("sky_frequency_ghz", _number(sky)),
                ("interval_low_ghz", _number(low)),
                ("interval_high_ghz", _number(high)),
            ),
            details=details,
        )
    )

    # LINE-RESOLUTION: Queue Spec.Res. must be equal or finer than proposal target width.
    dnu_q = _quantity(
        spw.spectral_resolution_mhz.value,
        spw.spectral_resolution_mhz.canonical_unit,
        "MHz",
    )
    resolution_reasons = []
    if sky is None:
        resolution_reasons.append("PROPOSED_SKY_FREQUENCY_REQUIRED")
    if dv_plan is None:
        resolution_reasons.append("PLANNED_RESOLUTION_REQUIRED")
    if dnu_q is None:
        resolution_reasons.append("QUEUE_SPECTRAL_RESOLUTION_REQUIRED")
    dnu_plan = None if resolution_reasons else sky * Fraction(1000) * dv_plan / C_KMS
    compatible = None if resolution_reasons else dnu_q <= dnu_plan
    if compatible is False:
        resolution_reasons.append("QUEUE_RESOLUTION_COARSER_THAN_PLANNED")
    results.append(
        _result(
            "LINE-RESOLUTION-COMPATIBILITY",
            context,
            compatible,
            resolution_reasons,
            proposed=_value(dv_plan, "km/s", window.window_id, "PREPARED_PLANNED_RESOLUTION"),
            candidate=_value(
                dnu_q,
                "MHz",
                f"Spec.Res. SPW {spw.number}",
                "QUEUE_SPECTRAL_RESOLUTION",
            ),
            derived=(
                ("planned_resolution_kms", _number(dv_plan)),
                ("planned_resolution_mhz", _number(dnu_plan)),
                ("queue_resolution_mhz", _number(dnu_q)),
            ),
            details=details,
        )
    )

    # LINE-RMS: Queue Req.Sensitivity @ Ref.Freq.Width -> proposal resolution -> beam correction.
    rms_reasons = []
    if compatible is False:
        rms_reasons.append("QUEUE_RESOLUTION_COARSER_THAN_PLANNED")
    elif compatible is None:
        rms_reasons.append("QUEUE_RESOLUTION_COMPATIBILITY_REQUIRED")

    sensitivity = _sensitivity(request, planned.sensitivity_id)
    rms = None if sensitivity is None else sensitivity.rms
    sigma_requested = None if rms is None else _quantity(rms.value, rms.unit, "mJy/beam")
    if sigma_requested is None:
        rms_reasons.append("PLANNED_LINE_RMS_REQUIRED")
    if sensitivity is not None and sensitivity.basis not in {"SMOOTHED", "NATIVE_CHANNEL"}:
        rms_reasons.append("PLANNED_LINE_RMS_BASIS_UNRESOLVED")

    sigma_q_ref = _quantity(
        candidate.sensitivity_reference.requested_sensitivity_mjy.value,
        candidate.sensitivity_reference.requested_sensitivity_mjy.canonical_unit,
        "mJy",
    )
    ref_width = _quantity(
        candidate.sensitivity_reference.reference_width_mhz.value,
        candidate.sensitivity_reference.reference_width_mhz.canonical_unit,
        "MHz",
    )
    if sigma_q_ref is None:
        rms_reasons.append("QUEUE_REQUESTED_SENSITIVITY_REQUIRED")
    if ref_width is None:
        rms_reasons.append("QUEUE_REFERENCE_WIDTH_REQUIRED")

    theta = request.angular_resolution
    theta_plan = None if theta is None else _quantity(theta.value, theta.unit, "arcsec")
    theta_queue = _quantity(
        candidate.angular_resolution.value,
        candidate.angular_resolution.canonical_unit,
        "arcsec",
    )
    if theta_plan is None:
        rms_reasons.append("PROPOSED_ANGULAR_RESOLUTION_REQUIRED_FOR_RMS")
    if theta_queue is None:
        rms_reasons.append("QUEUE_ANGULAR_RESOLUTION_REQUIRED_FOR_RMS")

    spectral_squared = comp_squared = ratio_squared = None
    if not rms_reasons:
        spectral_squared = sigma_q_ref**2 * ref_width / dnu_plan
        comp_squared = spectral_squared * (theta_plan / theta_queue) ** 4
        ratio_squared = comp_squared / sigma_requested**2

    rms_details = details + (
        ("sensitivity_binding", candidate.sensitivity_binding),
        ("source_sensitivity_unit", "mJy"),
        ("portal_scaling", "QUEUE_PORTAL_PER_SPW_SCALING_APPLIED"),
        ("limitation", "QUEUE_PORTAL_SPW_TSYS_VARIATION_NOT_MODELLED"),
        ("raw_reference_frequency", candidate.sensitivity_reference.reference_frequency_ghz.raw_text),
        ("spectral_rms_squared_exact", "" if spectral_squared is None else str(spectral_squared)),
        ("comparable_rms_squared_exact", "" if comp_squared is None else str(comp_squared)),
        ("rms_ratio_squared_exact", "" if ratio_squared is None else str(ratio_squared)),
    )
    results.append(
        _result(
            "LINE-RMS",
            context,
            None if rms_reasons else ratio_squared <= 4,
            tuple(dict.fromkeys(rms_reasons)),
            proposed=_value(
                sigma_requested,
                "mJy/beam",
                "request.sensitivities" if sensitivity is None else sensitivity.sensitivity_id,
                "REQUESTED_AT_PLANNED_RESOLUTION",
            ),
            candidate=_value(
                sigma_q_ref,
                "mJy",
                "Req.Sensitivity",
                "QUEUE_REQUESTED_RMS_AT_REFERENCE_WIDTH",
            ),
            derived=(
                ("planned_resolution_mhz", _number(dnu_plan)),
                ("queue_reference_width_mhz", _number(ref_width)),
                ("queue_rms_at_planned_resolution_mjy", _number(spectral_squared, sqrt=True)),
                ("theta_plan_arcsec", _number(theta_plan)),
                ("theta_queue_arcsec", _number(theta_queue)),
                ("comparable_queue_rms_mjy", _number(comp_squared, sqrt=True)),
                ("sigma_requested_mjy_beam", _number(sigma_requested)),
                ("max_factor", 2.0),
            ),
            details=rms_details,
        )
    )
    return tuple(results)


def evaluate_queue_line(request, context, common_criteria):
    """AND every complete Queue pair, then OR whole pairs in one coherent row context."""
    if "LINE" not in request.intents:
        raise ValueError("Queue line evaluation requires a selected LINE intent")
    common = {r.criterion_id: r for r in common_criteria}
    if len(common) != len(common_criteria) or set(common) != {"POS-SINGLE", "ANGULAR"}:
        raise ValueError("Queue line evaluation requires exactly POS-SINGLE and ANGULAR")
    if any(r.context_id != context.context_id for r in common.values()):
        raise ValueError("Common Queue line criteria belong to another context")

    pairing = build_queue_line_pairs(request, context)
    supported = queue_common_scope_supported(tuple(common.values()))
    pairs = []
    for attempt in pairing.attempts:
        criteria = (
            common["POS-SINGLE"],
            common["ANGULAR"],
            *_numerical(request, context, attempt),
        )
        truth = three_and(_truth(r) for r in criteria) if supported else Truth.UNKNOWN
        reasons = tuple(
            f"{r.criterion_id}_UNRESOLVED_OR_UNAPPROVED"
            for r in criteria
            if not r.eligible_for_formal_aggregation
        )
        if not supported:
            reasons += ("BRANCH_SCOPE_UNSUPPORTED",)
        pairs.append(QueueLinePairEvaluation(attempt, criteria, truth, STATUS[truth], reasons))

    values = [p.truth for p in pairs]
    reasons = list(pairing.reasons)
    if not pairing.proposed_enumeration_complete:
        values.append(Truth.UNKNOWN)
        reasons.append("PROPOSED_ENUMERATION_INCOMPLETE")
    if not pairing.candidate_enumeration_complete:
        values.append(Truth.UNKNOWN)
        reasons.append("CANDIDATE_SPW_ENUMERATION_INCOMPLETE")
    if not supported:
        reasons.append("BRANCH_SCOPE_UNSUPPORTED")
    truth = three_or(values) if supported else Truth.UNKNOWN
    if truth is Truth.UNKNOWN and any(p.truth is Truth.UNKNOWN for p in pairs):
        reasons.append("UNRESOLVED_LINE_PAIRS")
    branch = BranchAssessment(
        "LINE",
        context.context_id,
        STATUS[truth],
        truth,
        LINE_CRITERIA,
        tuple(dict.fromkeys(reasons)),
        method_version="queue_line_context_or_1",
        decision_refs=(DECISION_REF,),
    )
    return pairing, tuple(pairs), branch
