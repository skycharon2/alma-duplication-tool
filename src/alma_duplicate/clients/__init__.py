"""Public Archive client interfaces."""

from .archive_adapter import (
    ADAPTER_VERSION,
    ArchivePipelineBatch,
    ArchiveRowAdapterError,
    IncompleteArchiveQueryError,
    PreparedArchiveRow,
    prepare_archive_rows,
    run_archive_pipeline,
)
from .archive_client import (
    ARCHIVE_CLIENT_VERSION,
    DEFAULT_MAXREC,
    ArchiveClient,
    PyvoTapExecutor,
)
from .archive_contract import (
    ArchiveQueryErrorKind,
    ArchiveQueryProvenance,
    ArchiveQueryResult,
    ArchiveQueryStatus,
    TapExecutionError,
    TapExecutor,
    TapResponse,
)
from .archive_queries import (
    ARCHIVE_SCHEMA_VERSION,
    ARCHIVE_SELECTED_COLUMNS,
    COUNT_ALIAS,
    REQUIRED_ARCHIVE_COLUMNS,
    ArchiveQuerySpec,
    build_count_adql,
    build_retrieval_adql,
    build_where_clause,
    normalize_query_parameters,
)

__all__ = [
    "ADAPTER_VERSION",
    "ARCHIVE_CLIENT_VERSION",
    "ARCHIVE_SCHEMA_VERSION",
    "ARCHIVE_SELECTED_COLUMNS",
    "COUNT_ALIAS",
    "DEFAULT_MAXREC",
    "REQUIRED_ARCHIVE_COLUMNS",
    "ArchiveClient",
    "ArchivePipelineBatch",
    "ArchiveQueryErrorKind",
    "ArchiveQueryProvenance",
    "ArchiveQueryResult",
    "ArchiveQuerySpec",
    "ArchiveQueryStatus",
    "ArchiveRowAdapterError",
    "IncompleteArchiveQueryError",
    "PreparedArchiveRow",
    "PyvoTapExecutor",
    "TapExecutionError",
    "TapExecutor",
    "TapResponse",
    "build_count_adql",
    "build_retrieval_adql",
    "build_where_clause",
    "normalize_query_parameters",
    "prepare_archive_rows",
    "run_archive_pipeline",
]
