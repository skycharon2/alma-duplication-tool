from __future__ import annotations

import alma_duplicate.clients as archive_clients
import alma_duplicate.domain as archive_domain

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


def test_archive_mode_inference_is_not_publicly_exported() -> None:
    removed_client_names = (
        "ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION",
        "ARCHIVE_UI_FREQUENCY_SUPPORT_CONTRACT_VERSION",
        "SCIENCE_ARCHIVE_MANUAL_MAPPING_VERSION",
        "ArchiveSpectralAxisMetadataValidation",
        "ArchiveSpectralModeEvidence",
        "ArchiveUiFrequencySupportEvidence",
        "build_archive_spectral_mode_evidence",
        "build_archive_ui_frequency_support_evidence",
        "resolve_source_spw_spectral_modes",
        "resolve_source_spw_ui_frequency_support_evidence",
        "validate_archive_spectral_axis_metadata",
    )

    for name in removed_client_names:
        assert not hasattr(archive_clients, name)

    removed_domain_names = (
        "ArchiveCorrelatorMode",
        "ArchiveCorrelatorModeMappingSource",
        "ArchiveFrequencySupportType",
        "ArchiveSpectralModeClassificationSource",
        "ArchiveSpectralModeEvidence",
        "ArchiveSpectralModeStatus",
        "ArchiveUiClassificationSource",
        "ArchiveUiFrequencySupportEvidence",
        "ArchiveUiFrequencySupportStatus",
        "ArchiveUiFrequencySupportType",
        "SourceSpwSpectralModeEvidence",
        "SourceSpwUiFrequencySupportEvidence",
    )

    for name in removed_domain_names:
        assert not hasattr(archive_domain, name)
