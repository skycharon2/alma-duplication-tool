"""Shared, exact proposed REST/SKY frequency preparation.

Keeps raw request evidence intact. Redshift conversion does not infer a reference
frame, convert RMS, or reinterpret bandwidths.
"""

import math
from dataclasses import dataclass
from fractions import Fraction

FREQUENCY_PREPARATION_VERSION = "proposed_sky_frequency_1"


def _positive(value):
    if isinstance(value, bool):
        raise ValueError("Boolean quantity")
    value = Fraction(str(value))
    if value <= 0:
        raise ValueError("Nonpositive quantity")
    return value


def exact_request_quantity(quantity):
    """Recover decimal input before float unit normalization, for frequency and spectral-resolution preparation."""
    scales = {
        "GHz": {"GHz": "1", "MHz": "0.001", "kHz": "0.000001", "Hz": "0.000000001"},
        "MHz": {"GHz": "1000", "MHz": "1", "kHz": "0.001", "Hz": "0.000001"},
        "km/s": {"km/s": "1", "m/s": "0.001"},
    }
    try:
        scale = Fraction(scales[quantity.unit][quantity.raw_unit])
    except KeyError as exc:
        raise ValueError("Unsupported request input unit") from exc
    return _positive(quantity.raw_value) * scale


def _finite_float(value):
    try:
        rounded = float(value)
    except OverflowError:
        return None
    return rounded if math.isfinite(rounded) and rounded > 0 else None


@dataclass(frozen=True, slots=True)
class PreparedFrequency:
    sky_ghz_exact: Fraction | None
    sky_ghz: float | None
    reasons: tuple[str, ...] = ()


def prepare_frequency(frequency, source_redshift):
    """Convert explicit REST + z once; SKY never consumes the redshift."""
    if frequency is None or frequency.kind not in {"REST", "SKY"}:
        return PreparedFrequency(None, None, ("FREQUENCY_REFERENCE_REQUIRED",))
    try:
        if frequency.quantity.unit != "GHz":
            raise ValueError("Canonical GHz required")
        sky = exact_request_quantity(frequency.quantity)
        if frequency.kind == "REST":
            if source_redshift is None:
                return PreparedFrequency(None, None, ("SOURCE_REDSHIFT_REQUIRED",))
            if isinstance(source_redshift, bool):
                raise ValueError("Boolean redshift")
            denominator = 1 + Fraction(str(source_redshift))
            if denominator <= 0:
                raise ValueError("Require z > -1")
            sky /= denominator
    except (ValueError, ZeroDivisionError, TypeError):
        return PreparedFrequency(None, None, ("INVALID_FREQUENCY_INPUT",))
    display = _finite_float(sky)
    if display is None:
        return PreparedFrequency(None, None, ("SKY_FREQUENCY_UNREPRESENTABLE",))
    return PreparedFrequency(sky, display)
