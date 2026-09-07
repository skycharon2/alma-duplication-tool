"""Resolve optional raw evidence columns before building science ADQL."""

from alma_duplicate.clients.archive_contract import (
    ArchiveOptionalColumnEvidence,
    ArchiveOptionalColumnStatus as Status,
    ArchiveProjectionEvidence,
    TapExecutionError,
    TapExecutor,
)
from alma_duplicate.clients.archive_queries import (
    ARCHIVE_CORE_COLUMNS, ARCHIVE_OPTIONAL_COLUMNS,
    ARCHIVE_PROJECTION_VERSION, ARCHIVE_TABLE,
)


def plan_archive_projection(
    executor: TapExecutor,
    requested: tuple[str, ...] = ARCHIVE_OPTIONAL_COLUMNS,
) -> ArchiveProjectionEvidence:
    """Fail open only for optional evidence, never for core schema checks.

    A complete, valid probe is required to claim NOT_IN_SCHEMA. Truncated,
    duplicate or malformed metadata cannot establish absence.
    """
    if len(set(requested)) != len(requested) or not set(requested).issubset(
        ARCHIVE_OPTIONAL_COLUMNS
    ):
        raise ValueError("optional columns must be unique supported names")
    # Canonical order, independent of caller ordering.
    requested = tuple(name for name in ARCHIVE_OPTIONAL_COLUMNS if name in requested)
    adql = None
    raw_status = None
    rows = ()
    warnings = ()
    error = None
    available = set()
    if requested:
        names = ", ".join(f"'{name}'" for name in requested)
        adql = (
            "SELECT column_name\nFROM TAP_SCHEMA.columns\n"
            f"WHERE table_name = '{ARCHIVE_TABLE}'\n"
            f"    AND column_name IN ({names})"
        )
        try:
            response = executor.execute(adql, maxrec=len(requested) + 1)
            rows = response.rows
            warnings = response.warnings
            raw_status = (
                str(response.query_status_raw)
                if response.query_status_raw is not None else None
            )
            if raw_status != "OK" or response.declared_columns != ("column_name",):
                raise ValueError("optional schema probe is incomplete or malformed")
            for row in rows:
                name = row.get("column_name")
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                if not isinstance(name, str):
                    raise ValueError("invalid schema column name")
                name = name.strip().casefold()
                if name not in requested or name in available:
                    raise ValueError("unexpected or duplicate schema column name")
                available.add(name)
        except (TapExecutionError, ValueError) as exc:
            error = str(exc)
            available.clear()
            warnings += (f"Optional projection schema unavailable: {exc}",)
    decisions = tuple(
        ArchiveOptionalColumnEvidence(
            column_name=name,
            status=(Status.NOT_REQUESTED if name not in requested
                    else Status.SCHEMA_UNAVAILABLE if error is not None
                    else Status.SELECTED if name in available
                    else Status.NOT_IN_SCHEMA),
        )
        for name in ARCHIVE_OPTIONAL_COLUMNS
    )
    return ArchiveProjectionEvidence(
        version=ARCHIVE_PROJECTION_VERSION,
        selected_columns=ARCHIVE_CORE_COLUMNS + tuple(
            item.column_name for item in decisions if item.status is Status.SELECTED
        ),
        optional_columns=decisions, probe_adql=adql,
        probe_status_raw=raw_status, probe_rows=rows,
        probe_error=error, warnings=warnings,
    )
