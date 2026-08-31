from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    ArchiveQueryProvenance,
    ArchiveQueryResult,
    ArchiveQueryStatus,
    TapResponse,
)


def _provenance(
    *,
    expected_count: int | None = 0,
    retrieved_count: int | None = 0,
) -> ArchiveQueryProvenance:
    started_at = datetime(
        2026,
        8,
        31,
        10,
        0,
        tzinfo=timezone.utc,
    )

    return ArchiveQueryProvenance(
        query_run_id="query-run-001",
        endpoint="https://example.invalid/tap",
        count_adql=(
            "SELECT COUNT(*) AS total_matches "
            "FROM ivoa.obscore"
        ),
        retrieval_adql=(
            "SELECT proposal_id "
            "FROM ivoa.obscore"
        ),
        normalized_parameters=(
            ("ra_deg", 201.365),
            ("dec_deg", -43.019),
            ("radius_deg", 0.006),
        ),
        configured_maxrec=10_000,
        started_at=started_at,
        finished_at=started_at,
        expected_count=expected_count,
        retrieved_count=retrieved_count,
        count_query_status_raw="OK",
        retrieval_query_status_raw="OK",
        query_hash="example-query-hash",
        client_version="1",
        schema_version="1",
    )


def test_archive_query_status_values_are_stable() -> None:
    assert ArchiveQueryStatus.COMPLETE == "COMPLETE"
    assert ArchiveQueryStatus.OVERFLOW == "OVERFLOW"
    assert (
        ArchiveQueryStatus.COUNT_MISMATCH
        == "COUNT_MISMATCH"
    )
    assert ArchiveQueryStatus.ERROR == "ERROR"


def test_valid_empty_result_is_complete() -> None:
    result = ArchiveQueryResult(
        status=ArchiveQueryStatus.COMPLETE,
        rows=(),
        provenance=_provenance(),
    )

    assert result.rows == ()
    assert result.is_complete
    assert result.can_reconstruct


def test_incomplete_result_preserves_partial_rows() -> None:
    row = {
        "proposal_id": "2021.A.00028.S",
    }

    result = ArchiveQueryResult(
        status=ArchiveQueryStatus.OVERFLOW,
        rows=(row,),
        provenance=_provenance(
            expected_count=2,
            retrieved_count=1,
        ),
    )

    assert result.rows == (row,)
    assert not result.is_complete
    assert not result.can_reconstruct


def test_error_result_requires_error_kind() -> None:
    with pytest.raises(
        ValueError,
        match="require an error_kind",
    ):
        ArchiveQueryResult(
            status=ArchiveQueryStatus.ERROR,
            rows=(),
            provenance=_provenance(
                expected_count=None,
                retrieved_count=None,
            ),
        )


def test_non_error_result_rejects_error_kind() -> None:
    with pytest.raises(
        ValueError,
        match="Only ERROR results",
    ):
        ArchiveQueryResult(
            status=ArchiveQueryStatus.COMPLETE,
            rows=(),
            provenance=_provenance(),
            error_kind=(
                ArchiveQueryErrorKind.SERVICE_ERROR
            ),
        )


def test_complete_result_rejects_schema_drift() -> None:
    with pytest.raises(
        ValueError,
        match="cannot have missing columns",
    ):
        ArchiveQueryResult(
            status=ArchiveQueryStatus.COMPLETE,
            rows=(),
            provenance=_provenance(),
            missing_columns=("obs_id",),
        )


def test_contract_objects_are_frozen() -> None:
    result = ArchiveQueryResult(
        status=ArchiveQueryStatus.COMPLETE,
        rows=(),
        provenance=_provenance(),
    )

    with pytest.raises(FrozenInstanceError):
        result.status = ArchiveQueryStatus.ERROR


def test_empty_tap_response_preserves_schema() -> None:
    response = TapResponse(
        rows=(),
        declared_columns=(
            "proposal_id",
            "obs_id",
        ),
        query_status_raw="OK",
    )

    assert response.rows == ()
    assert response.declared_columns == (
        "proposal_id",
        "obs_id",
    )