"""Application-derived ALMA array-family evidence for one Archive row.

The classification is heuristic evidence derived from the ObsCore
``antenna_arrays`` Pad:Antenna list. It is not an authoritative Archive field
and never a duplication verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ArrayFamily(StrEnum):
    MAIN_ARRAY_12M = "MAIN_ARRAY_12M"
    ACA_7M = "ACA_7M"
    TOTAL_POWER = "TOTAL_POWER"
    MIXED = "MIXED"
    UNRECOGNIZED = "UNRECOGNIZED"
    MISSING = "MISSING"


class ArrayClassificationBasis(StrEnum):
    PAD_ANTENNA_MAJORITY = "PAD_ANTENNA_MAJORITY"
    LEGACY_LABEL = "LEGACY_LABEL"
    NONE = "NONE"


INTERFEROMETRIC_DIAMETER_M = {
    ArrayFamily.MAIN_ARRAY_12M: 12.0,
    ArrayFamily.ACA_7M: 7.0,
}


@dataclass(frozen=True, slots=True)
class ArrayClassification:
    raw_value: object
    family: ArrayFamily
    basis: ArrayClassificationBasis
    antenna_count: int
    family_counts: tuple[tuple[str, int], ...]
    dominant_fraction: float | None
    unrecognized_tokens: tuple[str, ...]
    reasons: tuple[str, ...]
    method_version: str = "array_family_1"
    evidence_level: str = "application-derived"

    @property
    def interferometric_diameter_m(self) -> float | None:
        """Dish diameter for 12-m or 7-m interferometry only; TP/mixed stay None."""
        return INTERFEROMETRIC_DIAMETER_M.get(self.family)
