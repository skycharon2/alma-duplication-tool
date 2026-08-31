"""Contracts for safe ALMA Archive TAP query execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypeAlias


ParameterScalar: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
)

NormalizedParameters: TypeAlias = tuple[
    tuple[str, ParameterScalar],
    ...,
]

RawArchiveRow: TypeAlias = Mapping[str, object]


class ArchiveQueryStatus(StrEnum):
    """Final completeness status of one Archive query run."""

    COMPLETE = "COMPLETE"
    OVERFLOW = "OVERFLOW"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    ERROR = "ERROR"


class ArchiveQueryErrorKind(StrEnum):
    """Structured reason for an Archive query error."""

    SERVICE_ERROR = "SERVICE_ERROR"
    QUERY_ERROR = "QUERY_ERROR"
    RESPONSE_FORMAT_ERROR = "RESPONSE_FORMAT_ERROR"
    INVALID_COUNT = "INVALID_COUNT"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    UNKNOWN_QUERY_STATUS = "UNKNOWN_QUERY_STATUS"


@dataclass(frozen=True, slots=True)
class ArchiveQueryProvenance:
    """Traceable evidence for one COUNT-and-retrieval run."""

    query_run_id: str
    endpoint: str
    count_adql: str
    retrieval_adql: str
    normalized_parameters: NormalizedParameters
    configured_maxrec: int
    started_at: datetime
    finished_at: datetime | None
    expected_count: int | None
    retrieved_count: int | None
    count_query_status_raw: str | None
    retrieval_query_status_raw: str | None
    query_hash: str
    client_version: str
    schema_version: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.query_run_id.strip():
            raise ValueError(
                "query_run_id must not be blank"
            )

        if not self.endpoint.strip():
            raise ValueError(
                "endpoint must not be blank"
            )

        if self.configured_maxrec <= 0:
            raise ValueError(
                "configured_maxrec must be positive"
            )

        for count_name, count_value in (
            ("expected_count", self.expected_count),
            ("retrieved_count", self.retrieved_count),
        ):
            if (
                count_value is not None
                and count_value < 0
            ):
                raise ValueError(
                    f"{count_name} must not be negative"
                )


@dataclass(frozen=True, slots=True)
class TapResponse:
    """Source-neutral representation of one TAP response."""

    rows: tuple[RawArchiveRow, ...]
    declared_columns: tuple[str, ...]
    query_status_raw: object | None
    warnings: tuple[str, ...] = ()


class TapExecutor(Protocol):
    """Port implemented by real and fake TAP executors."""

    def execute(
        self,
        adql: str,
        *,
        maxrec: int,
    ) -> TapResponse:
        """Execute ADQL and return a source-neutral response."""

        ...


@dataclass(frozen=True, slots=True)
class ArchiveQueryResult:
    """Safe result returned by the production Archive client."""

    status: ArchiveQueryStatus
    rows: tuple[RawArchiveRow, ...]
    provenance: ArchiveQueryProvenance
    missing_columns: tuple[str, ...] = ()
    error_kind: ArchiveQueryErrorKind | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if (
            self.status is ArchiveQueryStatus.ERROR
            and self.error_kind is None
        ):
            raise ValueError(
                "ERROR results require an error_kind"
            )

        if (
            self.status is not ArchiveQueryStatus.ERROR
            and self.error_kind is not None
        ):
            raise ValueError(
                "Only ERROR results may have an error_kind"
            )

        if (
            self.status is ArchiveQueryStatus.COMPLETE
            and self.missing_columns
        ):
            raise ValueError(
                "COMPLETE results cannot have missing columns"
            )

    @property
    def is_complete(self) -> bool:
        """Return whether candidate absence may be interpreted."""

        return self.status is ArchiveQueryStatus.COMPLETE

    @property
    def can_reconstruct(self) -> bool:
        """Return whether rows may enter reconstruction."""

        return self.is_complete