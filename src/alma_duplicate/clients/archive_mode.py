"""Versioned per-SPW Archive mode derivation from public TAP evidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from numbers import Integral

from alma_duplicate.clients.archive_contract import (
    TapFieldMetadata,
)
from alma_duplicate.domain.archive_evidence import (
    ArchiveCorrelatorMode,
    ArchiveCorrelatorModeMappingSource,
    ArchiveFrequencySupportType,
    ArchiveSpectralModeClassificationSource,
    ArchiveSpectralModeEvidence,
    ArchiveSpectralModeStatus,
)
from alma_duplicate.domain.reconstruction import (
    SourceSpwAssociationKey,
    SourceSpwSpectralModeEvidence,
)

ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION = "1"
ARCHIVE_UI_CHANNEL_COUNT_RULE_VERSION = "2026.06.01"
SCIENCE_ARCHIVE_MANUAL_MAPPING_VERSION = "cycle13-v1"
ARCHIVE_SPECTRAL_AXIS_FIELD = "em_xel"
ARCHIVE_UI_LINE_CHANNEL_THRESHOLD = 129
ARCHIVE_SPECTRAL_AXIS_EXPECTED_DATATYPES = frozenset({"int"})


class ArchiveSpectralAxisMetadataStatus(StrEnum):
    """Validation result for the live ``em_xel`` field descriptor."""

    VERIFIED_INTEGER_DATATYPE = "VERIFIED_INTEGER_DATATYPE"
    MISSING_FIELD_METADATA = "MISSING_FIELD_METADATA"
    INCOMPATIBLE_SOURCE_DATATYPE = "INCOMPATIBLE_SOURCE_DATATYPE"


@dataclass(frozen=True, slots=True)
class ArchiveSpectralAxisMetadataValidation:
    """Validated source descriptor used before classifying ``em_xel``."""

    metadata: TapFieldMetadata | None
    status: ArchiveSpectralAxisMetadataStatus
    contract_version: str = ARCHIVE_SPECTRAL_MODE_CONTRACT_VERSION

    @property
    def is_usable(self) -> bool:
        return self.status is (
            ArchiveSpectralAxisMetadataStatus
            .VERIFIED_INTEGER_DATATYPE
        )


def validate_archive_spectral_axis_metadata(
    field_metadata: tuple[TapFieldMetadata, ...],
) -> ArchiveSpectralAxisMetadataValidation:
    """Require the public TAP ``em_xel`` descriptor to remain integer."""

    matches = tuple(
        field
        for field in field_metadata
        if field.name.casefold() == ARCHIVE_SPECTRAL_AXIS_FIELD
    )
    if len(matches) != 1:
        return ArchiveSpectralAxisMetadataValidation(
            metadata=None,
            status=(
                ArchiveSpectralAxisMetadataStatus
                .MISSING_FIELD_METADATA
            ),
        )

    metadata = matches[0]
    if metadata.datatype.strip().casefold() not in (
        ARCHIVE_SPECTRAL_AXIS_EXPECTED_DATATYPES
    ):
        return ArchiveSpectralAxisMetadataValidation(
            metadata=metadata,
            status=(
                ArchiveSpectralAxisMetadataStatus
                .INCOMPATIBLE_SOURCE_DATATYPE
            ),
        )

    return ArchiveSpectralAxisMetadataValidation(
        metadata=metadata,
        status=(
            ArchiveSpectralAxisMetadataStatus
            .VERIFIED_INTEGER_DATATYPE
        ),
    )


def _is_masked(value: object) -> bool:
    mask = getattr(value, "mask", False)
    try:
        return bool(mask)
    except (TypeError, ValueError):
        return False


def _mode_evidence(
    *,
    raw_value: object,
    spectral_axis_elements: int | None,
    frequency_support_type: ArchiveFrequencySupportType,
    correlator_mode: ArchiveCorrelatorMode,
    status: ArchiveSpectralModeStatus,
    source_datatype: str | None,
) -> ArchiveSpectralModeEvidence:
    return ArchiveSpectralModeEvidence(
        raw_spectral_axis_elements=raw_value,
        spectral_axis_elements=spectral_axis_elements,
        frequency_support_type=frequency_support_type,
        correlator_mode=correlator_mode,
        status=status,
        source_datatype=source_datatype,
        classification_source=(
            ArchiveSpectralModeClassificationSource
            .ARCHIVE_UI_CHANNEL_COUNT_RULE
        ),
        classification_version=(
            ARCHIVE_UI_CHANNEL_COUNT_RULE_VERSION
        ),
        mapping_source=(
            ArchiveCorrelatorModeMappingSource
            .SCIENCE_ARCHIVE_MANUAL
        ),
        mapping_version=SCIENCE_ARCHIVE_MANUAL_MAPPING_VERSION,
    )


def build_archive_spectral_mode_evidence(
    raw_value: object,
    validation: ArchiveSpectralAxisMetadataValidation,
) -> ArchiveSpectralModeEvidence:
    """Apply the Archive UI rule, then the manual's TDM/FDM mapping."""

    source_datatype = (
        validation.metadata.datatype
        if validation.metadata is not None
        else None
    )
    if not validation.is_usable:
        return _mode_evidence(
            raw_value=raw_value,
            spectral_axis_elements=None,
            frequency_support_type=(
                ArchiveFrequencySupportType.UNKNOWN
            ),
            correlator_mode=ArchiveCorrelatorMode.UNKNOWN,
            status=(
                ArchiveSpectralModeStatus
                .UNKNOWN_METADATA_UNUSABLE
            ),
            source_datatype=source_datatype,
        )

    if raw_value is None or _is_masked(raw_value):
        return _mode_evidence(
            raw_value=raw_value,
            spectral_axis_elements=None,
            frequency_support_type=(
                ArchiveFrequencySupportType.UNKNOWN
            ),
            correlator_mode=ArchiveCorrelatorMode.UNKNOWN,
            status=(
                ArchiveSpectralModeStatus.UNKNOWN_MISSING_VALUE
            ),
            source_datatype=source_datatype,
        )

    if (
        isinstance(raw_value, bool)
        or not isinstance(raw_value, Integral)
        or int(raw_value) <= 0
    ):
        return _mode_evidence(
            raw_value=raw_value,
            spectral_axis_elements=None,
            frequency_support_type=(
                ArchiveFrequencySupportType.UNKNOWN
            ),
            correlator_mode=ArchiveCorrelatorMode.UNKNOWN,
            status=(
                ArchiveSpectralModeStatus.UNKNOWN_INVALID_VALUE
            ),
            source_datatype=source_datatype,
        )

    spectral_axis_elements = int(raw_value)
    if spectral_axis_elements < ARCHIVE_UI_LINE_CHANNEL_THRESHOLD:
        frequency_support_type = (
            ArchiveFrequencySupportType.CONTINUUM
        )
        correlator_mode = ArchiveCorrelatorMode.TDM
    else:
        frequency_support_type = ArchiveFrequencySupportType.LINE
        correlator_mode = ArchiveCorrelatorMode.FDM

    return _mode_evidence(
        raw_value=raw_value,
        spectral_axis_elements=spectral_axis_elements,
        frequency_support_type=frequency_support_type,
        correlator_mode=correlator_mode,
        status=ArchiveSpectralModeStatus.DERIVED,
        source_datatype=source_datatype,
    )


def _association_evidence(
    *,
    association_key: SourceSpwAssociationKey,
    supporting_raw_row_ids: tuple[str, ...],
    spectral_axis_elements: int | None,
    frequency_support_type: ArchiveFrequencySupportType,
    correlator_mode: ArchiveCorrelatorMode,
    status: ArchiveSpectralModeStatus,
) -> SourceSpwSpectralModeEvidence:
    return SourceSpwSpectralModeEvidence(
        association_key=association_key,
        supporting_raw_row_ids=supporting_raw_row_ids,
        spectral_axis_elements=spectral_axis_elements,
        frequency_support_type=frequency_support_type,
        correlator_mode=correlator_mode,
        status=status,
        classification_source=(
            ArchiveSpectralModeClassificationSource
            .ARCHIVE_UI_CHANNEL_COUNT_RULE
        ),
        classification_version=(
            ARCHIVE_UI_CHANNEL_COUNT_RULE_VERSION
        ),
        mapping_source=(
            ArchiveCorrelatorModeMappingSource
            .SCIENCE_ARCHIVE_MANUAL
        ),
        mapping_version=SCIENCE_ARCHIVE_MANUAL_MAPPING_VERSION,
    )


def resolve_source_spw_spectral_modes(
    linked_row_evidence: Iterable[
        tuple[
            str,
            SourceSpwAssociationKey,
            ArchiveSpectralModeEvidence,
        ]
    ],
) -> tuple[SourceSpwSpectralModeEvidence, ...]:
    """Resolve row evidence without promoting it to Member OUS scope.

    Multiple raw rows may support one logical association.  They must agree
    on the validated channel count and on both derived labels; otherwise the
    association fails closed with ``UNKNOWN_CONFLICT``.
    """

    grouped: dict[
        SourceSpwAssociationKey,
        list[tuple[str, ArchiveSpectralModeEvidence]],
    ] = defaultdict(list)
    seen_raw_row_ids: set[str] = set()

    for raw_row_id, association_key, evidence in linked_row_evidence:
        if not raw_row_id.strip():
            raise ValueError("raw_row_id must not be blank")
        if raw_row_id in seen_raw_row_ids:
            raise ValueError("raw_row_id values must be unique")
        seen_raw_row_ids.add(raw_row_id)
        grouped[association_key].append((raw_row_id, evidence))

    resolved: list[SourceSpwSpectralModeEvidence] = []
    for association_key in sorted(grouped):
        rows = tuple(
            sorted(grouped[association_key], key=lambda item: item[0])
        )
        raw_row_ids = tuple(raw_row_id for raw_row_id, _ in rows)
        evidence_items = tuple(evidence for _, evidence in rows)

        if all(evidence.is_derived for evidence in evidence_items):
            signatures = {
                (
                    evidence.spectral_axis_elements,
                    evidence.frequency_support_type,
                    evidence.correlator_mode,
                    evidence.classification_source,
                    evidence.classification_version,
                    evidence.mapping_source,
                    evidence.mapping_version,
                )
                for evidence in evidence_items
            }
            if len(signatures) == 1:
                first = evidence_items[0]
                resolved.append(
                    _association_evidence(
                        association_key=association_key,
                        supporting_raw_row_ids=raw_row_ids,
                        spectral_axis_elements=(
                            first.spectral_axis_elements
                        ),
                        frequency_support_type=(
                            first.frequency_support_type
                        ),
                        correlator_mode=first.correlator_mode,
                        status=ArchiveSpectralModeStatus.DERIVED,
                    )
                )
                continue

            unknown_status = (
                ArchiveSpectralModeStatus.UNKNOWN_CONFLICT
            )
        else:
            statuses = {evidence.status for evidence in evidence_items}
            if (
                ArchiveSpectralModeStatus.UNKNOWN_METADATA_UNUSABLE
                in statuses
            ):
                unknown_status = (
                    ArchiveSpectralModeStatus
                    .UNKNOWN_METADATA_UNUSABLE
                )
            elif (
                ArchiveSpectralModeStatus.UNKNOWN_INVALID_VALUE
                in statuses
            ):
                unknown_status = (
                    ArchiveSpectralModeStatus.UNKNOWN_INVALID_VALUE
                )
            else:
                unknown_status = (
                    ArchiveSpectralModeStatus.UNKNOWN_MISSING_VALUE
                )

        resolved.append(
            _association_evidence(
                association_key=association_key,
                supporting_raw_row_ids=raw_row_ids,
                spectral_axis_elements=None,
                frequency_support_type=(
                    ArchiveFrequencySupportType.UNKNOWN
                ),
                correlator_mode=ArchiveCorrelatorMode.UNKNOWN,
                status=unknown_status,
            )
        )

    return tuple(resolved)
