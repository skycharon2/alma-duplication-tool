"""Derive planned line coordinates and resolution without candidate calculations."""

import math
from fractions import Fraction

from alma_duplicate.domain.line_evidence import ProposedLineEvidence
from alma_duplicate.domain.proposed_observation import (
    ProposedWindow,
    ProposedSensitivity,
)

C_KMS = Fraction("299792.458")


def _positive(value):
    if isinstance(value, bool):
        raise ValueError("Boolean quantity")
    value = Fraction(str(value))
    if value <= 0:
        raise ValueError("Nonpositive quantity")
    return value


def _finite_float(value):
    try:
        rounded = float(value)
    except OverflowError:
        return None
    return rounded if math.isfinite(rounded) and rounded > 0 else None


def prepare_line_window(
    window: ProposedWindow,
    sensitivities: tuple[ProposedSensitivity, ...],
    source_redshift: float | None,
) -> ProposedLineEvidence:
    """One WINDOW-scoped declaration owns the requested RMS and resolution.

    Both resolution declarations, when present, must agree in exact canonical
    arithmetic. Channel spacing and noise bandwidth never fill this role.
    """
    reasons = []
    sky = None
    center = window.center
    if center is None or center.kind not in {"REST", "SKY"}:
        reasons.append("LINE_CENTER_REQUIRED")
    else:
        try:
            if center.quantity.unit != "GHz":
                raise ValueError("Canonical GHz required")
            sky = _positive(center.quantity.value)
            if center.kind == "REST":
                if source_redshift is None:
                    reasons.append("SOURCE_REDSHIFT_REQUIRED")
                    sky = None
                else:
                    if isinstance(source_redshift, bool):
                        raise ValueError("Boolean redshift")
                    denominator = 1 + Fraction(str(source_redshift))
                    if denominator <= 0:
                        raise ValueError("Invalid redshift")
                    sky /= denominator
        except (ValueError, ZeroDivisionError):
            sky = None
            reasons.append("INVALID_LINE_FREQUENCY_INPUT")
    sky_value = _finite_float(sky) if sky is not None else None
    if sky is not None and sky_value is None:
        reasons.append("SKY_FREQUENCY_UNREPRESENTABLE")
        sky = None
    matches = [
        s
        for s in sensitivities
        if s.purpose == "LINE"
        and s.scope == "WINDOW"
        and s.window_ids == (window.window_id,)
    ]
    sensitivity = matches[0] if len(matches) == 1 else None
    if sensitivity is None:
        reasons.append("UNIQUE_WINDOW_LINE_SENSITIVITY_REQUIRED")
    elif sensitivity.rms is None:
        reasons.append("PLANNED_LINE_RMS_REQUIRED")
    elif sensitivity.basis not in {"NATIVE_CHANNEL", "SMOOTHED"}:
        reasons.append("PLANNED_LINE_RMS_BASIS_UNRESOLVED")
    quantities = [("window.spectral_resolution", window.spectral_resolution)]
    if sensitivity is not None:
        quantities.append(
            ("sensitivity.smoothing_resolution", sensitivity.smoothing_resolution)
        )
    values = []
    sources = []
    for name, q in quantities:
        if q is None:
            continue
        sources.append(name)
        try:
            width = _positive(q.value)
            if q.unit == "km/s":
                values.append(width)
            elif q.unit == "MHz":
                if sky is None:
                    reasons.append("SKY_FREQUENCY_REQUIRED_FOR_RESOLUTION")
                else:
                    values.append(C_KMS * width / (sky * 1000))
            else:
                reasons.append("UNSUPPORTED_PLANNED_RESOLUTION_UNIT")
        except ValueError:
            reasons.append("INVALID_PLANNED_RESOLUTION")
    resolution = None
    if not sources:
        reasons.append("PLANNED_RESOLUTION_REQUIRED")
    elif len(set(values)) > 1:
        reasons.append("CONFLICTING_PLANNED_RESOLUTIONS")
    elif len(values) == len(sources):
        resolution = _finite_float(values[0])
        if resolution is None:
            reasons.append("PLANNED_RESOLUTION_UNREPRESENTABLE")
    return ProposedLineEvidence(
        window.window_id,
        sensitivity.sensitivity_id if sensitivity else None,
        sky_value,
        resolution,
        tuple(sources),
        tuple(dict.fromkeys(reasons)),
    )
