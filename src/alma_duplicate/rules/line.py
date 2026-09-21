"""Confirmed Archive line rules, evaluated without crossing pair boundaries."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import math

from astropy import units as u

from alma_duplicate.domain.line_pairing import LinePairAttempt
from alma_duplicate.line_pairing import build_line_pairs
from alma_duplicate.proposed_line import C_KMS
from alma_duplicate.rules.aggregation import (
    BranchAssessment,
    Truth,
    three_and,
    three_or,
)
from alma_duplicate.rules.confirmed import DECISION_REF, archive_scope
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


def _truth(result):
    if not result.eligible_for_formal_aggregation:
        return Truth.UNKNOWN
    return Truth.TRUE if result.outcome is O.SATISFIED else Truth.FALSE


@dataclass(frozen=True, slots=True)
class LinePairEvaluation:
    """All six conditions refer to one window and one resolved candidate SPW."""

    attempt: LinePairAttempt
    criteria: tuple[CriterionResult, ...]
    truth: Truth
    status: str
    reasons: tuple[str, ...] = ()
    method_version: str = "archive_line_pair_and_1"
    decision_refs: tuple[str, ...] = (DECISION_REF,)
    scope: str = "ONE_PROPOSED_WINDOW_ONE_CANDIDATE_COMPONENT"

    def __post_init__(self):
        if tuple(r.criterion_id for r in self.criteria) != LINE_CRITERIA:
            raise ValueError(
                "A line pair requires all six criteria exactly once in order"
            )
        if any(
            r.context_id != self.attempt.candidate_context_id for r in self.criteria
        ):
            raise ValueError("Pair criterion belongs to another context")
        if self.status != STATUS[self.truth]:
            raise ValueError("Pair status disagrees with truth")
        expected = (
            Truth.UNKNOWN
            if "BRANCH_SCOPE_UNSUPPORTED" in self.reasons
            else three_and(_truth(r) for r in self.criteria)
        )
        if self.truth is not expected:
            raise ValueError("Pair truth disagrees with its gated criteria")


def _number(value, *, sqrt=False):
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 40
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        result = float(decimal.sqrt() if sqrt else decimal)
    return result if math.isfinite(result) and (result != 0 or value == 0) else None


def _quantity(value, unit, target):
    """Convert explicit units only, comparing decimal scalars and scale exactly."""
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
        elif reason.startswith(
            ("CANDIDATE_", "EXACT_COMPONENT_", "COMPONENT_", "UNIQUE_COMPONENT_")
        ):
            side, path = S.CANDIDATE, "context.assigned_component"
        return CriterionIssue(side, reason, path, reason.replace("_", " ").capitalize())

    return CriterionResult(
        criterion_id=name,
        policy_ref=f"{POLICY_DOCUMENT}, Spectral windows",
        method_version=f"archive_{name.lower().replace('-', '_')}_1",
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


def _numerical(request, context, attempt):
    """The caller builds preparation once; resolve its reference once for all rules."""
    if attempt.reference is None:
        return tuple(
            _result(
                name, context, None, attempt.reasons or ("PAIR_REFERENCE_REQUIRED",)
            )
            for name in LINE_CRITERIA[2:]
        )
    window, sensitivity, component = attempt.reference.resolve(request, context)
    planned = attempt.proposed
    sky = _quantity(planned.sky_frequency_ghz, "GHz", "GHz")
    dv_plan = _quantity(planned.planned_resolution_kms, "km/s", "km/s")
    mode = attempt.candidate_mode
    candidate_mode = (
        mode.operational_mode
        if mode is not None and mode.status == "AVAILABLE"
        else "UNKNOWN"
    )
    modes = (window.correlator_mode, candidate_mode)
    # Both sides are required; a known TDM is a definite failure even if the other is unknown.
    fdm = False if "TDM" in modes else (True if modes == ("FDM", "FDM") else None)
    mode_reasons = tuple(
        f"{side}_FDM_MODE_REQUIRED"
        for side, value in zip(("PROPOSED", "CANDIDATE"), modes)
        if value not in {"FDM", "TDM"}
    )
    results = [
        _result(
            "LINE-FDM",
            context,
            fdm,
            mode_reasons if fdm is None else (),
            details=(
                ("proposed_mode", modes[0]),
                ("candidate_mode", modes[1]),
                ("mode_method_version", "" if mode is None else mode.method_version),
            ),
        )
    ]

    interval = component.frequency_interval
    low = None if interval is None else _quantity(interval.low, interval.unit, "GHz")
    high = None if interval is None else _quantity(interval.high, interval.unit, "GHz")
    coverage_reasons = []
    if sky is None:
        coverage_reasons.append("PROPOSED_SKY_FREQUENCY_REQUIRED")
    if low is None or high is None or low > high:
        coverage_reasons.append("EXACT_COMPONENT_INTERVAL_REQUIRED")
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
            details=(("interval_source", "frequency_support.assigned_component"),),
        )
    )

    resolution = component.resolution
    dnu = (
        None
        if resolution is None
        else _quantity(resolution.value, resolution.unit, "GHz")
    )
    dv_archive = None if sky is None or dnu is None else C_KMS * dnu / sky
    resolution_reasons = []
    if sky is None:
        resolution_reasons.append("PROPOSED_SKY_FREQUENCY_REQUIRED")
    if dnu is None:
        resolution_reasons.append("COMPONENT_FREQUENCY_RESOLUTION_REQUIRED")
    if dv_plan is None:
        resolution_reasons.append("PLANNED_RESOLUTION_REQUIRED")
    compatible = None if resolution_reasons else dv_archive <= dv_plan
    if compatible is False:
        resolution_reasons.append("ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED")
    resolution_derived = (
        ("archive_resolution_kms", _number(dv_archive)),
        ("planned_resolution_kms", _number(dv_plan)),
    )
    results.append(
        _result(
            "LINE-RESOLUTION-COMPATIBILITY",
            context,
            compatible,
            resolution_reasons,
            proposed=_value(
                dv_plan, "km/s", window.window_id, "PREPARED_PLANNED_RESOLUTION"
            ),
            candidate=_value(
                dv_archive,
                "km/s",
                "frequency_support.assigned_component.resolution",
                "AT_PROPOSED_SKY_CENTER",
            ),
            derived=resolution_derived,
        )
    )

    rms_reasons = list(resolution_reasons)
    entries = [s for s in component.sensitivities if s.basis == "10km/s"]
    sigma10 = (
        _quantity(entries[0].value, entries[0].unit, "mJy/beam")
        if len(entries) == 1
        else None
    )
    if sigma10 is None:
        rms_reasons.append("UNIQUE_COMPONENT_10KMS_RMS_REQUIRED")
    rms = sensitivity.rms
    sigma_requested = (
        None if rms is None else _quantity(rms.value, rms.unit, "mJy/beam")
    )
    if sigma_requested is None:
        rms_reasons.append("PLANNED_LINE_RMS_REQUIRED")
    if sensitivity.basis not in {"SMOOTHED", "NATIVE_CHANNEL"}:
        rms_reasons.append("PLANNED_LINE_RMS_BASIS_UNRESOLVED")
    theta = request.angular_resolution
    theta_plan = None if theta is None else _quantity(theta.value, theta.unit, "arcsec")
    q = context.evidence.prepared.comparison_evidence.angular_resolution.quantity
    theta_archive = (
        _quantity(q.canonical_value, q.canonical_unit, "arcsec")
        if q.is_available
        else None
    )
    if theta_plan is None:
        rms_reasons.append("PROPOSED_ANGULAR_RESOLUTION_REQUIRED_FOR_RMS")
    if theta_archive is None:
        rms_reasons.append("CANDIDATE_ANGULAR_RESOLUTION_REQUIRED_FOR_RMS")
    at_plan_squared = comp_squared = ratio_squared = None
    if not rms_reasons:
        at_plan_squared = sigma10**2 * Fraction(10) / dv_plan
        comp_squared = at_plan_squared * (theta_plan / theta_archive) ** 4
        ratio_squared = comp_squared / sigma_requested**2
    derived = resolution_derived + (
        ("sigma_10kms_mjy_beam", _number(sigma10)),
        ("theta_plan_arcsec", _number(theta_plan)),
        ("theta_archive_arcsec", _number(theta_archive)),
        ("sigma_at_plan_mjy_beam", _number(at_plan_squared, sqrt=True)),
        ("sigma_comp_mjy_beam", _number(comp_squared, sqrt=True)),
        ("sigma_requested_mjy_beam", _number(sigma_requested)),
        ("max_factor", 2.0),
    )
    details = (
        ()
        if ratio_squared is None
        else (
            ("rms_ratio_squared_exact", str(ratio_squared)),
            ("sigma_at_plan_squared_exact", str(at_plan_squared)),
            ("sigma_comp_squared_exact", str(comp_squared)),
        )
    )
    results.append(
        _result(
            "LINE-RMS",
            context,
            None if rms_reasons else ratio_squared <= 4,
            rms_reasons,
            proposed=_value(
                sigma_requested,
                "mJy/beam",
                sensitivity.sensitivity_id,
                "REQUESTED_AT_PLANNED_RESOLUTION",
            ),
            candidate=_value(
                sigma10,
                "mJy/beam",
                "frequency_support.assigned_component.sensitivity@10km/s",
                "ARCHIVE_ESTIMATED_10KMS_RMS",
            ),
            derived=derived,
            details=details,
        )
    )
    return tuple(results)


def evaluate_line(request, context, common_criteria):
    """Build, evaluate AND per pair, then OR complete pairs in this context only."""
    if "LINE" not in request.intents:
        raise ValueError("Line evaluation requires a selected LINE intent")
    common = {r.criterion_id: r for r in common_criteria}
    if len(common) != len(common_criteria) or set(common) != {"POS-SINGLE", "ANGULAR"}:
        raise ValueError(
            "Line evaluation requires exactly the common position and angular criteria"
        )
    if any(r.context_id != context.context_id for r in common.values()):
        raise ValueError("Common line criteria belong to another context")
    pairing = build_line_pairs(request, context)
    supported = (
        archive_scope(request, context)
        and context.evidence.prepared.normalized_metadata.is_mosaic.value is False
        and context.evidence.row_link.is_linked
        and not context.alternative_context_ids
        and not {
            "UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED",
            "CONFLICTING_POSITION_INTERPRETATION",
        }.intersection(common["POS-SINGLE"].reasons)
    )
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
        pairs.append(
            LinePairEvaluation(attempt, criteria, truth, STATUS[truth], reasons)
        )
    values = [p.truth for p in pairs]
    reasons = list(pairing.reasons)
    if not pairing.proposed_enumeration_complete:
        values.append(Truth.UNKNOWN)
        reasons.append("PROPOSED_ENUMERATION_INCOMPLETE")
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
        tuple(reasons),
        method_version="archive_line_context_or_1",
    )
    return pairing, tuple(pairs), branch
