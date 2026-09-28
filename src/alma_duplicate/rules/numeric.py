"""Exact comparisons of decimal spellings of validated canonical scalars.

No epsilon changes a policy threshold. This does not recover precision lost
before this boundary or interpret measurement uncertainty. Fraction arithmetic
avoids division/product overflow and Decimal ambient-context rounding.
"""
import math
from fractions import Fraction
from decimal import Decimal, localcontext

from astropy import units as u

NUMERIC_METHOD = "canonical_decimal_exact_1"


def positive_canonical(value: float) -> Fraction:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError("Canonical scalar must be finite and positive")
    return Fraction(str(value))


def compare_positive(left: float, right: float) -> int:
    a, b = positive_canonical(left), positive_canonical(right)
    return (a > b) - (a < b)


def symmetric_factor(left: float, right: float) -> Fraction:
    a, b = positive_canonical(left), positive_canonical(right)
    return max(a, b) / min(a, b)


def rational_to_display(value: Fraction | None, *, sqrt: bool = False) -> float | None:
    """Render a rational at 40 decimal digits; never use this for decisions.

    Unrepresentable nonzero values return None, including float overflow and
    underflow. Exact zero remains zero. Square roots are presentation only.
    """
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 40
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
        result = float(decimal.sqrt() if sqrt else decimal)
    return result if math.isfinite(result) and (result != 0 or value == 0) else None


def explicit_unit_quantity(value, unit, target) -> Fraction | None:
    """Convert explicit units only, comparing decimal scalars and scale exactly."""
    if value is None or unit is None:
        return None
    try:
        return positive_canonical(value) * positive_canonical(
            u.Unit(unit).to(u.Unit(target))
        )
    except (ValueError, TypeError):
        return None
