"""Typed scientific evidence projected from ALMA Archive rows.

The objects in this module are source evidence, not duplication decisions.
They keep Archive semantics, units, provenance, and missing/invalid states
explicit so that later cross-source comparison cannot rely on bare floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ArchiveQuantityStatus(StrEnum):
    """Availability of one unit-bearing Archive value."""

    AVAILABLE = "AVAILABLE"
    MISSING_VALUE = "MISSING_VALUE"
    INVALID_VALUE = "INVALID_VALUE"
    MISSING_FIELD_METADATA = "MISSING_FIELD_METADATA"
    INCOMPATIBLE_SOURCE_DATATYPE = "INCOMPATIBLE_SOURCE_DATATYPE"
    MISSING_SOURCE_UNIT = "MISSING_SOURCE_UNIT"
    INCOMPATIBLE_SOURCE_UNIT = "INCOMPATIBLE_SOURCE_UNIT"


class ArchiveUnitConformance(StrEnum):
    """Relationship between live TAP units and the field contract."""

    EXACT = "EXACT"
    COMPATIBLE_CONVERSION = "COMPATIBLE_CONVERSION"
    MISSING_FIELD_METADATA = "MISSING_FIELD_METADATA"
    MISSING_SOURCE_UNIT = "MISSING_SOURCE_UNIT"
    INCOMPATIBLE_SOURCE_UNIT = "INCOMPATIBLE_SOURCE_UNIT"


class ArchiveFrequencyFrameStatus(StrEnum):
    """Public evidence for the Archive sky-frequency reference frame."""

    SKY_FREQUENCY_FRAME_UNSPECIFIED = (
        "SKY_FREQUENCY_FRAME_UNSPECIFIED"
    )


class ArchiveSensitivityKind(StrEnum):
    """Two distinct sensitivity estimates exposed by the Archive."""

    LINE_10_KMS = "LINE_10_KMS"
    CONTINUUM_AGGREGATE_BANDWIDTH = (
        "CONTINUUM_AGGREGATE_BANDWIDTH"
    )


class ArchiveSensitivityBasis(StrEnum):
    """Documented basis of Archive sensitivity evidence."""

    QA0_EB_METADATA_CALCULATOR_ESTIMATE = (
        "QA0_EB_METADATA_CALCULATOR_ESTIMATE"
    )


class ArchiveFrequencySupportType(StrEnum):
    """Archive UI-compatible frequency-support classification."""

    CONTINUUM = "CONTINUUM"
    LINE = "LINE"
    UNKNOWN = "UNKNOWN"


class ArchiveCorrelatorMode(StrEnum):
    """Correlator mode mapped from Archive frequency-support type."""

    TDM = "TDM"
    FDM = "FDM"
    UNKNOWN = "UNKNOWN"


class ArchiveSpectralModeStatus(StrEnum):
    """Derivation status for one row or Source-SPW association."""

    DERIVED = "DERIVED"
    UNKNOWN_MISSING_VALUE = "UNKNOWN_MISSING_VALUE"
    UNKNOWN_INVALID_VALUE = "UNKNOWN_INVALID_VALUE"
    UNKNOWN_METADATA_UNUSABLE = "UNKNOWN_METADATA_UNUSABLE"
    UNKNOWN_CONFLICT = "UNKNOWN_CONFLICT"


class ArchiveSpectralModeClassificationSource(StrEnum):
    """Rule used to reproduce the Archive UI support type."""

    ARCHIVE_UI_CHANNEL_COUNT_RULE = (
        "ARCHIVE_UI_CHANNEL_COUNT_RULE"
    )


class ArchiveCorrelatorModeMappingSource(StrEnum):
    """Published mapping from support type to correlator mode."""

    SCIENCE_ARCHIVE_MANUAL = "SCIENCE_ARCHIVE_MANUAL"


class ArchiveEvidenceIssueKind(StrEnum):
    """Structured reason why typed evidence is unavailable."""

    FIELD_METADATA_UNUSABLE = "FIELD_METADATA_UNUSABLE"
    VALUE_MISSING = "VALUE_MISSING"
    VALUE_INVALID = "VALUE_INVALID"
    FREQUENCY_INTERVAL_INVALID = "FREQUENCY_INTERVAL_INVALID"
    ARCHIVE_FRAME_UNSPECIFIED = "ARCHIVE_FRAME_UNSPECIFIED"


@dataclass(frozen=True, slots=True)
class ArchiveEvidenceProvenance:
    """Location of one projected value in a TAP query result."""

    query_run_id: str
    raw_row_id: str
    result_index: int
    source_field: str
    source_ucd: str | None


@dataclass(frozen=True, slots=True)
class ArchiveEvidenceIssue:
    """One non-policy diagnostic attached to Archive evidence."""

    kind: ArchiveEvidenceIssueKind
    message: str
    source_field: str | None = None


@dataclass(frozen=True, slots=True)
class ArchiveQuantity:
    """One raw scalar converted through its live TAP unit descriptor."""

    raw_value: object
    source_unit: str | None
    canonical_value: float | None
    canonical_unit: str
    status: ArchiveQuantityStatus
    unit_conformance: ArchiveUnitConformance
    provenance: ArchiveEvidenceProvenance

    @property
    def is_available(self) -> bool:
        return self.status is ArchiveQuantityStatus.AVAILABLE


@dataclass(frozen=True, slots=True)
class ArchiveFrequencyInterval:
    """Archive sky-frequency coverage derived from centre and bandwidth."""

    centre: ArchiveQuantity
    bandwidth: ArchiveQuantity
    lower_ghz: float | None
    upper_ghz: float | None
    frame_status: ArchiveFrequencyFrameStatus
    derivation: str = "centre_ghz +/- bandwidth_ghz / 2"

    @property
    def is_available(self) -> bool:
        return (
            self.lower_ghz is not None
            and self.upper_ghz is not None
        )


@dataclass(frozen=True, slots=True)
class ArchiveSpectralResolution:
    """Archive spectral-resolution evidence in canonical kHz."""

    quantity: ArchiveQuantity
    semantic_basis: str = (
        "Archive lowest spectral resolution; not assumed to be "
        "native channel spacing"
    )


@dataclass(frozen=True, slots=True)
class ArchiveAngularResolution:
    """Archive angular-resolution estimate in canonical arcseconds."""

    quantity: ArchiveQuantity
    semantic_basis: str = (
        "Archive approximate spatial resolution for robust=0.5"
    )


@dataclass(frozen=True, slots=True)
class ArchiveSensitivityEstimate:
    """Metadata-based Archive estimate, never achieved FITS RMS."""

    quantity: ArchiveQuantity
    kind: ArchiveSensitivityKind
    basis: ArchiveSensitivityBasis = (
        ArchiveSensitivityBasis
        .QA0_EB_METADATA_CALCULATOR_ESTIMATE
    )


@dataclass(frozen=True, slots=True)
class ArchiveSpectralModeEvidence:
    """Per-row mode evidence derived from the public TAP ``em_xel``.

    ``spectral_axis_elements`` is populated only after the raw value and
    source datatype have passed validation.  FDM/TDM remains derived
    evidence because TAP does not expose either label directly.
    """

    raw_spectral_axis_elements: object
    spectral_axis_elements: int | None
    frequency_support_type: ArchiveFrequencySupportType
    correlator_mode: ArchiveCorrelatorMode
    status: ArchiveSpectralModeStatus
    source_datatype: str | None
    classification_source: ArchiveSpectralModeClassificationSource
    classification_version: str
    mapping_source: ArchiveCorrelatorModeMappingSource
    mapping_version: str

    @property
    def is_derived(self) -> bool:
        return self.status is ArchiveSpectralModeStatus.DERIVED


@dataclass(frozen=True, slots=True)
class ArchiveComparisonEvidence:
    """Typed Archive row projection for a later comparison adapter."""

    frequency: ArchiveFrequencyInterval
    spectral_resolution: ArchiveSpectralResolution
    angular_resolution: ArchiveAngularResolution
    line_sensitivity: ArchiveSensitivityEstimate
    continuum_sensitivity: ArchiveSensitivityEstimate
    issues: tuple[ArchiveEvidenceIssue, ...]

    @property
    def unit_safe(self) -> bool:
        """Return whether every selected quantity used valid live units."""

        quantities = (
            self.frequency.centre,
            self.frequency.bandwidth,
            self.spectral_resolution.quantity,
            self.angular_resolution.quantity,
            self.line_sensitivity.quantity,
            self.continuum_sensitivity.quantity,
        )
        unsafe_statuses = {
            ArchiveQuantityStatus.MISSING_FIELD_METADATA,
            ArchiveQuantityStatus.INCOMPATIBLE_SOURCE_DATATYPE,
            ArchiveQuantityStatus.MISSING_SOURCE_UNIT,
            ArchiveQuantityStatus.INCOMPATIBLE_SOURCE_UNIT,
        }
        return all(
            quantity.status not in unsafe_statuses
            for quantity in quantities
        )

    @property
    def has_frequency_coverage(self) -> bool:
        return self.frequency.is_available

    @property
    def cross_source_frequency_ready(self) -> bool:
        """Remain false until an Archive/Queue frame mapping is approved."""

        return False
