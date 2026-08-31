"""Adapters and client orchestration for the ALMA Archive TAP service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pyvo.dal import TAPService
from pyvo.dal.exceptions import (
    DALAccessError,
    DALFormatError,
    DALQueryError,
)

from alma_duplicate.clients.archive_contract import (
    ArchiveQueryErrorKind,
    TapExecutionError,
    TapResponse,
)


class _PyvoResult(Protocol):
    query_status: object | None
    infos: Mapping[object, object]

    def to_table(self) -> object:
        ...


class _PyvoService(Protocol):
    def run_sync(
        self,
        query: str,
        *,
        maxrec: int,
    ) -> _PyvoResult:
        ...


class PyvoTapExecutor:
    """Translate PyVO-specific responses into ``TapResponse``."""

    def __init__(
        self,
        endpoint: str,
        *,
        service: _PyvoService | None = None,
    ) -> None:
        normalized_endpoint = endpoint.strip().rstrip("/")
        if not normalized_endpoint:
            raise ValueError("endpoint must not be blank")

        self.endpoint = normalized_endpoint
        self._service = service

    def _get_service(self) -> _PyvoService:
        if self._service is None:
            self._service = TAPService(self.endpoint)
        return self._service

    def execute(
        self,
        adql: str,
        *,
        maxrec: int,
    ) -> TapResponse:
        if not adql.strip():
            raise ValueError("adql must not be blank")
        if maxrec <= 0:
            raise ValueError("maxrec must be positive")

        try:
            result = self._get_service().run_sync(
                adql,
                maxrec=maxrec,
            )
        except DALQueryError as exc:
            raise TapExecutionError(
                ArchiveQueryErrorKind.QUERY_ERROR,
                str(exc),
            ) from exc
        except DALFormatError as exc:
            raise TapExecutionError(
                ArchiveQueryErrorKind.RESPONSE_FORMAT_ERROR,
                str(exc),
            ) from exc
        except DALAccessError as exc:
            raise TapExecutionError(
                ArchiveQueryErrorKind.SERVICE_ERROR,
                str(exc),
            ) from exc

        try:
            table = result.to_table()
            columns = tuple(
                str(column)
                for column in table.colnames
            )
            rows = tuple(
                {
                    column: table_row[column]
                    for column in columns
                }
                for table_row in table
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise TapExecutionError(
                ArchiveQueryErrorKind.RESPONSE_FORMAT_ERROR,
                f"Unable to convert TAP result table: {exc}",
            ) from exc

        return TapResponse(
            rows=rows,
            declared_columns=columns,
            query_status_raw=getattr(
                result,
                "query_status",
                None,
            ),
            warnings=_extract_info_warnings(result),
        )


def _extract_info_warnings(
    result: _PyvoResult,
) -> tuple[str, ...]:
    infos = getattr(result, "infos", {})
    if not isinstance(infos, Mapping):
        return ()

    return tuple(
        f"{key}={value}"
        for key, value in sorted(
            infos.items(),
            key=lambda item: str(item[0]),
        )
        if str(key).upper() != "QUERY_STATUS"
    )
