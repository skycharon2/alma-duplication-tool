"""Exact comparisons of decimal spellings of validated canonical scalars.

No epsilon changes a policy threshold. This does not recover precision lost
before this boundary or interpret measurement uncertainty. Fraction arithmetic
avoids division/product overflow and Decimal ambient-context rounding.
"""
import math
from fractions import Fraction

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
