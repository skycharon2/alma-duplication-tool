from __future__ import annotations

from datetime import datetime, timezone

import pytest

from alma_duplicate.clients.archive_client import (
    ArchiveClient,
)
from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    ArchiveQueryStatus,
    TapExecutionError,
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
    tzinfo=timezone.utc,
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
        query_status_raw=status,
        warnings=("retrieval fixture",),
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
    assert result.provenance.warnings == (
        "count fixture",
        "retrieval fixture",
    )
    assert executor.calls[0].maxrec == 1
    assert executor.calls[1].maxrec == 10_000
    assert "COUNT(*)" in executor.calls[0].adql
    assert "COUNT(*)" not in executor.calls[1].adql
    assert executor.remaining_action_count == 0


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
