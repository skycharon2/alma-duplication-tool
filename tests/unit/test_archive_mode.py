from __future__ import annotations

import pytest

from alma_duplicate.clients.archive_contract import TapFieldMetadata
from alma_duplicate.clients.archive_mode import (
    ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION,
    ARCHIVE_UI_CHANNEL_COUNT_RULE_VERSION,
    SCIENCE_ARCHIVE_MANUAL_MAPPING_VERSION,
    ArchiveSpectralAxisMetadataStatus,
    build_archive_spectral_mode_evidence,
    resolve_source_spw_spectral_modes,
    validate_archive_spectral_axis_metadata,
)
from alma_duplicate.domain.archive_evidence import (
    ArchiveCorrelatorMode,
    ArchiveFrequencySupportType,
    ArchiveSpectralModeStatus,
)
from alma_duplicate.domain.reconstruction import (
    SourceExecutionKey,
    SourceSpwAssociationKey,
)


def _metadata(datatype: str = "int") -> tuple[TapFieldMetadata, ...]:
    return (
        TapFieldMetadata(
            name="em_xel",
            datatype=datatype,
            arraysize=None,
            unit=None,
            ucd="meta.number",
            utype=None,
            xtype=None,
            description="Number of elements along the spectral axis",
        ),
    )


def _evidence(value: object):
    return build_archive_spectral_mode_evidence(
        value,
        validate_archive_spectral_axis_metadata(_metadata()),
    )


def _association(spw_index: int) -> SourceSpwAssociationKey:
    return SourceSpwAssociationKey(
        context=SourceExecutionKey(
            member_ous_uid="uid://A001/X129e/X2b6",
            asdm_uid="uid://A002/X1/X1",
            source_name="CI_Tau",
        ),
        spw_token=str(spw_index),
        spw_index=spw_index,
    )


@pytest.mark.parametrize(
    (
        "value",
        "expected_type",
        "expected_mode",
    ),
    [
        (
            1,
            ArchiveFrequencySupportType.CONTINUUM,
            ArchiveCorrelatorMode.TDM,
        ),
        (
            128,
            ArchiveFrequencySupportType.CONTINUUM,
            ArchiveCorrelatorMode.TDM,
        ),
        (
            129,
            ArchiveFrequencySupportType.LINE,
            ArchiveCorrelatorMode.FDM,
        ),
        (
            1920,
            ArchiveFrequencySupportType.LINE,
            ArchiveCorrelatorMode.FDM,
        ),
    ],
)
def test_channel_count_boundary_matches_archive_ui(
    value: int,
    expected_type: ArchiveFrequencySupportType,
    expected_mode: ArchiveCorrelatorMode,
) -> None:
    evidence = _evidence(value)

    assert evidence.raw_spectral_axis_elements == value
    assert evidence.spectral_axis_elements == value
    assert evidence.frequency_support_type is expected_type
    assert evidence.correlator_mode is expected_mode
    assert evidence.status is ArchiveSpectralModeStatus.DERIVED
    assert evidence.classification_version == (
        ARCHIVE_UI_CHANNEL_COUNT_RULE_VERSION
    )
    assert evidence.mapping_version == (
        SCIENCE_ARCHIVE_MANUAL_MAPPING_VERSION
    )


def test_missing_value_returns_unknown() -> None:
    evidence = _evidence(None)

    assert evidence.raw_spectral_axis_elements is None
    assert evidence.spectral_axis_elements is None
    assert evidence.frequency_support_type is (
        ArchiveFrequencySupportType.UNKNOWN
    )
    assert evidence.correlator_mode is ArchiveCorrelatorMode.UNKNOWN
    assert evidence.status is (
        ArchiveSpectralModeStatus.UNKNOWN_MISSING_VALUE
    )


@pytest.mark.parametrize("value", [0, -1, 128.5, "128", True])
def test_invalid_value_returns_unknown(value: object) -> None:
    evidence = _evidence(value)

    assert evidence.raw_spectral_axis_elements == value
    assert evidence.spectral_axis_elements is None
    assert evidence.frequency_support_type is (
        ArchiveFrequencySupportType.UNKNOWN
    )
    assert evidence.correlator_mode is ArchiveCorrelatorMode.UNKNOWN
    assert evidence.status is (
        ArchiveSpectralModeStatus.UNKNOWN_INVALID_VALUE
    )


@pytest.mark.parametrize(
    ("metadata", "expected_status"),
    [
        (
            (),
            ArchiveSpectralAxisMetadataStatus.MISSING_FIELD_METADATA,
        ),
        (
            _metadata("double"),
            ArchiveSpectralAxisMetadataStatus
            .INCOMPATIBLE_SOURCE_DATATYPE,
        ),
    ],
)
def test_unusable_metadata_fails_closed(
    metadata: tuple[TapFieldMetadata, ...],
    expected_status: ArchiveSpectralAxisMetadataStatus,
) -> None:
    validation = validate_archive_spectral_axis_metadata(metadata)
    evidence = build_archive_spectral_mode_evidence(128, validation)

    assert validation.contract_version == (
        ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION
    )
    assert validation.status is expected_status
    assert not validation.is_usable
    assert evidence.spectral_axis_elements is None
    assert evidence.correlator_mode is ArchiveCorrelatorMode.UNKNOWN
    assert evidence.status is (
        ArchiveSpectralModeStatus.UNKNOWN_METADATA_UNUSABLE
    )


def test_mixed_mode_is_resolved_per_source_spw_association() -> None:
    tdm_association = _association(0)
    fdm_association = _association(1)

    resolved = resolve_source_spw_spectral_modes(
        (
            ("query:00000000", tdm_association, _evidence(128)),
            ("query:00000001", fdm_association, _evidence(1920)),
        )
    )

    by_association = {item.association_key: item for item in resolved}
    assert by_association[tdm_association].correlator_mode is (
        ArchiveCorrelatorMode.TDM
    )
    assert by_association[fdm_association].correlator_mode is (
        ArchiveCorrelatorMode.FDM
    )
    assert all(item.is_derived for item in resolved)


def test_conflicting_rows_for_one_association_fail_closed() -> None:
    association = _association(0)

    resolved = resolve_source_spw_spectral_modes(
        (
            ("query:00000000", association, _evidence(128)),
            ("query:00000001", association, _evidence(1920)),
        )
    )

    assert len(resolved) == 1
    evidence = resolved[0]
    assert evidence.supporting_raw_row_ids == (
        "query:00000000",
        "query:00000001",
    )
    assert evidence.spectral_axis_elements is None
    assert evidence.frequency_support_type is (
        ArchiveFrequencySupportType.UNKNOWN
    )
    assert evidence.correlator_mode is ArchiveCorrelatorMode.UNKNOWN
    assert evidence.status is (
        ArchiveSpectralModeStatus.UNKNOWN_CONFLICT
    )
