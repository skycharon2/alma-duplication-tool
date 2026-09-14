"""CONT-SETUP: does the proposed setup count as a continuum observation?

Appendix A, "Spectral windows": "To be considered a 'continuum' observation, the
proposed correlator setup must contain 2 or more windows with a bandwidth
> 1.8 GHz." This is applicability of the continuum condition, evaluated on the
proposed setup only; it is not a duplication verdict.

Width meaning (Q2, reported oral feedback): usable bandwidth. The expected
results follow the acceptance table prepared in
docs/evidence/scientific_feedback.md:

* USABLE widths are compared directly. The boundary is strict: 1.8 GHz does not
  qualify; canonical decimal values are compared without an equality band.
* A usable width cannot exceed its nominal width under this interpretation.
  NOMINAL width <= 1.8 GHz does not qualify; a larger width is unresolved
  unless the caller explicitly selects a provisional conversion; ``nominal_conversion=
  "PORTAL_SCRIPT_V1"`` applies the portal-script mapping used by the Queue
  adapter and records that choice.
* Two or more distinct qualifying windows give SATISFIED even for an incomplete
  list. NOT_SATISFIED needs a complete, fully resolved list with fewer than two.
  Otherwise evaluation is INSUFFICIENT_INFORMATION and outcome is None.
  Declared intents never decide.
"""
from __future__ import annotations

from alma_duplicate.domain.proposed_observation import ProposedObservationRequest, ProposedWindow
from alma_duplicate.queue_normalization import QueueFrequencyDerivationError, map_nominal_to_usable_mhz
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionOutcome as O, CriterionResult, EvidenceSide, MethodApproval, CriterionIssue,
    EvaluationStatus as E, MethodApplicability as A,
)

from alma_duplicate.rules.numeric import compare_positive, positive_canonical

CRITERION_ID = "CONT-SETUP"
METHOD_VERSION = "continuum_setup_2"
POLICY_REF = f"{POLICY_DOCUMENT}, Spectral windows (continuum definition)"
THRESHOLD_GHZ = 1.8
MIN_QUALIFYING_WINDOWS = 2
PORTAL_SCRIPT_V1 = "PORTAL_SCRIPT_V1"
DECISION_REFS = ("scientific-feedback-Q2:usable-bandwidth-for-1.8-GHz-threshold",)

QUALIFIED, NOT_QUALIFIED, UNRESOLVED = "QUALIFIED", "NOT_QUALIFIED", "UNRESOLVED"


def _format_width(value: float) -> str:
    """Preserve boundary-significant digits in diagnostic details."""
    text = str(value)
    return text[:-2] if text.endswith(".0") else text


def _exceeds_threshold(width_ghz: float) -> bool:
    return compare_positive(width_ghz, THRESHOLD_GHZ) > 0


def _portal_usable_ghz(width_ghz: float) -> float | None:
    try:
        usable_mhz, _ = map_nominal_to_usable_mhz(width_ghz * 1000.0)
    except QueueFrequencyDerivationError:
        return None
    return None if usable_mhz is None else usable_mhz / 1000.0


def qualify_window(window: ProposedWindow, *, nominal_conversion: str | None = None) -> tuple[str, str]:
    """Return (status, reason) for one proposed window."""
    if nominal_conversion not in (None, PORTAL_SCRIPT_V1):
        raise ValueError("Unsupported nominal conversion")
    if window.bandwidth is not None:
        if window.bandwidth.unit != "GHz":
            return UNRESOLVED, "WINDOW_WIDTH_UNIT_INCOMPATIBLE"
        width_ghz, kind = window.bandwidth.value, window.bandwidth_kind
    elif window.interval is not None:
        width_ghz, kind = window.interval.span_ghz, window.interval.kind
    else:
        return UNRESOLVED, "WINDOW_WIDTH_MISSING"
    try:
        positive_canonical(width_ghz)
    except ValueError:
        return UNRESOLVED, "WINDOW_WIDTH_INVALID"
    if kind == "UNKNOWN":
        return UNRESOLVED, "WINDOW_WIDTH_SEMANTICS_UNKNOWN"
    if kind == "USABLE":
        status = QUALIFIED if _exceeds_threshold(width_ghz) else NOT_QUALIFIED
        return status, f"USABLE_{_format_width(width_ghz)}_GHZ"
    if not _exceeds_threshold(width_ghz):
        # Usable width <= nominal width <= threshold under any reading.
        return NOT_QUALIFIED, f"{kind}_{_format_width(width_ghz)}_GHZ_BOUNDS_USABLE_WIDTH"
    if kind == "NOMINAL" and nominal_conversion == PORTAL_SCRIPT_V1:
        usable = _portal_usable_ghz(width_ghz)
        if usable is None:
            return UNRESOLVED, f"NOMINAL_{_format_width(width_ghz)}_GHZ_HAS_NO_PORTAL_MAPPING"
        status = QUALIFIED if _exceeds_threshold(usable) else NOT_QUALIFIED
        return status, f"NOMINAL_{_format_width(width_ghz)}_GHZ_PORTAL_USABLE_{_format_width(usable)}_GHZ"
    return UNRESOLVED, f"{kind}_{_format_width(width_ghz)}_GHZ_NEEDS_APPROVED_USABLE_WIDTH"


def evaluate_continuum_setup(
    request: ProposedObservationRequest, *, nominal_conversion: str | None = None,
) -> CriterionResult:
    """Evaluate CONT-SETUP on the validated proposed setup."""
    if nominal_conversion not in (None, PORTAL_SCRIPT_V1):
        raise ValueError(f"Unsupported nominal conversion: {nominal_conversion!r}")
    identities = [w.window_id for w in request.spectral_windows]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate window identities: expected a validated request")
    per_window = [(w.window_id, *qualify_window(w, nominal_conversion=nominal_conversion))
                  for w in request.spectral_windows]
    details = tuple((window_id, f"{status}:{reason}") for window_id, status, reason in per_window)
    # Distinct identities only; the validator already rejects duplicate IDs.
    qualified = len({window_id for window_id, status, _ in per_window if status == QUALIFIED})
    unresolved = sum(status == UNRESOLVED for _, status, _ in per_window)
    derived = (("qualifying_windows", float(qualified)), ("unresolved_windows", float(unresolved)),
               ("threshold_ghz", THRESHOLD_GHZ))
    complete = request.setup_complete is True
    if qualified >= MIN_QUALIFYING_WINDOWS:
        outcome, reasons = O.SATISFIED, ("TWO_OR_MORE_WINDOWS_WIDER_THAN_1.8_GHZ",)
    elif complete and unresolved == 0:
        outcome, reasons = O.NOT_SATISFIED, ("FEWER_THAN_TWO_QUALIFYING_WINDOWS",)
    else:
        reasons = tuple(r for r, present in (
            ("SETUP_ENUMERATION_INCOMPLETE", not complete),
            ("WINDOW_WIDTH_UNRESOLVED", unresolved > 0),
        ) if present)
        outcome = None
    refs = DECISION_REFS + ((f"nominal-conversion:{nominal_conversion}",) if nominal_conversion else ())
    issues = tuple(CriterionIssue(EvidenceSide.PROPOSED,
                    "INVALID_EVIDENCE" if reason == "WINDOW_WIDTH_INVALID" else
                    "INCOMPATIBLE_UNIT" if reason == "WINDOW_WIDTH_UNIT_INCOMPATIBLE" else
                    "UNRESOLVED_SEMANTICS" if "SEMANTICS" in reason else "MISSING_USABLE_WIDTH",
                    f"request.spectral_windows[{index}].bandwidth", reason)
                   for index, (_, status, reason) in enumerate(per_window) if status == UNRESOLVED)
    if not complete:
        issues += (CriterionIssue(EvidenceSide.PROPOSED, "INCOMPLETE_ENUMERATION",
                                  "request.setup_complete", "Not all windows are declared"),)
    return CriterionResult(
        criterion_id=CRITERION_ID, policy_ref=POLICY_REF, method_version=METHOD_VERSION,
        approval=MethodApproval.PROVISIONAL,
        applicability=A.APPLICABLE if outcome is not None else A.UNRESOLVED,
        evaluation=E.EVALUATED if outcome is not None else E.INSUFFICIENT_INFORMATION,
        outcome=outcome, context_id=None, proposed=None, candidate=None, derived=derived,
        reasons=reasons, issues=issues, decision_refs=refs, details=details,
    )
