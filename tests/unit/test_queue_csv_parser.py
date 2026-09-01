from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from alma_duplicate.domain.queue import (
    QueueIssueKind,
    QueueMosaicKind,
    QueueParseStatus,
    QueueUnitInterpretation,
    RegularSpwEvidence,
    SpectralScanEvidence,
)
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "queue"
    / "queue_pipeline_v1.csv"
)


def _records() -> list[list[str]]:
    with FIXTURE_PATH.open(
        newline="",
        encoding="utf-8-sig",
    ) as stream:
        return list(csv.reader(stream))


def _render(records: list[list[str]]) -> bytes:
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(records)
    return stream.getvalue().encode("utf-8")


def _indices(records: list[list[str]]) -> dict[str, int]:
    return {
        name: index
        for index, name in enumerate(records[39])
    }


def _parse_fixture():
    return parse_queue_csv_bytes(FIXTURE_PATH.read_bytes())


def test_fixture_preserves_layout_metadata_and_raw_rows() -> None:
    result = _parse_fixture()

    assert result.status is QueueParseStatus.COMPLETE_WITH_WARNINGS
    assert len(result.snapshot.operational_columns) == 79
    assert len(result.snapshot.secondary_header_row) == 79
    assert len(result.snapshot.dictionary_entries) == 35
    assert len(result.field_metadata) == 79
    assert len(result.raw_rows) == 13
    assert len(result.row_inputs) == 13
    assert result.can_reconstruct
    assert [issue.kind for issue in result.issues] == [
        QueueIssueKind.CONFLICTING_UNIT_DECLARATION
    ]

    first = result.raw_rows[0]
    assert first.row_id.physical_start_line == 42
    assert first.value("Project Code") == "2024.1.00750.S"
    assert first.value("Lat Offset") == (
        "-4.7231237019733225e-11"
    )


def test_regular_spws_are_joined_only_by_slot_number() -> None:
    result = _parse_fixture()
    regular = result.row_inputs[0].spectral

    assert isinstance(regular, RegularSpwEvidence)
    assert [spw.number for spw in regular.spws] == [1, 2, 3, 4]
    assert regular.spws[0].frequency_ghz.value == pytest.approx(
        350.4999999999
    )
    assert regular.spws[0].bandwidth_mhz.value == 1875.0
    assert regular.spws[0].spectral_resolution_mhz.value == (
        15.6240234375
    )
    assert regular.sensitivity.reference_width_mhz.value == 7500.0


def test_sps_unit_conflict_is_preserved_and_resolved_explicitly() -> None:
    result = _parse_fixture()
    spectral = result.row_inputs[1].spectral

    assert isinstance(spectral, SpectralScanEvidence)
    bandwidth = spectral.per_window_bandwidth_mhz
    assert bandwidth.raw_text == "1000.0"
    assert bandwidth.raw_value == 1000.0
    assert bandwidth.value == 1000.0
    assert bandwidth.dictionary_unit == "[MHz]"
    assert bandwidth.secondary_unit == "[GHz]"
    assert bandwidth.canonical_unit == "MHz"
    assert bandwidth.unit_interpretation is (
        QueueUnitInterpretation.DICTIONARY_OVERRIDE
    )
    assert bandwidth.normalization_version == "1"
    assert spectral.lower_sky_frequency_ghz == 261.5
    assert spectral.upper_sky_frequency_ghz == 268.7
    assert spectral.window_expansion_status == "UNAVAILABLE"


def test_mosaic_tolerance_classifies_center_and_offset() -> None:
    result = _parse_fixture()
    center = result.row_inputs[3].spatial
    offset = result.row_inputs[4].spatial

    assert center.mosaic_kind is QueueMosaicKind.CUSTOM_POINTING
    assert center.zero_tolerance_arcsec == 1e-6
    assert abs(center.long_offset_arcsec.value) < 1e-6
    assert abs(center.lat_offset_arcsec.value) < 1e-6
    assert abs(offset.long_offset_arcsec.value) > 1e-6


def test_exact_duplicate_rows_keep_distinct_source_identity() -> None:
    result = _parse_fixture()
    first, second = result.raw_rows[5:7]

    assert first.raw_values == second.raw_values
    assert first.content_fingerprint == second.content_fingerprint
    assert first.row_id != second.row_id
    assert first.row_id.physical_start_line == 47
    assert second.row_id.physical_start_line == 48


def test_zero_requested_las_is_valid_source_evidence() -> None:
    records = _records()
    columns = _indices(records)
    records[41][columns["Req. LAS"]] = "0.0"

    result = parse_queue_csv_bytes(_render(records))

    assert result.is_complete
    assert result.row_inputs[0].request.requested_las_arcsec.value == 0.0


def test_partial_spw_triple_is_an_error() -> None:
    records = _records()
    columns = _indices(records)
    records[41][columns["Bandwidth SPW 1"]] = ""

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert QueueIssueKind.PARTIAL_SPW_TRIPLE in {
        issue.kind for issue in result.issues
    }


def test_partial_sps_record_is_an_error() -> None:
    records = _records()
    columns = _indices(records)
    records[42][columns["SPS Bandwidth"]] = ""

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert QueueIssueKind.PARTIAL_SPS_RECORD in {
        issue.kind for issue in result.issues
    }


def test_regular_and_sps_evidence_cannot_share_a_row() -> None:
    records = _records()
    columns = _indices(records)
    for column, value in {
        "SPS Start Freq.": "330",
        "SPS End Freq.": "360",
        "SPS Bandwidth": "1000",
        "SPS Spec. Res.": "0.5",
    }.items():
        records[41][columns[column]] = value

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert QueueIssueKind.MIXED_REGULAR_AND_SPS in {
        issue.kind for issue in result.issues
    }


def test_reference_frequency_must_lie_in_derived_coverage() -> None:
    records = _records()
    columns = _indices(records)
    records[41][columns["Ref.Frequency"]] = "1.0"

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert QueueIssueKind.REFERENCE_FREQUENCY_OUTSIDE_COVERAGE in {
        issue.kind for issue in result.issues
    }


def test_rectangle_requires_complete_geometry() -> None:
    records = _records()
    columns = _indices(records)
    records[43][columns["Mos. Length"]] = ""

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert QueueIssueKind.INCOMPLETE_RECTANGLE_GEOMETRY in {
        issue.kind for issue in result.issues
    }


def test_noncontiguous_spw_slots_are_preserved_with_warning() -> None:
    records = _records()
    columns = _indices(records)
    for column in (
        "Freq SPW 2",
        "Bandwidth SPW 2",
        "Spec.Res. SPW 2",
    ):
        records[41][columns[column]] = ""

    result = parse_queue_csv_bytes(_render(records))

    assert result.is_complete
    assert QueueIssueKind.NONCONTIGUOUS_SPW_SLOTS in {
        issue.kind for issue in result.issues
    }
    spectral = result.row_inputs[0].spectral
    assert isinstance(spectral, RegularSpwEvidence)
    assert [spw.number for spw in spectral.spws] == [1, 3, 4]


def test_changed_unit_is_schema_drift() -> None:
    records = _records()
    columns = _indices(records)
    records[40][columns["RA"]] = "[rad]"

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert QueueIssueKind.METADATA_DECLARATION_DRIFT in {
        issue.kind for issue in result.issues
    }


def test_missing_dictionary_only_field_is_schema_drift() -> None:
    records = _records()
    dictionary_row = next(
        index
        for index, record in enumerate(records)
        if record and record[0] == "standAlone_ACA"
    )
    records.pop(dictionary_row)

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert any(
        issue.kind is QueueIssueKind.METADATA_DECLARATION_DRIFT
        and issue.column == "standAlone_ACA"
        for issue in result.issues
    )


def test_known_reordered_columns_are_read_by_name() -> None:
    records = _records()
    columns = _indices(records)
    left = columns["RA"]
    right = columns["Dec"]
    for record in records[39:]:
        record[left], record[right] = record[right], record[left]

    result = parse_queue_csv_bytes(_render(records))

    assert result.is_complete
    assert QueueIssueKind.REORDERED_COLUMNS in {
        issue.kind for issue in result.issues
    }
    assert result.row_inputs[0].spatial.ra_deg.value == pytest.approx(
        253.24541666666667
    )


def test_row_width_mismatch_blocks_reconstruction() -> None:
    records = _records()
    records[41].pop()

    result = parse_queue_csv_bytes(_render(records))

    assert result.status is QueueParseStatus.ERROR
    assert not result.can_reconstruct
    assert QueueIssueKind.ROW_WIDTH_MISMATCH in {
        issue.kind for issue in result.issues
    }
