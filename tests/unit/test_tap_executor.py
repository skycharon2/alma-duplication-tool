from __future__ import annotations

import pytest
from pyvo.dal.exceptions import DALQueryError

from alma_duplicate.clients.archive_client import (
    PyvoTapExecutor,
)
from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    TapExecutionError,
)


class _FakeTable:
    colnames = ("proposal_id", "obs_id")

    def __iter__(self):
        return iter(
            (
                {
                    "proposal_id": "2021.A.00028.S",
                    "obs_id": "example-observation",
                },
            )
        )


class _FakeResult:
    query_status = "OK"
    infos = {
        "QUERY_STATUS": "OK",
        "NOTE": "offline fixture",
    }

    def to_table(self) -> _FakeTable:
        return _FakeTable()


class _FakeService:
    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def run_sync(
        self,
        query: str,
        *,
        maxrec: int,
    ) -> _FakeResult:
        self.calls.append((query, maxrec))
        if self.error is not None:
            raise self.error
        return _FakeResult()


def test_executor_converts_pyvo_result_without_network() -> None:
    service = _FakeService()
    executor = PyvoTapExecutor(
        "https://example.invalid/tap/",
        service=service,
    )

    response = executor.execute(
        "SELECT proposal_id, obs_id FROM ivoa.obscore",
        maxrec=25,
    )

    assert service.calls == [
        (
            "SELECT proposal_id, obs_id FROM ivoa.obscore",
            25,
        )
    ]
    assert response.query_status_raw == "OK"
    assert response.declared_columns == (
        "proposal_id",
        "obs_id",
    )
    assert response.rows[0]["proposal_id"] == (
        "2021.A.00028.S"
    )
    assert response.warnings == (
        "NOTE=offline fixture",
    )


def test_executor_normalizes_endpoint() -> None:
    executor = PyvoTapExecutor(
        " https://example.invalid/tap/ ",
        service=_FakeService(),
    )

    assert executor.endpoint == (
        "https://example.invalid/tap"
    )


def test_query_error_is_translated() -> None:
    service = _FakeService(
        error=DALQueryError("invalid ADQL")
    )
    executor = PyvoTapExecutor(
        "https://example.invalid/tap",
        service=service,
    )

    with pytest.raises(TapExecutionError) as caught:
        executor.execute(
            "INVALID QUERY",
            maxrec=1,
        )

    assert caught.value.kind is (
        ArchiveQueryErrorKind.QUERY_ERROR
    )


def test_executor_rejects_invalid_local_arguments() -> None:
    executor = PyvoTapExecutor(
        "https://example.invalid/tap",
        service=_FakeService(),
    )

    with pytest.raises(ValueError, match="adql"):
        executor.execute(" ", maxrec=1)

    with pytest.raises(ValueError, match="maxrec"):
        executor.execute("SELECT 1", maxrec=0)
