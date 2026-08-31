"""Pure ADQL construction for ALMA Archive spatial searches."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

from alma_duplicate.clients.archive_contract import (
    NormalizedParameters,
)


ARCHIVE_TABLE = "ivoa.obscore"
COUNT_ALIAS = "total_matches"
ARCHIVE_SCHEMA_VERSION = "1"

# Explicit projection used by normalization and v0.4 reconstruction.
ARCHIVE_SELECTED_COLUMNS = (
    "proposal_id",
    "obs_publisher_did",
    "group_ous_uid",
    "member_ous_uid",
    "asdm_uid",
    "obs_id",
    "target_name",
    "s_ra",
    "s_dec",
    "s_region",
    "frequency",
    "bandwidth",
    "frequency_support",
    "spectral_resolution",
    "spatial_resolution",
    "sensitivity_10kms",
    "cont_sensitivity_bandwidth",
    "antenna_arrays",
    "is_mosaic",
    "science_observation",
    "qa2_passed",
    "obs_release_date",
    "lastModified",
)

REQUIRED_ARCHIVE_COLUMNS = frozenset(
    ARCHIVE_SELECTED_COLUMNS
)


@dataclass(frozen=True, slots=True)
class ArchiveQuerySpec:
    """Validated spatial candidate-search parameters."""

    ra_deg: float
    dec_deg: float
    radius_deg: float
    science_only: bool = True

    def __post_init__(self) -> None:
        _validate_finite_real("ra_deg", self.ra_deg)
        _validate_finite_real("dec_deg", self.dec_deg)
        _validate_finite_real("radius_deg", self.radius_deg)

        if not 0.0 <= float(self.ra_deg) < 360.0:
            raise ValueError(
                "ra_deg must be in the range [0, 360)"
            )

        if not -90.0 <= float(self.dec_deg) <= 90.0:
            raise ValueError(
                "dec_deg must be in the range [-90, 90]"
            )

        if not 0.0 < float(self.radius_deg) <= 180.0:
            raise ValueError(
                "radius_deg must be in the range (0, 180]"
            )

        if not isinstance(self.science_only, bool):
            raise TypeError("science_only must be a bool")


def _validate_finite_real(
    field_name: str,
    value: object,
) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")

    if not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")


def _format_adql_number(value: Real) -> str:
    return format(float(value), ".15g")


def normalize_query_parameters(
    spec: ArchiveQuerySpec,
) -> NormalizedParameters:
    """Return immutable, canonical query parameters."""

    return (
        ("ra_deg", float(spec.ra_deg)),
        ("dec_deg", float(spec.dec_deg)),
        ("radius_deg", float(spec.radius_deg)),
        ("science_only", spec.science_only),
    )


def build_where_clause(spec: ArchiveQuerySpec) -> str:
    """Build the shared predicate for COUNT and retrieval."""

    ra_text = _format_adql_number(spec.ra_deg)
    dec_text = _format_adql_number(spec.dec_deg)
    radius_text = _format_adql_number(spec.radius_deg)

    clauses = [
        (
            "1 = INTERSECTS("
            "s_region, "
            f"CIRCLE('ICRS', {ra_text}, {dec_text}, "
            f"{radius_text}))"
        )
    ]

    if spec.science_only:
        clauses.append("science_observation = 'T'")

    return "\n    AND ".join(clauses)


def build_count_adql(spec: ArchiveQuerySpec) -> str:
    """Build a server-side COUNT query."""

    return (
        f"SELECT COUNT(*) AS {COUNT_ALIAS}\n"
        f"FROM {ARCHIVE_TABLE}\n"
        f"WHERE {build_where_clause(spec)}"
    )


def build_retrieval_adql(
    spec: ArchiveQuerySpec,
    *,
    columns: tuple[str, ...] = ARCHIVE_SELECTED_COLUMNS,
) -> str:
    """Build retrieval ADQL with an explicit projection."""

    if not columns:
        raise ValueError(
            "At least one retrieval column is required"
        )

    if any(not column.strip() for column in columns):
        raise ValueError(
            "Retrieval columns must not be blank"
        )

    if len(columns) != len(set(columns)):
        raise ValueError(
            "Retrieval columns must be unique"
        )

    projection = ",\n    ".join(columns)

    return (
        "SELECT\n"
        f"    {projection}\n"
        f"FROM {ARCHIVE_TABLE}\n"
        f"WHERE {build_where_clause(spec)}"
    )
