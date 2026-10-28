"""Derive planned line coordinates and resolution without candidate calculations."""

from fractions import Fraction

from alma_duplicate.proposed_frequency import (
    _positive, _finite_float, exact_request_quantity, prepare_frequency,
)

from alma_duplicate.domain.line_evidence import ProposedLineEvidence
from alma_duplicate.domain.proposed_observation import (
    ProposedWindow,
    ProposedSensitivity,
)

C_KMS = Fraction("299792.458")


def exact_prepared(value):
    """Read a prepared decision operand; never reconstruct it from display."""
    if value is None:
        return None
    try:
        return _positive(value)
    except (ValueError, ZeroDivisionError):
        return None


def prepare_line_window(
    window: ProposedWindow,
    sensitivities: tuple[ProposedSensitivity, ...],
    source_redshift: float | None,
) -> ProposedLineEvidence:
    """One WINDOW-scoped declaration owns the requested RMS and resolution.

    Both resolution declarations, when present, must agree in exact canonical
    arithmetic. Channel spacing and noise bandwidth never fill this role.
    """
    frequency = prepare_frequency(
        window.center,
        window.source_redshift if window.source_redshift is not None else source_redshift,
    )
    reasons = [{
        "FREQUENCY_REFERENCE_REQUIRED": "LINE_CENTER_REQUIRED",
        "INVALID_FREQUENCY_INPUT": "INVALID_LINE_FREQUENCY_INPUT",
    }.get(reason, reason) for reason in frequency.reasons]
    sky = frequency.sky_ghz_exact
    sky_value = frequency.sky_ghz
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
            width = exact_request_quantity(q)
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
        sky_frequency_ghz_exact=str(sky) if sky is not None else None,
        planned_resolution_kms_exact=str(values[0]) if resolution is not None else None,
    )
