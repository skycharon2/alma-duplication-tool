from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from astropy.table import Table

from alma_duplicate.clients.archive_adapter import (
    ADAPTER_VERSION,
    IncompleteArchiveQueryError,
    run_archive_pipeline,
)
from alma_duplicate.clients.archive_client import (
    ArchiveClient,
)
from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    ArchiveQueryStatus,
    TapFieldMetadata,
    TapResponse,
)
from alma_duplicate.clients.archive_queries import (
    ArchiveQuerySpec,
)
from alma_duplicate.domain.normalization import (
    MissingValueStatus,
    PublisherDidMappingStatus,
    TimestampParseStatus,
)
from alma_duplicate.domain.reconstruction import (
    ReconstructionStatus,
    SupportMappingStatus,
)
from alma_duplicate.reconstruction import (
    reconstruct_archive_rows,
)
from tests.fakes import FakeTapExecutor

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "archive"
    / "archive_pipeline_v04.ecsv"
)


def _field_metadata(
    columns: tuple[str, ...],
    *,
    unit_overrides: dict[str, str | None] | None = None,
) -> tuple[TapFieldMetadata, ...]:
    units = {
        "frequency": "GHz",
        "bandwidth": "Hz",
        "spectral_resolution": "kHz",
        "spatial_resolution": "arcsec",
        "sensitivity_10kms": "mJy / beam",
        "cont_sensitivity_bandwidth": "mJy / beam",
    }
    numeric_fields = frozenset(units)
    effective_units = units | (unit_overrides or {})
    return tuple(
        TapFieldMetadata(
            name=column,
            datatype=(
                "double"
                if column in numeric_fields
                else "char"
            ),
            arraysize=(
                None
                if column in numeric_fields
                else "*"
            ),
            unit=effective_units.get(column),
            ucd=None,
            utype=None,
            xtype=None,
            description=f"Fixture metadata for {column}",
        )
        for column in columns
    )


def _fixture_rows() -> tuple[dict[str, object], ...]:
    table = Table.read(
        FIXTURE_PATH,
        format="ascii.ecsv",
    )

    return tuple(
        {
            column: table_row[column]
            for column in table.colnames
        }
        for table_row in table
    )


def _complete_query_result(
    *,
    frequency_unit: str = "GHz",
    frequency_scale: float = 1.0,
):
    rows = _fixture_rows()
    if frequency_scale != 1.0:
        rows = tuple(
            {
                **row,
                "frequency": (
                    float(row["frequency"]) * frequency_scale
                ),
            }
            for row in rows
        )
    declared_columns = tuple(rows[0])
    executor = FakeTapExecutor(
        [
            TapResponse(
                rows=(
                    {
                        "total_matches": len(rows),
                    },
                ),
                declared_columns=("total_matches",),
                field_metadata=_field_metadata(
                    ("total_matches",)
                ),
                query_status_raw="OK",
            ),
            TapResponse(
                rows=rows,
                declared_columns=declared_columns,
                field_metadata=_field_metadata(
                    declared_columns,
                    unit_overrides={
                        "frequency": frequency_unit,
                    },
                ),
                query_status_raw="OK",
            ),
        ]
    )
    timestamp = datetime(
        2026,
        8,
        31,
        10,
        0,
        tzinfo=UTC,
    )
    client = ArchiveClient(
        "https://example.invalid/tap",
        executor=executor,
        maxrec=100,
        clock=lambda: timestamp,
        run_id_factory=lambda: "fixture-query-run",
    )

    return client.search(
        ArchiveQuerySpec(
            ra_deg=201.365,
            dec_deg=-43.019,
            radius_deg=0.006,
        )
    )


def test_complete_fixture_runs_full_pipeline() -> None:
    query_result = _complete_query_result()
    pipeline = run_archive_pipeline(query_result)

    assert query_result.status is (
        ArchiveQueryStatus.COMPLETE
    )
    assert pipeline.query_result.field_metadata == (
        query_result.field_metadata
    )
    assert len(pipeline.query_result.field_metadata) == 23
    assert len(pipeline.prepared_rows) == 5
    assert pipeline.field_contract.is_usable
    assert pipeline.comparison_units_safe
    assert pipeline.adapter_version == ADAPTER_VERSION == "3"
    assert pipeline.reconstruction.linked_row_count == 4
    assert pipeline.reconstruction.unlinked_row_count == 1

    observed_pairs = {
        (
            association.context.source_name,
            association.spw_index,
        )
        for association in (
            pipeline.reconstruction.associations
        )
    }

    assert ("SourceA", 0) in observed_pairs
    assert ("SourceA", 2) in observed_pairs
    assert ("SourceA", 1) not in observed_pairs

    brace_mappings = [
        mapping
        for mapping in (
            pipeline.reconstruction.support_mappings
        )
        if (
            mapping.association_key is not None
            and mapping.association_key.context.source_name
            == "SourceB"
        )
    ]

    assert len(brace_mappings) == 2
    assert {
        mapping.status
        for mapping in brace_mappings
    } == {SupportMappingStatus.ASSIGNED}
    assert {
        mapping.component_index
        for mapping in brace_mappings
    } == {1}

    unsafe_rows = [
        reconstruction
        for reconstruction in (
            pipeline.reconstruction.row_reconstructions
        )
        if reconstruction.status is (
            ReconstructionStatus.OBS_ID_UNSAFE
        )
    ]
    assert len(unsafe_rows) == 1


def test_normalization_preserves_raw_and_status() -> None:
    pipeline = run_archive_pipeline(
        _complete_query_result()
    )

    first = pipeline.prepared_rows[0]
    mismatch = pipeline.prepared_rows[2]

    assert str(first.raw_row["group_ous_uid"]).strip() == ""
    assert first.normalized_metadata.group_ous_uid.value is None
    assert (
        first.normalized_metadata.group_ous_uid.missing_status
        is MissingValueStatus.BLANK_NORMALIZED
    )
    assert (
        first.normalized_metadata.obs_release_date.status
        is TimestampParseStatus.SENTINEL_3000_DATE
    )
    assert first.normalized_metadata.obs_release_date.value is None
    assert (
        mismatch.normalized_metadata.publisher_did.status
        is PublisherDidMappingStatus.MISMATCH
    )
    assert first.raw_row_id == (
        "fixture-query-run:00000000"
    )
    assert first.comparison_evidence.unit_safe
    assert first.comparison_evidence.has_frequency_coverage
    assert first.comparison_evidence.frequency.lower_ghz == (
        pytest.approx(99.9)
    )
    assert first.comparison_evidence.frequency.upper_ghz == (
        pytest.approx(100.1)
    )
    assert (
        first.comparison_evidence.cross_source_frequency_ready
        is False
    )


def test_reconstruction_uses_canonical_tap_frequency_unit() -> None:
    pipeline = run_archive_pipeline(
        _complete_query_result(
            frequency_unit="MHz",
            frequency_scale=1000.0,
        )
    )

    first = pipeline.prepared_rows[0]
    assert first.raw_row["frequency"] == pytest.approx(100_000.0)
    assert (
        first.comparison_evidence.frequency.centre.source_unit
        == "MHz"
    )
    assert (
        first.comparison_evidence.frequency.centre.canonical_value
        == pytest.approx(100.0)
    )
    assert first.reconstruction_input.frequency_ghz == pytest.approx(
        100.0
    )
    assert pipeline.reconstruction.linked_row_count == 4
    assert pipeline.reconstruction.unlinked_row_count == 1
    assert {
        mapping.status
        for mapping in pipeline.reconstruction.support_mappings
        if mapping.association_key is not None
    } == {SupportMappingStatus.ASSIGNED}


def test_reconstruction_remains_shuffle_invariant() -> None:
    pipeline = run_archive_pipeline(
        _complete_query_result()
    )
    reversed_inputs = tuple(
        prepared.reconstruction_input
        for prepared in reversed(
            pipeline.prepared_rows
        )
    )

    assert reconstruct_archive_rows(
        reversed_inputs
    ) == pipeline.reconstruction


@pytest.mark.parametrize(
    ("status", "error_kind"),
    [
        (ArchiveQueryStatus.OVERFLOW, None),
        (ArchiveQueryStatus.COUNT_MISMATCH, None),
        (
            ArchiveQueryStatus.ERROR,
            ArchiveQueryErrorKind.SERVICE_ERROR,
        ),
    ],
)
def test_incomplete_results_cannot_enter_pipeline(
    status: ArchiveQueryStatus,
    error_kind: ArchiveQueryErrorKind | None,
) -> None:
    complete = _complete_query_result()
    incomplete = replace(
        complete,
        status=status,
        error_kind=error_kind,
        error_message=(
            "fixture error"
            if status is ArchiveQueryStatus.ERROR
            else None
        ),
    )

    with pytest.raises(
        IncompleteArchiveQueryError,
        match="cannot enter reconstruction",
    ):
        run_archive_pipeline(incomplete)
