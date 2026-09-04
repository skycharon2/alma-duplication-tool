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
