from __future__ import annotations

from alma_duplicate.clients import (
    ARCHIVE_COMPARISON_CONTRACT_VERSION,
    ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION,
    ArchiveClient,
    ArchiveFieldContractValidation,
    ArchiveQueryResult,
    ArchiveQuerySpec,
    ArchiveQueryStatus,
    ArchiveSpectralAxisMetadataValidation,
    PyvoTapExecutor,
    TapFieldMetadata,
    TapResponse,
    build_archive_spectral_mode_evidence,
    prepare_archive_rows,
    resolve_source_spw_spectral_modes,
    run_archive_pipeline,
    validate_archive_comparison_metadata,
    validate_archive_spectral_axis_metadata,
)


def test_archive_client_public_exports() -> None:
    assert ARCHIVE_COMPARISON_CONTRACT_VERSION == "2"
    assert ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION == "1"
    assert ArchiveClient.__name__ == "ArchiveClient"
    assert ArchiveFieldContractValidation.__name__ == (
        "ArchiveFieldContractValidation"
    )
    assert ArchiveSpectralAxisMetadataValidation.__name__ == (
        "ArchiveSpectralAxisMetadataValidation"
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
    assert callable(build_archive_spectral_mode_evidence)
    assert callable(resolve_source_spw_spectral_modes)
    assert callable(run_archive_pipeline)
    assert callable(validate_archive_comparison_metadata)
    assert callable(validate_archive_spectral_axis_metadata)
