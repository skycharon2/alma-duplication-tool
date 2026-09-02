from __future__ import annotations

import math

import pytest

from alma_duplicate.clients.archive_queries import (
    ARCHIVE_SELECTED_COLUMNS,
    ArchiveQuerySpec,
    build_count_adql,
    build_query_unit_metadata_adql,
    build_retrieval_adql,
    build_where_clause,
    normalize_query_parameters,
)


def _spec(
    *,
    science_only: bool = True,
) -> ArchiveQuerySpec:
    return ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        science_only=science_only,
    )


def test_count_and_retrieval_share_where_clause() -> None:
    spec = _spec()
    where_clause = build_where_clause(
        spec,
        frequency_units_verified=True,
    )

    assert build_count_adql(spec).endswith(where_clause)
    assert build_retrieval_adql(spec).endswith(
        where_clause
    )


def test_count_query_uses_server_side_count() -> None:
    query = build_count_adql(_spec())

    assert query.startswith(
        "SELECT COUNT(*) AS total_matches"
    )
    assert "FROM ivoa.obscore" in query
    assert "TOP" not in query.upper()


def test_retrieval_uses_explicit_projection() -> None:
    query = build_retrieval_adql(_spec())

    assert "SELECT *" not in query.upper()
    for column in ARCHIVE_SELECTED_COLUMNS:
        assert column in query


def test_science_filter_can_be_disabled() -> None:
    query = build_retrieval_adql(
        _spec(science_only=False)
    )

    assert "science_observation = 'T'" not in query


def test_normalized_parameters_are_immutable() -> None:
    parameters = normalize_query_parameters(_spec())

    assert parameters == (
        ("ra_deg", 201.365),
        ("dec_deg", -43.019),
        ("radius_deg", 0.006),
        ("science_only", True),
        ("frequency_min_ghz", None),
        ("frequency_max_ghz", None),
        ("angular_resolution_min_arcsec", None),
        ("angular_resolution_max_arcsec", None),
    )


def test_frequency_prefilter_uses_archive_coverage_overlap() -> None:
    spec = ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        frequency_min_ghz=229.0,
        frequency_max_ghz=231.0,
    )

    where_clause = build_where_clause(
        spec,
        frequency_units_verified=True,
    )

    assert (
        "frequency - 0.5 * bandwidth / 1000000000.0"
        in where_clause
    )
    assert "< 231" in where_clause
    assert "> 229" in where_clause
    assert build_count_adql(
        spec,
        frequency_units_verified=True,
    ).endswith(where_clause)
    assert build_retrieval_adql(
        spec,
        frequency_units_verified=True,
    ).endswith(where_clause)


def test_frequency_prefilter_requires_verified_query_units() -> None:
    spec = ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        frequency_min_ghz=229.0,
        frequency_max_ghz=231.0,
    )

    with pytest.raises(ValueError, match="verified Archive query units"):
        build_count_adql(spec)


def test_query_unit_probe_targets_only_arithmetic_fields() -> None:
    query = build_query_unit_metadata_adql()

    assert "FROM TAP_SCHEMA.columns" in query
    assert "table_name = 'ivoa.obscore'" in query
    assert "'frequency', 'bandwidth'" in query


def test_angular_prefilter_retains_unknown_resolution() -> None:
    spec = ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        angular_resolution_min_arcsec=0.1,
        angular_resolution_max_arcsec=1.5,
    )

    where_clause = build_where_clause(spec)

    assert "spatial_resolution IS NULL" in where_clause
    assert "spatial_resolution >= 0.1" in where_clause
    assert "spatial_resolution <= 1.5" in where_clause


@pytest.mark.parametrize(
    "kwargs",
    [
        {"frequency_min_ghz": 100.0},
        {"frequency_max_ghz": 101.0},
        {
            "frequency_min_ghz": 101.0,
            "frequency_max_ghz": 100.0,
        },
        {
            "angular_resolution_min_arcsec": -0.1,
            "angular_resolution_max_arcsec": 1.0,
        },
    ],
)
def test_invalid_optional_prefilter_is_rejected(
    kwargs: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        ArchiveQuerySpec(
            ra_deg=201.365,
            dec_deg=-43.019,
            radius_deg=0.006,
            **kwargs,
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("ra_deg", -0.1, "ra_deg"),
        ("ra_deg", 360.0, "ra_deg"),
        ("dec_deg", -90.1, "dec_deg"),
        ("dec_deg", 90.1, "dec_deg"),
        ("radius_deg", 0.0, "radius_deg"),
        ("radius_deg", 180.1, "radius_deg"),
        ("ra_deg", math.nan, "finite"),
    ],
)
def test_invalid_query_parameters_are_rejected(
    field_name: str,
    value: float,
    message: str,
) -> None:
    values = {
        "ra_deg": 201.365,
        "dec_deg": -43.019,
        "radius_deg": 0.006,
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=message):
        ArchiveQuerySpec(**values)


def test_non_numeric_coordinate_is_rejected() -> None:
    with pytest.raises(TypeError, match="real number"):
        ArchiveQuerySpec(
            ra_deg="201.365",  # type: ignore[arg-type]
            dec_deg=-43.019,
            radius_deg=0.006,
        )


def test_duplicate_retrieval_columns_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_retrieval_adql(
            _spec(),
            columns=("obs_id", "obs_id"),
        )
