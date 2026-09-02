from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alma_duplicate.clients.archive_client import (
    ArchiveClient,
)
from alma_duplicate.clients.archive_contract import (
    ArchiveAngularResolutionPrefilterStatus,
    ArchiveFrequencyPrefilterStatus,
    ArchiveQueryErrorKind,
    ArchiveQueryStatus,
    TapExecutionError,
    TapFieldMetadata,
    TapResponse,
)
from alma_duplicate.clients.archive_queries import (
    ARCHIVE_SELECTED_COLUMNS,
    COUNT_ALIAS,
    ArchiveQuerySpec,
)
from tests.fakes import FakeTapExecutor

NOW = datetime(
    2026,
    8,
    31,
    10,
    0,
    tzinfo=UTC,
)


def _field_metadata(
    columns: tuple[str, ...],
) -> tuple[TapFieldMetadata, ...]:
    return tuple(
        TapFieldMetadata(
            name=column,
            datatype="char",
            arraysize="*",
            unit=None,
            ucd=None,
            utype=None,
            xtype=None,
            description=f"Metadata for {column}",
        )
        for column in columns
    )


def _spec() -> ArchiveQuerySpec:
    return ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
    )


def _count_response(
    count: object,
    *,
    status: object | None = "OK",
    row_count: int = 1,
    declared_columns: tuple[str, ...] = (
        COUNT_ALIAS,
    ),
) -> TapResponse:
    rows = tuple(
        {COUNT_ALIAS: count}
        for _ in range(row_count)
    )

    return TapResponse(
        rows=rows,
        declared_columns=declared_columns,
        field_metadata=_field_metadata(
            declared_columns
        ),
        query_status_raw=status,
        warnings=("count fixture",),
    )


def _archive_row(index: int) -> dict[str, object]:
    row = {
        column: None
        for column in ARCHIVE_SELECTED_COLUMNS
    }
    row.update(
        {
            "proposal_id": "2021.A.00028.S",
            "obs_id": f"fixture-row-{index}",
        }
    )
    return row


def _retrieval_response(
    count: int,
    *,
    status: object | None = "OK",
    declared_columns: tuple[str, ...] = (
        ARCHIVE_SELECTED_COLUMNS
    ),
) -> TapResponse:
    return TapResponse(
        rows=tuple(
            _archive_row(index)
            for index in range(count)
        ),
        declared_columns=declared_columns,
        field_metadata=_field_metadata(
            declared_columns
        ),
        query_status_raw=status,
        warnings=("retrieval fixture",),
    )


def _query_unit_response(
    *,
    frequency_unit: str = "GHz",
    bandwidth_unit: str = "Hz",
    status: object | None = "OK",
    include_bandwidth: bool = True,
    spatial_resolution_unit: str | None = None,
) -> TapResponse:
    columns = ("column_name", "datatype", "unit")
    rows = [
        {
            "column_name": "frequency",
            "datatype": "double",
            "unit": frequency_unit,
        }
    ]
    if include_bandwidth:
        rows.append(
            {
                "column_name": "bandwidth",
                "datatype": "double",
                "unit": bandwidth_unit,
            }
        )
    if spatial_resolution_unit is not None:
        rows.append(
            {
                "column_name": "spatial_resolution",
                "datatype": "double",
                "unit": spatial_resolution_unit,
            }
        )
    return TapResponse(
        rows=tuple(rows),
        declared_columns=columns,
        field_metadata=_field_metadata(columns),
        query_status_raw=status,
        warnings=("unit metadata fixture",),
    )


def _frequency_spec() -> ArchiveQuerySpec:
    return ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        frequency_min_ghz=229.0,
        frequency_max_ghz=231.0,
    )


def _angular_spec() -> ArchiveQuerySpec:
    return ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        angular_resolution_min_arcsec=0.1,
        angular_resolution_max_arcsec=1.5,
    )


def _combined_prefilter_spec() -> ArchiveQuerySpec:
    return ArchiveQuerySpec(
        ra_deg=201.365,
        dec_deg=-43.019,
        radius_deg=0.006,
        frequency_min_ghz=229.0,
        frequency_max_ghz=231.0,
        angular_resolution_min_arcsec=0.1,
        angular_resolution_max_arcsec=1.5,
    )


def _client(
    actions: list[TapResponse | TapExecutionError],
    *,
    maxrec: int = 10_000,
) -> tuple[ArchiveClient, FakeTapExecutor]:
    executor = FakeTapExecutor(actions)
    client = ArchiveClient(
        "https://example.invalid/tap/",
        executor=executor,
        maxrec=maxrec,
        clock=lambda: NOW,
        run_id_factory=lambda: "query-run-001",
    )
    return client, executor


def test_complete_result_reconciles_count_and_rows() -> None:
    client, executor = _client(
        [
            _count_response(2),
            _retrieval_response(2),
        ]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.is_complete
    assert len(result.rows) == 2
    assert result.provenance.expected_count == 2
    assert result.provenance.retrieved_count == 2
    assert result.provenance.query_run_id == (
        "query-run-001"
    )
    assert len(result.provenance.query_hash) == 64
    assert result.provenance.client_version == "4"
    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus.NOT_REQUESTED
    )
    assert result.provenance.angular_resolution_prefilter_status is (
        ArchiveAngularResolutionPrefilterStatus.NOT_REQUESTED
    )
    assert result.provenance.warnings == (
        "count fixture",
        "retrieval fixture",
    )
    assert tuple(
        field.name
        for field in result.field_metadata
    ) == ARCHIVE_SELECTED_COLUMNS
    assert executor.calls[0].maxrec == 1
    assert executor.calls[1].maxrec == 10_000
    assert "COUNT(*)" in executor.calls[0].adql
    assert "COUNT(*)" not in executor.calls[1].adql
    assert executor.remaining_action_count == 0


def test_frequency_prefilter_runs_only_after_exact_unit_probe() -> None:
    client, executor = _client(
        [
            _query_unit_response(),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_frequency_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus.VERIFIED_EXACT_UNITS
    )
    assert len(result.provenance.query_unit_metadata) == 2
    assert "TAP_SCHEMA.columns" in executor.calls[0].adql
    assert "bandwidth / 1000000000.0" in executor.calls[1].adql
    assert "bandwidth / 1000000000.0" in executor.calls[2].adql


def test_frequency_unit_mismatch_falls_back_to_spatial_query() -> None:
    client, executor = _client(
        [
            _query_unit_response(frequency_unit="MHz"),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_frequency_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus.FALLBACK_UNIT_MISMATCH
    )
    assert "bandwidth / 1000000000.0" not in executor.calls[1].adql
    assert "bandwidth / 1000000000.0" not in executor.calls[2].adql
    assert dict(result.provenance.normalized_parameters)[
        "frequency_min_ghz"
    ] == 229.0


def test_incomplete_query_metadata_falls_back_to_spatial_query() -> None:
    client, executor = _client(
        [
            _query_unit_response(include_bandwidth=False),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_frequency_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus.FALLBACK_METADATA_INCOMPLETE
    )
    assert "bandwidth / 1000000000.0" not in executor.calls[1].adql


def test_query_metadata_error_falls_back_to_spatial_query() -> None:
    client, executor = _client(
        [
            TapExecutionError(
                ArchiveQueryErrorKind.SERVICE_ERROR,
                "metadata unavailable",
            ),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_frequency_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus
        .FALLBACK_METADATA_QUERY_ERROR
    )
    assert "bandwidth / 1000000000.0" not in executor.calls[1].adql


def test_angular_prefilter_runs_only_after_exact_unit_probe() -> None:
    client, executor = _client(
        [
            _query_unit_response(
                include_bandwidth=False,
                spatial_resolution_unit="arcsec",
            ),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_angular_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.provenance.angular_resolution_prefilter_status is (
        ArchiveAngularResolutionPrefilterStatus.VERIFIED_EXACT_UNITS
    )
    assert len(result.provenance.query_unit_metadata) == 2
    assert "'spatial_resolution'" in executor.calls[0].adql
    assert "spatial_resolution >= 0.1" in executor.calls[1].adql
    assert "spatial_resolution >= 0.1" in executor.calls[2].adql


def test_angular_unit_mismatch_falls_back_without_losing_request() -> None:
    client, executor = _client(
        [
            _query_unit_response(
                include_bandwidth=False,
                spatial_resolution_unit="mas",
            ),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_angular_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.provenance.angular_resolution_prefilter_status is (
        ArchiveAngularResolutionPrefilterStatus.FALLBACK_UNIT_MISMATCH
    )
    assert "spatial_resolution >=" not in executor.calls[1].adql
    assert "spatial_resolution >=" not in executor.calls[2].adql
    assert dict(result.provenance.normalized_parameters)[
        "angular_resolution_min_arcsec"
    ] == 0.1


def test_combined_prefilters_are_gated_independently() -> None:
    client, executor = _client(
        [
            _query_unit_response(
                spatial_resolution_unit="mas",
            ),
            _count_response(1),
            _retrieval_response(1),
        ]
    )

    result = client.search(_combined_prefilter_spec())

    assert result.provenance.frequency_prefilter_status is (
        ArchiveFrequencyPrefilterStatus.VERIFIED_EXACT_UNITS
    )
    assert result.provenance.angular_resolution_prefilter_status is (
        ArchiveAngularResolutionPrefilterStatus.FALLBACK_UNIT_MISMATCH
    )
    assert "bandwidth / 1000000000.0" in executor.calls[1].adql
    assert "spatial_resolution >=" not in executor.calls[1].adql


def test_valid_empty_result_is_complete() -> None:
    client, _ = _client(
        [
            _count_response(0),
            _retrieval_response(0),
        ]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.COMPLETE
    assert result.rows == ()
    assert result.provenance.expected_count == 0
    assert result.provenance.retrieved_count == 0
    assert len(result.field_metadata) == len(
        ARCHIVE_SELECTED_COLUMNS
    )
    assert result.can_reconstruct


def test_overflow_preserves_partial_rows() -> None:
    client, _ = _client(
        [
            _count_response(10),
            _retrieval_response(5, status="OVERFLOW"),
        ],
        maxrec=5,
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.OVERFLOW
    assert len(result.rows) == 5
    assert len(result.field_metadata) == len(
        ARCHIVE_SELECTED_COLUMNS
    )
    assert not result.can_reconstruct


@pytest.mark.parametrize(
    ("expected_count", "retrieved_count"),
    [
        (3, 2),
        (2, 3),
    ],
)
def test_count_mismatch_is_not_complete(
    expected_count: int,
    retrieved_count: int,
) -> None:
    client, _ = _client(
        [
            _count_response(expected_count),
            _retrieval_response(retrieved_count),
        ]
    )

    result = client.search(_spec())

    assert result.status is (
        ArchiveQueryStatus.COUNT_MISMATCH
    )
    assert len(result.field_metadata) == len(
        ARCHIVE_SELECTED_COLUMNS
    )
    assert not result.can_reconstruct


def test_schema_drift_is_structured_error() -> None:
    columns = tuple(
        column
        for column in ARCHIVE_SELECTED_COLUMNS
        if column != "obs_id"
    )
    client, _ = _client(
        [
            _count_response(1),
            _retrieval_response(
                1,
                declared_columns=columns,
            ),
        ]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.SCHEMA_DRIFT
    )
    assert result.missing_columns == ("obs_id",)
    assert len(result.rows) == 1
    assert tuple(
        field.name
        for field in result.field_metadata
    ) == columns
    assert not result.can_reconstruct


@pytest.mark.parametrize("status", [None, "UNKNOWN"])
def test_unknown_retrieval_status_is_error(
    status: object | None,
) -> None:
    client, _ = _client(
        [
            _count_response(1),
            _retrieval_response(1, status=status),
        ]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.UNKNOWN_QUERY_STATUS
    )
    assert len(result.field_metadata) == len(
        ARCHIVE_SELECTED_COLUMNS
    )


@pytest.mark.parametrize(
    "count_response",
    [
        _count_response("2"),
        _count_response(-1),
        _count_response(2, row_count=0),
        _count_response(2, row_count=2),
        _count_response(
            2,
            declared_columns=("wrong_name",),
        ),
    ],
)
def test_invalid_count_response_is_error(
    count_response: TapResponse,
) -> None:
    client, executor = _client([count_response])

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.INVALID_COUNT
    )
    assert len(executor.calls) == 1


def test_missing_count_status_is_error() -> None:
    client, executor = _client(
        [_count_response(2, status=None)]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.UNKNOWN_QUERY_STATUS
    )
    assert len(executor.calls) == 1


def test_count_overflow_is_invalid_count() -> None:
    client, executor = _client(
        [_count_response(2, status="OVERFLOW")]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.INVALID_COUNT
    )
    assert len(executor.calls) == 1


def test_count_execution_failure_is_error() -> None:
    client, _ = _client(
        [
            TapExecutionError(
                ArchiveQueryErrorKind.SERVICE_ERROR,
                "service unavailable",
            )
        ]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.SERVICE_ERROR
    )
    assert result.provenance.expected_count is None
    assert result.provenance.retrieved_count is None
    assert result.field_metadata == ()


def test_retrieval_execution_failure_preserves_count() -> None:
    client, _ = _client(
        [
            _count_response(2),
            TapExecutionError(
                ArchiveQueryErrorKind.QUERY_ERROR,
                "retrieval query failed",
            ),
        ]
    )

    result = client.search(_spec())

    assert result.status is ArchiveQueryStatus.ERROR
    assert result.error_kind is (
        ArchiveQueryErrorKind.QUERY_ERROR
    )
    assert result.provenance.expected_count == 2
    assert result.provenance.retrieved_count is None
    assert result.field_metadata == ()
