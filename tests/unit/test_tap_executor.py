from __future__ import annotations

from dataclasses import dataclass

import pytest
from pyvo.dal.exceptions import DALQueryError

from alma_duplicate.clients.archive_client import (
    PyvoTapExecutor,
)
from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    TapExecutionError,
)


@dataclass(frozen=True)
class _FakeField:
    name: str
    datatype: str
    arraysize: str | None = None
    unit: str | None = None
    ucd: str | None = None
    utype: str | None = None
    xtype: str | None = None
    description: str | None = None


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
    fielddescs = (
        _FakeField(
            name="proposal_id",
            datatype="char",
            arraysize="*",
            ucd="meta.id;obs.proposal",
            description="Project code",
        ),
        _FakeField(
            name="obs_id",
            datatype="char",
            arraysize="*",
            utype="  archive:ObservationID  ",
            description="  Observation identifier  ",
        ),
    )

    def to_table(self) -> _FakeTable:
        return _FakeTable()


class _EmptyFakeTable(_FakeTable):
    def __iter__(self):
        return iter(())


class _EmptyFakeResult(_FakeResult):
    def to_table(self) -> _EmptyFakeTable:
        return _EmptyFakeTable()


class _MismatchedMetadataResult(_FakeResult):
    fielddescs = (
        _FakeField(
            name="wrong_name",
            datatype="char",
        ),
    )


class _FakeService:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        result: _FakeResult | None = None,
    ) -> None:
        self.error = error
        self.result = result or _FakeResult()
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
        return self.result


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
    assert response.field_metadata[0].name == "proposal_id"
    assert response.field_metadata[0].datatype == "char"
    assert response.field_metadata[0].arraysize == "*"
    assert response.field_metadata[0].unit is None
    assert response.field_metadata[0].ucd == (
        "meta.id;obs.proposal"
    )
    assert response.field_metadata[0].description == (
        "Project code"
    )
    assert response.field_metadata[1].utype == (
        "  archive:ObservationID  "
    )
    assert response.field_metadata[1].description == (
        "  Observation identifier  "
    )
    assert response.warnings == (
        "NOTE=offline fixture",
    )


def test_zero_row_result_preserves_field_metadata() -> None:
    executor = PyvoTapExecutor(
        "https://example.invalid/tap",
        service=_FakeService(result=_EmptyFakeResult()),
    )

    response = executor.execute(
        "SELECT proposal_id, obs_id FROM ivoa.obscore",
        maxrec=25,
    )

    assert response.rows == ()
    assert tuple(
        field.name
        for field in response.field_metadata
    ) == response.declared_columns


def test_misaligned_field_metadata_is_format_error() -> None:
    executor = PyvoTapExecutor(
        "https://example.invalid/tap",
        service=_FakeService(
            result=_MismatchedMetadataResult()
        ),
    )

    with pytest.raises(TapExecutionError) as caught:
        executor.execute(
            "SELECT proposal_id, obs_id FROM ivoa.obscore",
            maxrec=25,
        )

    assert caught.value.kind is (
        ArchiveQueryErrorKind.RESPONSE_FORMAT_ERROR
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
