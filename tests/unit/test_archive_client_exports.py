from __future__ import annotations

from alma_duplicate.clients import (
    ARCHIVE_COMPARISON_CONTRACT_VERSION,
    ArchiveClient,
    ArchiveFieldContractValidation,
    ArchiveQueryResult,
    ArchiveQuerySpec,
    ArchiveQueryStatus,
    PyvoTapExecutor,
    TapFieldMetadata,
    TapResponse,
    prepare_archive_rows,
    run_archive_pipeline,
    validate_archive_comparison_metadata,
)


def test_archive_client_public_exports() -> None:
    assert ARCHIVE_COMPARISON_CONTRACT_VERSION == "2"
    assert ArchiveClient.__name__ == "ArchiveClient"
    assert ArchiveFieldContractValidation.__name__ == (
        "ArchiveFieldContractValidation"
    )
    assert ArchiveQueryResult.__name__ == (
        "ArchiveQueryResult"
    )
    assert ArchiveQuerySpec.__name__ == "ArchiveQuerySpec"
    assert ArchiveQueryStatus.COMPLETE == "COMPLETE"
    assert PyvoTapExecutor.__name__ == "PyvoTapExecutor"
    assert TapFieldMetadata.__name__ == "TapFieldMetadata"
    assert TapResponse.__name__ == "TapResponse"
    assert callable(prepare_archive_rows)
    assert callable(run_archive_pipeline)
    assert callable(validate_archive_comparison_metadata)
