"""Adapters and client orchestration for the ALMA Archive TAP service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from numbers import Integral
from typing import Callable, Protocol
from uuid import uuid4

from pyvo.dal import TAPService
from pyvo.dal.exceptions import (
    DALAccessError,
    DALFormatError,
    DALQueryError,
)

from alma_duplicate.clients.archive_contract import (
    ArchiveFrequencyPrefilterStatus,
    ArchiveQueryColumnUnit,
    ArchiveQueryErrorKind,
    ArchiveQueryProvenance,
    ArchiveQueryResult,
    ArchiveQueryStatus,
    TapFieldMetadata,
    TapExecutionError,
    TapExecutor,
    TapResponse,
)
from alma_duplicate.clients.archive_queries import (
    ARCHIVE_FREQUENCY_QUERY_UNITS,
    ARCHIVE_QUERY_UNIT_CONTRACT_VERSION,
    ARCHIVE_SCHEMA_VERSION,
    COUNT_ALIAS,
    REQUIRED_ARCHIVE_COLUMNS,
    ArchiveQuerySpec,
    build_count_adql,
    build_query_unit_metadata_adql,
    build_retrieval_adql,
    normalize_query_parameters,
)


ARCHIVE_CLIENT_VERSION = "3"
DEFAULT_MAXREC = 10_000


@dataclass(frozen=True, slots=True)
class _FrequencyPrefilterPlan:
    effective_spec: ArchiveQuerySpec
    units_verified: bool
    status: ArchiveFrequencyPrefilterStatus
    metadata: tuple[ArchiveQueryColumnUnit, ...] = ()
    warnings: tuple[str, ...] = ()


class _PyvoResult(Protocol):
    query_status: object | None
    infos: Mapping[object, object]
    fielddescs: object

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


def _optional_metadata_text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_metadata_text(
    value: object | None,
    *,
    attribute: str,
) -> str:
    if value is None:
        raise ValueError(
            f"TAP field descriptor is missing {attribute}"
        )
    return str(value)


def _extract_field_metadata(
    result: _PyvoResult,
) -> tuple[TapFieldMetadata, ...]:
    fielddescs = getattr(result, "fielddescs")

    return tuple(
        TapFieldMetadata(
            name=_required_metadata_text(
                getattr(field, "name", None),
                attribute="name",
            ),
            datatype=_required_metadata_text(
                getattr(field, "datatype", None),
                attribute="datatype",
            ),
            arraysize=_optional_metadata_text(
                getattr(field, "arraysize", None)
            ),
            unit=_optional_metadata_text(
                getattr(field, "unit", None)
            ),
            ucd=_optional_metadata_text(
                getattr(field, "ucd", None)
            ),
            utype=_optional_metadata_text(
                getattr(field, "utype", None)
            ),
            xtype=_optional_metadata_text(
                getattr(field, "xtype", None)
            ),
            description=_optional_metadata_text(
                getattr(field, "description", None)
            ),
        )
        for field in fielddescs
    )


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
            response = TapResponse(
                rows=rows,
                declared_columns=columns,
                field_metadata=_extract_field_metadata(result),
                query_status_raw=getattr(
                    result,
                    "query_status",
                    None,
                ),
                warnings=_extract_info_warnings(result),
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise TapExecutionError(
                ArchiveQueryErrorKind.RESPONSE_FORMAT_ERROR,
                f"Unable to convert TAP result: {exc}",
            ) from exc

        return response


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


class _CountResponseError(ValueError):
    def __init__(
        self,
        kind: ArchiveQueryErrorKind,
        message: str,
    ) -> None:
        super().__init__(message)
        self.kind = kind


def _status_text(value: object | None) -> str | None:
    if value is None:
        return None

    normalized_value = getattr(value, "value", value)
    text = str(normalized_value).strip()
    return text.upper() or None


def _raw_status_text(value: object | None) -> str | None:
    if value is None:
        return None

    raw_value = getattr(value, "value", value)
    text = str(raw_value).strip()
    return text or None


def _column_lookup(
    columns: tuple[str, ...],
) -> dict[str, str]:
    return {
        column.casefold(): column
        for column in columns
    }


def _extract_expected_count(
    response: TapResponse,
) -> int:
    status = _status_text(response.query_status_raw)

    if status is None:
        raise _CountResponseError(
            ArchiveQueryErrorKind.UNKNOWN_QUERY_STATUS,
            "COUNT response did not provide QUERY_STATUS",
        )

    if status != "OK":
        raise _CountResponseError(
            ArchiveQueryErrorKind.INVALID_COUNT,
            f"COUNT response QUERY_STATUS was {status!r}",
        )

    column_lookup = _column_lookup(
        response.declared_columns
    )
    count_column = column_lookup.get(
        COUNT_ALIAS.casefold()
    )

    if count_column is None:
        raise _CountResponseError(
            ArchiveQueryErrorKind.INVALID_COUNT,
            (
                "COUNT response is missing the "
                f"{COUNT_ALIAS!r} column"
            ),
        )

    if len(response.rows) != 1:
        raise _CountResponseError(
            ArchiveQueryErrorKind.INVALID_COUNT,
            "COUNT response must contain exactly one row",
        )

    try:
        raw_count = response.rows[0][count_column]
    except KeyError as exc:
        raise _CountResponseError(
            ArchiveQueryErrorKind.INVALID_COUNT,
            "COUNT row does not contain its declared column",
        ) from exc

    if (
        isinstance(raw_count, bool)
        or not isinstance(raw_count, Integral)
    ):
        raise _CountResponseError(
            ArchiveQueryErrorKind.INVALID_COUNT,
            "COUNT value must be a non-negative integer",
        )

    expected_count = int(raw_count)
    if expected_count < 0:
        raise _CountResponseError(
            ArchiveQueryErrorKind.INVALID_COUNT,
            "COUNT value must be a non-negative integer",
        )

    return expected_count


def _missing_required_columns(
    declared_columns: tuple[str, ...],
) -> tuple[str, ...]:
    available = {
        column.casefold()
        for column in declared_columns
    }

    return tuple(
        sorted(
            column
            for column in REQUIRED_ARCHIVE_COLUMNS
            if column.casefold() not in available
        )
    )


def _spatial_only_spec(spec: ArchiveQuerySpec) -> ArchiveQuerySpec:
    return replace(
        spec,
        frequency_min_ghz=None,
        frequency_max_ghz=None,
    )


def _query_unit_metadata(
    response: TapResponse,
) -> tuple[ArchiveQueryColumnUnit, ...] | None:
    if _status_text(response.query_status_raw) != "OK":
        return None

    columns = _column_lookup(response.declared_columns)
    required = ("column_name", "datatype", "unit")
    if any(name not in columns for name in required):
        return None

    parsed: list[ArchiveQueryColumnUnit] = []
    try:
        for row in response.rows:
            name = str(row[columns["column_name"]]).strip()
            datatype_raw = row[columns["datatype"]]
            unit_raw = row[columns["unit"]]
            parsed.append(
                ArchiveQueryColumnUnit(
                    column_name=name,
                    datatype=(
                        str(datatype_raw).strip()
                        if datatype_raw is not None
                        else None
                    ),
                    unit=(
                        str(unit_raw).strip()
                        if unit_raw is not None
                        else None
                    ),
                )
            )
    except (KeyError, TypeError, ValueError):
        return None

    return tuple(parsed)


def _query_units_are_exact(
    metadata: tuple[ArchiveQueryColumnUnit, ...],
) -> bool | None:
    by_name: dict[str, ArchiveQueryColumnUnit] = {}
    for item in metadata:
        key = item.column_name.casefold()
        if key in by_name:
            return None
        by_name[key] = item

    expected_names = {
        name.casefold()
        for name, _, _ in ARCHIVE_FREQUENCY_QUERY_UNITS
    }
    if set(by_name) != expected_names:
        return None

    return all(
        (
            by_name[name.casefold()].datatype is not None
            and by_name[name.casefold()].datatype.casefold()
            == datatype.casefold()
            and by_name[name.casefold()].unit == unit
        )
        for name, datatype, unit in ARCHIVE_FREQUENCY_QUERY_UNITS
    )


class ArchiveClient:
    """Execute COUNT and retrieval as one safe Archive query run."""

    def __init__(
        self,
        endpoint: str,
        *,
        executor: TapExecutor | None = None,
        maxrec: int = DEFAULT_MAXREC,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        normalized_endpoint = endpoint.strip().rstrip("/")
        if not normalized_endpoint:
            raise ValueError("endpoint must not be blank")
        if maxrec <= 0:
            raise ValueError("maxrec must be positive")

        self.endpoint = normalized_endpoint
        self.maxrec = maxrec
        self._executor = executor or PyvoTapExecutor(
            normalized_endpoint
        )
        self._clock = clock or (
            lambda: datetime.now(timezone.utc)
        )
        self._run_id_factory = run_id_factory or (
            lambda: str(uuid4())
        )

    def _plan_frequency_prefilter(
        self,
        spec: ArchiveQuerySpec,
    ) -> _FrequencyPrefilterPlan:
        if spec.frequency_min_ghz is None:
            return _FrequencyPrefilterPlan(
                effective_spec=spec,
                units_verified=False,
                status=ArchiveFrequencyPrefilterStatus.NOT_REQUESTED,
            )

        try:
            response = self._executor.execute(
                build_query_unit_metadata_adql(),
                maxrec=len(ARCHIVE_FREQUENCY_QUERY_UNITS),
            )
        except TapExecutionError as exc:
            return _FrequencyPrefilterPlan(
                effective_spec=_spatial_only_spec(spec),
                units_verified=False,
                status=(
                    ArchiveFrequencyPrefilterStatus
                    .FALLBACK_METADATA_QUERY_ERROR
                ),
                warnings=(
                    "frequency prefilter disabled because TAP_SCHEMA "
                    f"could not be verified: {exc}",
                ),
            )

        metadata = _query_unit_metadata(response)
        if metadata is None:
            return _FrequencyPrefilterPlan(
                effective_spec=_spatial_only_spec(spec),
                units_verified=False,
                status=(
                    ArchiveFrequencyPrefilterStatus
                    .FALLBACK_METADATA_INCOMPLETE
                ),
                warnings=response.warnings + (
                    "frequency prefilter disabled because TAP_SCHEMA "
                    "metadata was incomplete",
                ),
            )

        exact = _query_units_are_exact(metadata)
        if exact is None:
            return _FrequencyPrefilterPlan(
                effective_spec=_spatial_only_spec(spec),
                units_verified=False,
                status=(
                    ArchiveFrequencyPrefilterStatus
                    .FALLBACK_METADATA_INCOMPLETE
                ),
                metadata=metadata,
                warnings=response.warnings + (
                    "frequency prefilter disabled because TAP_SCHEMA "
                    "did not describe exactly frequency and bandwidth",
                ),
            )
        if not exact:
            return _FrequencyPrefilterPlan(
                effective_spec=_spatial_only_spec(spec),
                units_verified=False,
                status=(
                    ArchiveFrequencyPrefilterStatus
                    .FALLBACK_UNIT_MISMATCH
                ),
                metadata=metadata,
                warnings=response.warnings + (
                    "frequency prefilter disabled because Archive query "
                    "units did not match frequency=GHz and bandwidth=Hz",
                ),
            )

        return _FrequencyPrefilterPlan(
            effective_spec=spec,
            units_verified=True,
            status=(
                ArchiveFrequencyPrefilterStatus.VERIFIED_EXACT_UNITS
            ),
            metadata=metadata,
            warnings=response.warnings,
        )

    def search(
        self,
        spec: ArchiveQuerySpec,
    ) -> ArchiveQueryResult:
        query_run_id = self._run_id_factory()
        started_at = self._clock()
        prefilter_plan = self._plan_frequency_prefilter(spec)
        count_adql = build_count_adql(
            prefilter_plan.effective_spec,
            frequency_units_verified=prefilter_plan.units_verified,
        )
        retrieval_adql = build_retrieval_adql(
            prefilter_plan.effective_spec,
            frequency_units_verified=prefilter_plan.units_verified,
        )
        normalized_parameters = (
            normalize_query_parameters(spec)
        )
        query_hash = sha256(
            (
                self.endpoint
                + "\0"
                + count_adql
                + "\0"
                + retrieval_adql
                + "\0"
                + prefilter_plan.status.value
                + "\0"
                + repr(prefilter_plan.metadata)
            ).encode("utf-8")
        ).hexdigest()

        count_response: TapResponse | None = None
        retrieval_response: TapResponse | None = None
        expected_count: int | None = None

        try:
            count_response = self._executor.execute(
                count_adql,
                maxrec=1,
            )
        except TapExecutionError as exc:
            return self._error_result(
                kind=exc.kind,
                message=str(exc),
                rows=(),
                missing_columns=(),
                query_run_id=query_run_id,
                count_adql=count_adql,
                retrieval_adql=retrieval_adql,
                normalized_parameters=normalized_parameters,
                query_hash=query_hash,
                started_at=started_at,
                expected_count=None,
                count_response=None,
                retrieval_response=None,
                prefilter_plan=prefilter_plan,
            )

        try:
            expected_count = _extract_expected_count(
                count_response
            )
        except _CountResponseError as exc:
            return self._error_result(
                kind=exc.kind,
                message=str(exc),
                rows=(),
                missing_columns=(),
                query_run_id=query_run_id,
                count_adql=count_adql,
                retrieval_adql=retrieval_adql,
                normalized_parameters=normalized_parameters,
                query_hash=query_hash,
                started_at=started_at,
                expected_count=None,
                count_response=count_response,
                retrieval_response=None,
                prefilter_plan=prefilter_plan,
            )

        try:
            retrieval_response = self._executor.execute(
                retrieval_adql,
                maxrec=self.maxrec,
            )
        except TapExecutionError as exc:
            return self._error_result(
                kind=exc.kind,
                message=str(exc),
                rows=(),
                missing_columns=(),
                query_run_id=query_run_id,
                count_adql=count_adql,
                retrieval_adql=retrieval_adql,
                normalized_parameters=normalized_parameters,
                query_hash=query_hash,
                started_at=started_at,
                expected_count=expected_count,
                count_response=count_response,
                retrieval_response=None,
                prefilter_plan=prefilter_plan,
            )

        rows = retrieval_response.rows
        retrieved_count = len(rows)
        missing_columns = _missing_required_columns(
            retrieval_response.declared_columns
        )

        if missing_columns:
            return self._error_result(
                kind=ArchiveQueryErrorKind.SCHEMA_DRIFT,
                message=(
                    "Archive retrieval response is missing "
                    "required columns"
                ),
                rows=rows,
                missing_columns=missing_columns,
                query_run_id=query_run_id,
                count_adql=count_adql,
                retrieval_adql=retrieval_adql,
                normalized_parameters=normalized_parameters,
                query_hash=query_hash,
                started_at=started_at,
                expected_count=expected_count,
                count_response=count_response,
                retrieval_response=retrieval_response,
                prefilter_plan=prefilter_plan,
            )

        retrieval_status = _status_text(
            retrieval_response.query_status_raw
        )

        if retrieval_status not in {"OK", "OVERFLOW"}:
            return self._error_result(
                kind=(
                    ArchiveQueryErrorKind
                    .UNKNOWN_QUERY_STATUS
                ),
                message=(
                    "Archive retrieval response has an "
                    "unknown or missing QUERY_STATUS"
                ),
                rows=rows,
                missing_columns=(),
                query_run_id=query_run_id,
                count_adql=count_adql,
                retrieval_adql=retrieval_adql,
                normalized_parameters=normalized_parameters,
                query_hash=query_hash,
                started_at=started_at,
                expected_count=expected_count,
                count_response=count_response,
                retrieval_response=retrieval_response,
                prefilter_plan=prefilter_plan,
            )

        if retrieval_status == "OVERFLOW":
            status = ArchiveQueryStatus.OVERFLOW
        elif expected_count != retrieved_count:
            status = ArchiveQueryStatus.COUNT_MISMATCH
        else:
            status = ArchiveQueryStatus.COMPLETE

        provenance = self._provenance(
            query_run_id=query_run_id,
            count_adql=count_adql,
            retrieval_adql=retrieval_adql,
            normalized_parameters=normalized_parameters,
            query_hash=query_hash,
            started_at=started_at,
            expected_count=expected_count,
            retrieved_count=retrieved_count,
            count_response=count_response,
            retrieval_response=retrieval_response,
            prefilter_plan=prefilter_plan,
        )

        return ArchiveQueryResult(
            status=status,
            rows=rows,
            provenance=provenance,
            field_metadata=retrieval_response.field_metadata,
        )

    def _error_result(
        self,
        *,
        kind: ArchiveQueryErrorKind,
        message: str,
        rows: tuple[Mapping[str, object], ...],
        missing_columns: tuple[str, ...],
        query_run_id: str,
        count_adql: str,
        retrieval_adql: str,
        normalized_parameters: tuple[
            tuple[str, str | int | float | bool | None],
            ...,
        ],
        query_hash: str,
        started_at: datetime,
        expected_count: int | None,
        count_response: TapResponse | None,
        retrieval_response: TapResponse | None,
        prefilter_plan: _FrequencyPrefilterPlan,
    ) -> ArchiveQueryResult:
        provenance = self._provenance(
            query_run_id=query_run_id,
            count_adql=count_adql,
            retrieval_adql=retrieval_adql,
            normalized_parameters=normalized_parameters,
            query_hash=query_hash,
            started_at=started_at,
            expected_count=expected_count,
            retrieved_count=(
                len(retrieval_response.rows)
                if retrieval_response is not None
                else None
            ),
            count_response=count_response,
            retrieval_response=retrieval_response,
            prefilter_plan=prefilter_plan,
        )

        return ArchiveQueryResult(
            status=ArchiveQueryStatus.ERROR,
            rows=rows,
            provenance=provenance,
            field_metadata=(
                retrieval_response.field_metadata
                if retrieval_response is not None
                else ()
            ),
            missing_columns=missing_columns,
            error_kind=kind,
            error_message=message,
        )

    def _provenance(
        self,
        *,
        query_run_id: str,
        count_adql: str,
        retrieval_adql: str,
        normalized_parameters: tuple[
            tuple[str, str | int | float | bool | None],
            ...,
        ],
        query_hash: str,
        started_at: datetime,
        expected_count: int | None,
        retrieved_count: int | None,
        count_response: TapResponse | None,
        retrieval_response: TapResponse | None,
        prefilter_plan: _FrequencyPrefilterPlan,
    ) -> ArchiveQueryProvenance:
        warnings = (
            prefilter_plan.warnings
            + (
                count_response.warnings
                if count_response is not None
                else ()
            )
            + (
                retrieval_response.warnings
                if retrieval_response is not None
                else ()
            )
        )

        return ArchiveQueryProvenance(
            query_run_id=query_run_id,
            endpoint=self.endpoint,
            count_adql=count_adql,
            retrieval_adql=retrieval_adql,
            normalized_parameters=normalized_parameters,
            configured_maxrec=self.maxrec,
            started_at=started_at,
            finished_at=self._clock(),
            expected_count=expected_count,
            retrieved_count=retrieved_count,
            count_query_status_raw=_raw_status_text(
                count_response.query_status_raw
                if count_response is not None
                else None
            ),
            retrieval_query_status_raw=(
                _raw_status_text(
                    retrieval_response.query_status_raw
                )
                if retrieval_response is not None
                else None
            ),
            query_hash=query_hash,
            client_version=ARCHIVE_CLIENT_VERSION,
            schema_version=ARCHIVE_SCHEMA_VERSION,
            frequency_prefilter_status=prefilter_plan.status,
            query_unit_contract_version=(
                ARCHIVE_QUERY_UNIT_CONTRACT_VERSION
            ),
            query_unit_metadata=prefilter_plan.metadata,
            warnings=warnings,
        )
