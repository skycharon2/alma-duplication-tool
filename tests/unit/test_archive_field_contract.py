from __future__ import annotations

import pytest

from alma_duplicate.clients.archive_contract import (
    TapFieldMetadata,
)
from alma_duplicate.clients.archive_field_contract import (
    ARCHIVE_COMPARISON_FIELD_SPECS,
    build_archive_comparison_evidence,
    validate_archive_comparison_metadata,
)
from alma_duplicate.domain.archive_evidence import (
    ArchiveEvidenceIssueKind,
    ArchiveFrequencyFrameStatus,
    ArchiveQuantityStatus,
    ArchiveSensitivityBasis,
    ArchiveSensitivityKind,
    ArchiveUnitConformance,
)


def _metadata(
    *,
    unit_overrides: dict[str, str | None] | None = None,
) -> tuple[TapFieldMetadata, ...]:
    overrides = unit_overrides or {}
    return tuple(
        TapFieldMetadata(
            name=spec.name,
            datatype="double",
            arraysize=None,
            unit=overrides.get(spec.name, spec.expected_unit),
            ucd=f"fixture.{spec.name}",
            utype=None,
            xtype=None,
            description=f"Fixture metadata for {spec.name}",
        )
        for spec in ARCHIVE_COMPARISON_FIELD_SPECS
    )


def _row() -> dict[str, object]:
    return {
        "frequency": 100.0,
        "bandwidth": 200_000_000.0,
        "spectral_resolution": 976.56,
        "spatial_resolution": 0.5,
        "sensitivity_10kms": 1.0,
        "cont_sensitivity_bandwidth": 0.2,
    }


def test_exact_live_units_build_typed_evidence() -> None:
    validation = validate_archive_comparison_metadata(
        _metadata()
    )

    evidence = build_archive_comparison_evidence(
        _row(),
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert validation.is_usable
    assert validation.changed_compatible_units == ()
    assert evidence.unit_safe
    assert evidence.frequency.lower_ghz == pytest.approx(99.9)
    assert evidence.frequency.upper_ghz == pytest.approx(100.1)
    assert (
        evidence.frequency.frame_status
        is ArchiveFrequencyFrameStatus
        .SKY_FREQUENCY_FRAME_UNSPECIFIED
    )
    assert not evidence.cross_source_frequency_ready
    assert evidence.spectral_resolution.quantity.canonical_value == (
        pytest.approx(976.56)
    )
    assert evidence.line_sensitivity.kind is (
        ArchiveSensitivityKind.LINE_10_KMS
    )
    assert evidence.continuum_sensitivity.kind is (
        ArchiveSensitivityKind.CONTINUUM_AGGREGATE_BANDWIDTH
    )
    assert evidence.line_sensitivity.basis is (
        ArchiveSensitivityBasis
        .QA0_EB_METADATA_CALCULATOR_ESTIMATE
    )
    assert ArchiveEvidenceIssueKind.ARCHIVE_FRAME_UNSPECIFIED in {
        issue.kind
        for issue in evidence.issues
    }


def test_compatible_changed_unit_is_converted_not_assumed() -> None:
    validation = validate_archive_comparison_metadata(
        _metadata(unit_overrides={"frequency": "MHz"})
    )
    row = _row()
    row["frequency"] = 100_000.0

    evidence = build_archive_comparison_evidence(
        row,
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert validation.is_usable
    assert validation.changed_compatible_units == ("frequency",)
    assert validation.field("frequency").unit_conformance is (
        ArchiveUnitConformance.COMPATIBLE_CONVERSION
    )
    assert evidence.frequency.centre.source_unit == "MHz"
    assert evidence.frequency.centre.canonical_value == 100.0


@pytest.mark.parametrize("unit", [None, "arcsec"])
def test_missing_or_incompatible_frequency_unit_fails_closed(
    unit: str | None,
) -> None:
    validation = validate_archive_comparison_metadata(
        _metadata(unit_overrides={"frequency": unit})
    )

    evidence = build_archive_comparison_evidence(
        _row(),
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert not validation.is_usable
    assert not evidence.unit_safe
    assert not evidence.has_frequency_coverage
    assert evidence.frequency.centre.canonical_value is None
    assert evidence.frequency.centre.status in {
        ArchiveQuantityStatus.MISSING_SOURCE_UNIT,
        ArchiveQuantityStatus.INCOMPATIBLE_SOURCE_UNIT,
    }


def test_changed_source_datatype_fails_closed() -> None:
    metadata = list(_metadata())
    frequency = metadata[0]
    metadata[0] = TapFieldMetadata(
        name=frequency.name,
        datatype="char",
        arraysize="*",
        unit=frequency.unit,
        ucd=frequency.ucd,
        utype=frequency.utype,
        xtype=frequency.xtype,
        description=frequency.description,
    )
    validation = validate_archive_comparison_metadata(tuple(metadata))

    evidence = build_archive_comparison_evidence(
        _row(),
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert not validation.is_usable
    assert evidence.frequency.centre.status is (
        ArchiveQuantityStatus.INCOMPATIBLE_SOURCE_DATATYPE
    )


def test_missing_value_is_distinct_from_bad_metadata() -> None:
    validation = validate_archive_comparison_metadata(_metadata())
    row = _row()
    row["spatial_resolution"] = None

    evidence = build_archive_comparison_evidence(
        row,
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert evidence.unit_safe
    assert evidence.angular_resolution.quantity.status is (
        ArchiveQuantityStatus.MISSING_VALUE
    )


@pytest.mark.parametrize(
    "value",
    [-1.0, 0.0],
)
def test_non_positive_physical_quantity_is_invalid(value: float) -> None:
    validation = validate_archive_comparison_metadata(_metadata())
    row = _row()
    row["bandwidth"] = value

    evidence = build_archive_comparison_evidence(
        row,
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert evidence.frequency.bandwidth.status is (
        ArchiveQuantityStatus.INVALID_VALUE
    )
    assert not evidence.has_frequency_coverage


@pytest.mark.parametrize(
    "field_name",
    [
        "frequency",
        "bandwidth",
        "spectral_resolution",
        "spatial_resolution",
        "sensitivity_10kms",
        "cont_sensitivity_bandwidth",
    ],
)
def test_all_comparison_quantities_require_strictly_positive_values(
    field_name: str,
) -> None:
    validation = validate_archive_comparison_metadata(_metadata())
    row = _row()
    row[field_name] = 0.0

    evidence = build_archive_comparison_evidence(
        row,
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    quantities = {
        "frequency": evidence.frequency.centre,
        "bandwidth": evidence.frequency.bandwidth,
        "spectral_resolution": evidence.spectral_resolution.quantity,
        "spatial_resolution": evidence.angular_resolution.quantity,
        "sensitivity_10kms": evidence.line_sensitivity.quantity,
        "cont_sensitivity_bandwidth": (
            evidence.continuum_sensitivity.quantity
        ),
    }
    assert quantities[field_name].status is (
        ArchiveQuantityStatus.INVALID_VALUE
    )


def test_non_positive_frequency_interval_is_not_available() -> None:
    validation = validate_archive_comparison_metadata(_metadata())
    row = _row()
    row["frequency"] = 0.05
    row["bandwidth"] = 200_000_000.0

    evidence = build_archive_comparison_evidence(
        row,
        validation,
        query_run_id="query-1",
        raw_row_id="query-1:00000000",
        result_index=0,
    )

    assert evidence.frequency.centre.is_available
    assert evidence.frequency.bandwidth.is_available
    assert not evidence.has_frequency_coverage
    assert evidence.frequency.lower_ghz is None
    assert evidence.frequency.upper_ghz is None
    assert ArchiveEvidenceIssueKind.FREQUENCY_INTERVAL_INVALID in {
        issue.kind for issue in evidence.issues
    }
