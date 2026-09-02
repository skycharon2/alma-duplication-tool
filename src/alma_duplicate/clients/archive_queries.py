"""Pure ADQL construction for broad ALMA Archive candidate searches."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

from alma_duplicate.clients.archive_contract import (
    NormalizedParameters,
)

ARCHIVE_TABLE = "ivoa.obscore"
COUNT_ALIAS = "total_matches"
ARCHIVE_SCHEMA_VERSION = "1"
ARCHIVE_QUERY_UNIT_CONTRACT_VERSION = "2"

ARCHIVE_FREQUENCY_QUERY_UNITS = (
    ("frequency", "double", "GHz"),
    ("bandwidth", "double", "Hz"),
)
ARCHIVE_ANGULAR_RESOLUTION_QUERY_UNITS = (
    ("spatial_resolution", "double", "arcsec"),
)
ARCHIVE_QUERY_ARITHMETIC_UNITS = (
    ARCHIVE_FREQUENCY_QUERY_UNITS
    + ARCHIVE_ANGULAR_RESOLUTION_QUERY_UNITS
)

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
    """Validated broad candidate-search parameters.

    Frequency and angular-resolution bounds are optional prefilters.  They
    reduce network volume but do not replace strict local comparison.
    """

    ra_deg: float
    dec_deg: float
    radius_deg: float
    science_only: bool = True
    frequency_min_ghz: float | None = None
    frequency_max_ghz: float | None = None
    angular_resolution_min_arcsec: float | None = None
    angular_resolution_max_arcsec: float | None = None

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

        _validate_optional_interval(
            "frequency",
            self.frequency_min_ghz,
            self.frequency_max_ghz,
            minimum=0.0,
        )
        _validate_optional_interval(
            "angular_resolution",
            self.angular_resolution_min_arcsec,
            self.angular_resolution_max_arcsec,
            minimum=0.0,
        )


def _validate_finite_real(
    field_name: str,
    value: object,
) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number")

    if not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")


def _validate_optional_interval(
    label: str,
    lower: float | None,
    upper: float | None,
    *,
    minimum: float,
) -> None:
    if (lower is None) != (upper is None):
        raise ValueError(
            f"{label} minimum and maximum must be provided together"
        )
    if lower is None or upper is None:
        return

    _validate_finite_real(f"{label}_minimum", lower)
    _validate_finite_real(f"{label}_maximum", upper)
    if float(lower) < minimum:
        raise ValueError(
            f"{label} minimum must be at least {minimum}"
        )
    if float(upper) <= float(lower):
        raise ValueError(
            f"{label} maximum must be greater than its minimum"
        )


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
        (
            "frequency_min_ghz",
            (
                float(spec.frequency_min_ghz)
                if spec.frequency_min_ghz is not None
                else None
            ),
        ),
        (
            "frequency_max_ghz",
            (
                float(spec.frequency_max_ghz)
                if spec.frequency_max_ghz is not None
                else None
            ),
        ),
        (
            "angular_resolution_min_arcsec",
            (
                float(spec.angular_resolution_min_arcsec)
                if spec.angular_resolution_min_arcsec is not None
                else None
            ),
        ),
        (
            "angular_resolution_max_arcsec",
            (
                float(spec.angular_resolution_max_arcsec)
                if spec.angular_resolution_max_arcsec is not None
                else None
            ),
        ),
    )


def requested_query_unit_contract(
    spec: ArchiveQuerySpec,
) -> tuple[tuple[str, str, str], ...]:
    """Return only the arithmetic-field descriptors needed by ``spec``."""

    requested: tuple[tuple[str, str, str], ...] = ()
    if spec.frequency_min_ghz is not None:
        requested += ARCHIVE_FREQUENCY_QUERY_UNITS
    if spec.angular_resolution_min_arcsec is not None:
        requested += ARCHIVE_ANGULAR_RESOLUTION_QUERY_UNITS
    return requested


def build_query_unit_metadata_adql(
    expected_units: tuple[tuple[str, str, str], ...] = (
        ARCHIVE_QUERY_ARITHMETIC_UNITS
    ),
) -> str:
    """Return the TAP_SCHEMA probe required before query arithmetic."""

    if not expected_units:
        raise ValueError("at least one query-arithmetic field is required")
    column_names = tuple(name for name, _, _ in expected_units)
    if len(column_names) != len(set(column_names)):
        raise ValueError("query-arithmetic fields must be unique")
    quoted_columns = ", ".join(
        f"'{column_name}'" for column_name in column_names
    )

    return (
        "SELECT column_name, datatype, unit\n"
        "FROM TAP_SCHEMA.columns\n"
        f"WHERE table_name = '{ARCHIVE_TABLE}'\n"
        f"    AND column_name IN ({quoted_columns})"
    )


def build_where_clause(
    spec: ArchiveQuerySpec,
    *,
    frequency_units_verified: bool = False,
    angular_resolution_units_verified: bool = False,
) -> str:
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

    if spec.frequency_min_ghz is not None:
        if not frequency_units_verified:
            raise ValueError(
                "frequency prefilter requires verified Archive query units"
            )
        frequency_min = _format_adql_number(
            spec.frequency_min_ghz
        )
        frequency_max = _format_adql_number(
            spec.frequency_max_ghz
        )
        clauses.append(
            "((frequency IS NULL OR bandwidth IS NULL) OR (\n"
            "        (frequency - 0.5 * bandwidth / 1000000000.0) "
            f"< {frequency_max}\n"
            "        AND (frequency + 0.5 * bandwidth / "
            f"1000000000.0) > {frequency_min}))"
        )

    if spec.angular_resolution_min_arcsec is not None:
        if not angular_resolution_units_verified:
            raise ValueError(
                "angular-resolution prefilter requires verified "
                "Archive query units"
            )
        resolution_min = _format_adql_number(
            spec.angular_resolution_min_arcsec
        )
        resolution_max = _format_adql_number(
            spec.angular_resolution_max_arcsec
        )
        clauses.append(
            "(spatial_resolution IS NULL OR "
            f"(spatial_resolution >= {resolution_min} AND "
            f"spatial_resolution <= {resolution_max}))"
        )

    return "\n    AND ".join(clauses)


def build_count_adql(
    spec: ArchiveQuerySpec,
    *,
    frequency_units_verified: bool = False,
    angular_resolution_units_verified: bool = False,
) -> str:
    """Build a server-side COUNT query."""

    where_clause = build_where_clause(
        spec,
        frequency_units_verified=frequency_units_verified,
        angular_resolution_units_verified=(
            angular_resolution_units_verified
        ),
    )

    return (
        f"SELECT COUNT(*) AS {COUNT_ALIAS}\n"
        f"FROM {ARCHIVE_TABLE}\n"
        f"WHERE {where_clause}"
    )


def build_retrieval_adql(
    spec: ArchiveQuerySpec,
    *,
    columns: tuple[str, ...] = ARCHIVE_SELECTED_COLUMNS,
    frequency_units_verified: bool = False,
    angular_resolution_units_verified: bool = False,
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
    where_clause = build_where_clause(
        spec,
        frequency_units_verified=frequency_units_verified,
        angular_resolution_units_verified=(
            angular_resolution_units_verified
        ),
    )

    return (
        "SELECT\n"
        f"    {projection}\n"
        f"FROM {ARCHIVE_TABLE}\n"
        f"WHERE {where_clause}"
    )
