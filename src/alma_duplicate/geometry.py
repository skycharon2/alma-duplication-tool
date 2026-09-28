"""Pure angular calculations; no source interpretation or selection policy.

Coordinates must already share the intended frame. Callers own frame/geometry
validation, diameter and frequency evidence, and inclusive or legacy boundaries.
"""
from __future__ import annotations

import math
from numbers import Real
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alma_duplicate.domain.spatial import SkyPosition


def angular_separation_deg(a: SkyPosition, b: SkyPosition) -> float:
    """Great-circle angle via atan2 of cross-product norm and dot product."""
    ra1, dec1, ra2, dec2 = map(math.radians, (a.ra_deg, a.dec_deg, b.ra_deg, b.dec_deg))
    delta = ra2 - ra1
    x = math.cos(dec2) * math.sin(delta)
    y = math.cos(dec1) * math.sin(dec2) - math.sin(dec1) * math.cos(dec2) * math.cos(delta)
    dot = math.sin(dec1) * math.sin(dec2) + math.cos(dec1) * math.cos(dec2) * math.cos(delta)
    return math.degrees(math.atan2(math.hypot(x, y), dot))


def primary_beam_fwhm_deg(frequency_ghz: float, diameter_m: float) -> float:
    """Full width, not radius; fixed coefficient 1.13 and exact SI speed of light."""
    for value in (frequency_ghz, diameter_m):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise ValueError("Frequency and diameter must be finite positive numbers")
    width = math.degrees(1.13 * 299792458. / 1e9 / frequency_ghz / diameter_m)
    if not math.isfinite(width) or not 0 < width <= 360:
        raise ValueError("Beam cannot be represented as a physical sky width")
    return width
