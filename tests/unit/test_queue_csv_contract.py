from __future__ import annotations

import pytest

from alma_duplicate.clients.queue_csv_contract import (
    QUEUE_BANDWIDTH_COLUMNS,
    QUEUE_DICTIONARY_ALIASES,
    QUEUE_DICTIONARY_ONLY_FIELDS,
    QUEUE_EVIDENCE_SNAPSHOT_SHA256,
    QUEUE_EXPECTED_COLUMNS,
    QUEUE_EXPECTED_SECONDARY_HEADER,
    QUEUE_FIELD_SPECS,
    QUEUE_FREQUENCY_COLUMNS,
    QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC,
    QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ,
    QUEUE_SPECTRAL_RESOLUTION_COLUMNS,
    QUEUE_SPW_COLUMNS,
    QUEUE_SPW_SLOT_COUNT,
    QueueMetadataStatus,
    SecondaryTokenKind,
    classify_secondary_token,
    spw_columns,
)


def test_contract_has_exact_operational_shape() -> None:
    assert len(QUEUE_EXPECTED_COLUMNS) == 79
    assert len(set(QUEUE_EXPECTED_COLUMNS)) == 79
    assert tuple(QUEUE_FIELD_SPECS) == (
        QUEUE_EXPECTED_COLUMNS
    )
    assert len(QUEUE_EXPECTED_SECONDARY_HEADER) == 79


def test_numbered_spw_fields_are_aligned_by_slot() -> None:
    assert QUEUE_SPW_SLOT_COUNT == 16
    assert len(QUEUE_SPW_COLUMNS) == 16
    assert len(QUEUE_FREQUENCY_COLUMNS) == 16
    assert len(QUEUE_BANDWIDTH_COLUMNS) == 16
    assert len(QUEUE_SPECTRAL_RESOLUTION_COLUMNS) == 16

    first = spw_columns(1)
    last = spw_columns(16)

    assert first.frequency == "Freq SPW 1"
    assert first.bandwidth == "Bandwidth SPW 1"
    assert first.spectral_resolution == (
        "Spec.Res. SPW 1"
    )
    assert last.frequency == "Freq SPW 16"
    assert last.bandwidth == "Bandwidth SPW 16"
    assert last.spectral_resolution == (
        "Spec.Res. SPW 16"
    )


@pytest.mark.parametrize("number", [0, 17])
def test_spw_number_outside_contract_is_rejected(
    number: int,
) -> None:
    with pytest.raises(ValueError):
        spw_columns(number)


def test_sps_bandwidth_conflict_remains_explicit() -> None:
    spec = QUEUE_FIELD_SPECS["SPS Bandwidth"]

    assert spec.dictionary_declaration == "[MHz]"
    assert spec.secondary_token == "[GHz]"
    assert spec.canonical_unit == "MHz"
    assert spec.metadata_status is (
        QueueMetadataStatus.CONFLICTING_UNITS
    )


def test_mosaic_dictionary_boolean_is_not_accepted() -> None:
    spec = QUEUE_FIELD_SPECS["Mosaic"]

    assert spec.dictionary_declaration == "[boolean]"
    assert spec.metadata_status is (
        QueueMetadataStatus.SEMANTIC_CONFLICT
    )


def test_velocity_spelling_is_normalized_but_preserved() -> None:
    spec = QUEUE_FIELD_SPECS["Velocity"]

    assert spec.dictionary_declaration == "[km/s]"
    assert spec.secondary_token == "[kms/s]"
    assert spec.canonical_unit == "km/s"
    assert spec.metadata_status is (
        QueueMetadataStatus.LEXICAL_VARIANT
    )


def test_secondary_row_contains_header_continuation() -> None:
    index = QUEUE_EXPECTED_COLUMNS.index("Mos. Coord.")

    assert QUEUE_EXPECTED_SECONDARY_HEADER[index] == (
        "Ref. Sys."
    )
    assert classify_secondary_token(
        "Mos. Coord.",
        "Ref. Sys.",
    ) is SecondaryTokenKind.HEADER_CONTINUATION
    assert classify_secondary_token(
        "RA",
        "[deg]",
    ) is SecondaryTokenKind.UNIT
    assert classify_secondary_token(
        "Project Code",
        "",
    ) is SecondaryTokenKind.BLANK
    assert classify_secondary_token(
        "Project Code",
        "surprise",
    ) is SecondaryTokenKind.UNEXPECTED


def test_dictionary_only_field_is_not_operational() -> None:
    assert QUEUE_DICTIONARY_ONLY_FIELDS == (
        "standAlone_ACA",
    )
    assert "standAlone_ACA" not in QUEUE_EXPECTED_COLUMNS


def test_aliases_are_explicit_not_fuzzy() -> None:
    assert QUEUE_DICTIONARY_ALIASES == {
        "Mos. Coord. Ref. Sys": "Mos. Coord.",
        "Req.LAS": "Req. LAS",
        "Spec.Res SPW [N]": "Spec.Res. SPW N",
    }


def test_snapshot_and_numeric_tolerances_are_pinned() -> None:
    assert len(QUEUE_EVIDENCE_SNAPSHOT_SHA256) == 64
    assert QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC == 1e-6
    assert QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ == (
        1e-12
    )
