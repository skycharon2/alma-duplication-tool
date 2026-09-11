"""CONT-SETUP: does the proposed setup count as a continuum observation?

Appendix A, "Spectral windows": "To be considered a 'continuum' observation, the
proposed correlator setup must contain 2 or more windows with a bandwidth
> 1.8 GHz." This is applicability of the continuum condition, evaluated on the
proposed setup only; it is not a duplication verdict.

Width meaning (Q2, reported oral feedback): usable bandwidth. The expected
results follow the acceptance table prepared in
docs/evidence/scientific_feedback.md:

* USABLE widths are compared directly. The boundary is strict: 1.8 GHz does not
  qualify; values within 1e-9 GHz of the threshold count as equal to it.
* A usable width can never exceed its nominal width, so a NOMINAL (or UNKNOWN
  kind) width <= 1.8 GHz does not qualify. A larger NOMINAL width is unresolved
  unless the caller opts into an approved conversion; ``nominal_conversion=
  "PORTAL_SCRIPT_V1"`` applies the portal-script mapping used by the Queue
  adapter and records that choice.
* Two or more distinct qualifying windows give SATISFIED even for an incomplete
  list. NOT_SATISFIED needs a complete, fully resolved list with fewer than two.
  Everything else is INSUFFICIENT_INFORMATION. Declared intents never decide.
"""
from __future__ import annotations

from alma_duplicate.domain.proposed_observation import ProposedObservationRequest, ProposedWindow
from alma_duplicate.queue_normalization import QueueFrequencyDerivationError, map_nominal_to_usable_mhz
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionOutcome as O, CriterionResult, EvidenceSide, MethodApproval,
)

CRITERION_ID = "CONT-SETUP"
METHOD_VERSION = "continuum_setup_1"
POLICY_REF = f"{POLICY_DOCUMENT}, Spectral windows (continuum definition)"
THRESHOLD_GHZ = 1.8
MIN_QUALIFYING_WINDOWS = 2
EQUALITY_BAND_GHZ = 1e-9
PORTAL_SCRIPT_V1 = "PORTAL_SCRIPT_V1"
DECISION_REFS = ("scientific-feedback-Q2:usable-bandwidth-for-1.8-GHz-threshold",)

QUALIFIED, NOT_QUALIFIED, UNRESOLVED = "QUALIFIED", "NOT_QUALIFIED", "UNRESOLVED"


def _exceeds_threshold(width_ghz: float) -> bool:
    return width_ghz > THRESHOLD_GHZ + EQUALITY_BAND_GHZ


def _portal_usable_ghz(width_ghz: float) -> float | None:
    try:
        usable_mhz, _ = map_nominal_to_usable_mhz(width_ghz * 1000.0)
    except QueueFrequencyDerivationError:
        return None
    return None if usable_mhz is None else usable_mhz / 1000.0


def qualify_window(window: ProposedWindow, *, nominal_conversion: str | None = None) -> tuple[str, str]:
    """Return (status, reason) for one proposed window."""
    if window.bandwidth is not None:
        width_ghz, kind = window.bandwidth.value, window.bandwidth_kind
    elif window.interval is not None:
        width_ghz, kind = window.interval.span_ghz, window.interval.kind
    else:
        return UNRESOLVED, "WINDOW_WIDTH_MISSING"
    if kind == "USABLE":
        status = QUALIFIED if _exceeds_threshold(width_ghz) else NOT_QUALIFIED
        return status, f"USABLE_{width_ghz:g}_GHZ"
    if not _exceeds_threshold(width_ghz):
        # Usable width <= nominal width <= threshold under any reading.
        return NOT_QUALIFIED, f"{kind}_{width_ghz:g}_GHZ_BOUNDS_USABLE_WIDTH"
    if kind == "NOMINAL" and nominal_conversion == PORTAL_SCRIPT_V1:
        usable = _portal_usable_ghz(width_ghz)
        if usable is None:
            return UNRESOLVED, f"NOMINAL_{width_ghz:g}_GHZ_HAS_NO_PORTAL_MAPPING"
        status = QUALIFIED if _exceeds_threshold(usable) else NOT_QUALIFIED
        return status, f"NOMINAL_{width_ghz:g}_GHZ_PORTAL_USABLE_{usable:g}_GHZ"
    return UNRESOLVED, f"{kind}_{width_ghz:g}_GHZ_NEEDS_APPROVED_USABLE_WIDTH"


def evaluate_continuum_setup(
    request: ProposedObservationRequest, *, nominal_conversion: str | None = None,
) -> CriterionResult:
    """Evaluate CONT-SETUP on the validated proposed setup."""
    if nominal_conversion not in (None, PORTAL_SCRIPT_V1):
        raise ValueError(f"Unsupported nominal conversion: {nominal_conversion!r}")
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
        outcome, reasons, side = O.SATISFIED, ("TWO_OR_MORE_WINDOWS_WIDER_THAN_1.8_GHZ",), None
    elif complete and unresolved == 0:
        outcome, reasons, side = O.NOT_SATISFIED, ("FEWER_THAN_TWO_QUALIFYING_WINDOWS",), None
    else:
        reasons = tuple(r for r, present in (
            ("SETUP_ENUMERATION_INCOMPLETE", not complete),
            ("WINDOW_WIDTH_UNRESOLVED", unresolved > 0),
        ) if present)
        outcome, side = O.INSUFFICIENT_INFORMATION, EvidenceSide.PROPOSED
    refs = DECISION_REFS + ((f"nominal-conversion:{nominal_conversion}",) if nominal_conversion else ())
    return CriterionResult(CRITERION_ID, POLICY_REF, METHOD_VERSION, MethodApproval.PROVISIONAL,
                           outcome, None, None, None, derived, reasons, side, refs, details)
