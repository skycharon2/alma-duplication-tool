"""Domain objects for current-cycle Queue CSV ingestion."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias


class QueueParseStatus(StrEnum):
    """Completeness of one Queue CSV ingestion run."""

    COMPLETE = "COMPLETE"
    COMPLETE_WITH_WARNINGS = "COMPLETE_WITH_WARNINGS"
    ERROR = "ERROR"


class QueueIssueSeverity(StrEnum):
    """Impact of one Queue ingestion issue."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class QueueIssueKind(StrEnum):
    """Structured reason reported by Queue ingestion."""

    LAYOUT_NOT_FOUND = "LAYOUT_NOT_FOUND"
    MALFORMED_DICTIONARY_ENTRY = "MALFORMED_DICTIONARY_ENTRY"
    DUPLICATE_DICTIONARY_ENTRY = "DUPLICATE_DICTIONARY_ENTRY"
    DUPLICATE_COLUMN = "DUPLICATE_COLUMN"
    MISSING_REQUIRED_COLUMN = "MISSING_REQUIRED_COLUMN"
    UNEXPECTED_COLUMN = "UNEXPECTED_COLUMN"
    REORDERED_COLUMNS = "REORDERED_COLUMNS"
    ROW_WIDTH_MISMATCH = "ROW_WIDTH_MISMATCH"
    MISSING_REQUIRED_VALUE = "MISSING_REQUIRED_VALUE"
    INVALID_NUMERIC_VALUE = "INVALID_NUMERIC_VALUE"
    INVALID_BOOLEAN_VALUE = "INVALID_BOOLEAN_VALUE"
    UNSUPPORTED_CATEGORY = "UNSUPPORTED_CATEGORY"
    PARTIAL_SPW_TRIPLE = "PARTIAL_SPW_TRIPLE"
    NONCONTIGUOUS_SPW_SLOTS = (
        "NONCONTIGUOUS_SPW_SLOTS"
    )
    PARTIAL_SPS_RECORD = "PARTIAL_SPS_RECORD"
    MIXED_REGULAR_AND_SPS = "MIXED_REGULAR_AND_SPS"
    MISSING_SPECTRAL_REPRESENTATION = (
        "MISSING_SPECTRAL_REPRESENTATION"
    )
    CONFLICTING_UNIT_DECLARATION = (
        "CONFLICTING_UNIT_DECLARATION"
    )
    METADATA_DECLARATION_DRIFT = (
        "METADATA_DECLARATION_DRIFT"
    )
    REFERENCE_FREQUENCY_OUTSIDE_COVERAGE = (
        "REFERENCE_FREQUENCY_OUTSIDE_COVERAGE"
    )
    INVALID_FREQUENCY_INTERVAL = (
        "INVALID_FREQUENCY_INTERVAL"
    )
    INCOMPLETE_RECTANGLE_GEOMETRY = (
        "INCOMPLETE_RECTANGLE_GEOMETRY"
    )
    SCHEMA_DRIFT = "SCHEMA_DRIFT"


class QueueMosaicKind(StrEnum):
    """Evidence-based spatial classification of one Queue row."""

    SINGLE_FIELD = "SINGLE_FIELD"
    CUSTOM_POINTING = "CUSTOM_POINTING"
    RECTANGULAR_MOSAIC = "RECTANGULAR_MOSAIC"
    UNSPECIFIED_WITH_OFFSET = "UNSPECIFIED_WITH_OFFSET"
    UNKNOWN = "UNKNOWN"


class QueueFrequencyDerivationKind(StrEnum):
    """How a Queue source frequency became a sky frequency."""

    DECLARED_SKY_FREQUENCY = "DECLARED_SKY_FREQUENCY"
    RADIO_DOPPLER = "RADIO_DOPPLER"
    OPTICAL_DOPPLER = "OPTICAL_DOPPLER"
    RELATIVISTIC_DOPPLER = "RELATIVISTIC_DOPPLER"


class QueueUsableBandwidthDerivationKind(StrEnum):
    """How a Queue usable SPW width was interpreted."""

    NOMINAL_MAPPED = "NOMINAL_MAPPED"
    ALREADY_USABLE = "ALREADY_USABLE"
    UNRECOGNIZED = "UNRECOGNIZED"


class QueueUsableBandwidthApplicability(StrEnum):
    """Scientific-policy readiness of the portal-script mapping."""

    PENDING_ARRAY_PROCESSOR_CONFIRMATION = (
        "PENDING_ARRAY_PROCESSOR_CONFIRMATION"
    )


class QueueCapabilityStatus(StrEnum):
    """Availability of evidence required by later rule layers."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class QueueUnitInterpretation(StrEnum):
    """How a raw numeric token received its canonical unit."""

    DIRECT = "DIRECT"
    LEXICAL_NORMALIZATION = "LEXICAL_NORMALIZATION"
    DICTIONARY_OVERRIDE = "DICTIONARY_OVERRIDE"


@dataclass(frozen=True, slots=True)
class QueueRawRowId:
    """Snapshot-scoped physical source-row identity."""

    snapshot_sha256: str
    physical_start_line: int
    physical_end_line: int

    def __post_init__(self) -> None:
        if len(self.snapshot_sha256) != 64:
            raise ValueError("snapshot_sha256 must contain 64 hex chars")
        if self.physical_start_line <= 0:
            raise ValueError("physical_start_line must be positive")
        if self.physical_end_line < self.physical_start_line:
            raise ValueError(
                "physical_end_line precedes physical_start_line"
            )

    @property
    def value(self) -> str:
        """Return a portable textual row identifier."""

        return (
            f"{self.snapshot_sha256}:"
            f"{self.physical_start_line}"
        )


@dataclass(frozen=True, slots=True)
class QueueParseIssue:
    """One structured Queue-ingestion diagnostic."""

    kind: QueueIssueKind
    severity: QueueIssueSeverity
    message: str
    row_id: QueueRawRowId | None = None
    column: str | None = None
    slot_number: int | None = None
    raw_value: str | None = None


@dataclass(frozen=True, slots=True)
class QueueDictionaryEntry:
    """One exact entry from the embedded source dictionary."""

    physical_start_line: int
    source_name: str
    declaration: str
    description: str


@dataclass(frozen=True, slots=True)
class QueueFieldMetadata:
    """Runtime field metadata reconciled without discarding sources."""

    name: str
    canonical_name: str
    dictionary_name: str
    dictionary_declaration: str | None
    dictionary_description: str | None
    secondary_token: str | None
    canonical_unit: str | None
    metadata_status: str


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    """Provenance and source metadata for one exact CSV snapshot."""

    source_url: str
    snapshot_sha256: str
    captured_at: datetime | None
    byte_length: int
    encoding: str
    description_raw: str
    operational_columns: tuple[str, ...]
    secondary_header_row: tuple[str, ...]
    dictionary_entries: tuple[QueueDictionaryEntry, ...]
    schema_version: str
    parser_version: str

    def __post_init__(self) -> None:
        if not self.source_url.strip():
            raise ValueError("source_url must not be blank")
        if len(self.snapshot_sha256) != 64:
            raise ValueError("snapshot_sha256 must contain 64 hex chars")
        if self.byte_length < 0:
            raise ValueError("byte_length must not be negative")


@dataclass(frozen=True, slots=True)
class RawQueueRow:
    """One operational CSV record before semantic conversion."""

    row_id: QueueRawRowId
    source_ordinal: int
    declared_columns: tuple[str, ...]
    raw_values: tuple[str, ...]
    content_fingerprint: str

    def __post_init__(self) -> None:
        if self.source_ordinal < 0:
            raise ValueError("source_ordinal must not be negative")
        if len(self.content_fingerprint) != 64:
            raise ValueError(
                "content_fingerprint must contain 64 hex chars"
            )

    def value(self, column: str) -> str:
        """Return one exact raw value by declared column name."""

        try:
            index = self.declared_columns.index(column)
        except ValueError as exc:
            raise KeyError(column) from exc
        try:
            return self.raw_values[index]
        except IndexError as exc:
            raise KeyError(column) from exc


@dataclass(frozen=True, slots=True)
class QueueQuantity:
    """A raw numeric token plus lossless unit interpretation evidence."""

    raw_text: str
    raw_value: float
    value: float
    dictionary_unit: str | None
    secondary_unit: str | None
    canonical_unit: str | None
    unit_interpretation: QueueUnitInterpretation
    normalization_version: str

    @property
    def raw_unit(self) -> str | None:
        """Return the physical secondary-header token for compatibility."""

        return self.secondary_unit


@dataclass(frozen=True, slots=True)
class QueueGroupKey:
    """Analytical reconstruction scope, not an ALMA entity ID."""

    project_code: str
    target_name: str
    band: str


@dataclass(frozen=True, slots=True)
class QueueVelocityContext:
    """Velocity evidence required for Queue-side Doppler conversion."""

    velocity_kms: QueueQuantity
    frame_raw: str
    convention_raw: str
    is_sky_frequency: bool


@dataclass(frozen=True, slots=True)
class QueueSensitivityRequest:
    """Proposal-side requested RMS and its reference basis."""

    reference_frequency_ghz: QueueQuantity
    reference_width_mhz: QueueQuantity
    requested_sensitivity_mjy: QueueQuantity


@dataclass(frozen=True, slots=True)
class QueueFrequencyDerivation:
    """Traceable Queue-side conversion of one source frequency."""

    source_frequency_ghz: QueueQuantity
    sky_frequency_ghz: float
    doppler_factor: float
    kind: QueueFrequencyDerivationKind
    velocity_frame_raw: str
    velocity_convention_raw: str
    derivation_version: str


@dataclass(frozen=True, slots=True)
class QueueSpw:
    """One complete numbered regular-SPW record."""

    number: int
    frequency_ghz: QueueQuantity
    bandwidth_mhz: QueueQuantity
    spectral_resolution_mhz: QueueQuantity
    frequency_derivation: QueueFrequencyDerivation
    nominal_bandwidth_ghz: float
    usable_bandwidth_ghz: float
    usable_bandwidth_derivation_version: str
    usable_bandwidth_derivation_kind: (
        QueueUsableBandwidthDerivationKind
    )
    usable_bandwidth_applicability: (
        QueueUsableBandwidthApplicability
    )
    lower_sky_frequency_ghz: float
    upper_sky_frequency_ghz: float
    usable_lower_sky_frequency_ghz: float
    usable_upper_sky_frequency_ghz: float

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise ValueError("SPW number must be positive")
        if not self.usable_bandwidth_derivation_version.strip():
            raise ValueError(
                "usable bandwidth derivation version must not be blank"
            )

        for name, value in (
            ("nominal_bandwidth_ghz", self.nominal_bandwidth_ghz),
            ("usable_bandwidth_ghz", self.usable_bandwidth_ghz),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")

        if self.usable_bandwidth_ghz > self.nominal_bandwidth_ghz:
            raise ValueError(
                "usable bandwidth must not exceed nominal bandwidth"
            )

        for label, lower, upper, width in (
            (
                "nominal",
                self.lower_sky_frequency_ghz,
                self.upper_sky_frequency_ghz,
                self.nominal_bandwidth_ghz,
            ),
            (
                "usable",
                self.usable_lower_sky_frequency_ghz,
                self.usable_upper_sky_frequency_ghz,
                self.usable_bandwidth_ghz,
            ),
        ):
            if (
                not math.isfinite(lower)
                or not math.isfinite(upper)
                or lower <= 0.0
                or lower >= upper
            ):
                raise ValueError(f"{label} frequency interval is invalid")
            if not math.isclose(
                upper - lower,
                width,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    f"{label} interval width does not match bandwidth"
                )

    @property
    def sky_bandwidth_ghz(self) -> float:
        """Compatibility alias for the pre-v2 field name.

        The value is the nominal correlator bandwidth converted to GHz;
        it is not Doppler-scaled.
        """

        return self.nominal_bandwidth_ghz

    @property
    def nominal_lower_sky_frequency_ghz(self) -> float:
        """Explicit name for the conservative nominal lower bound."""

        return self.lower_sky_frequency_ghz

    @property
    def nominal_upper_sky_frequency_ghz(self) -> float:
        """Explicit name for the conservative nominal upper bound."""

        return self.upper_sky_frequency_ghz


@dataclass(frozen=True, slots=True)
class QueueSpatialEvidence:
    """Typed spatial evidence projected from one raw row."""

    ra_deg: QueueQuantity
    dec_deg: QueueQuantity
    ra_hms_raw: str
    dec_dms_raw: str
    long_offset_arcsec: QueueQuantity
    lat_offset_arcsec: QueueQuantity
    mosaic_raw: str
    mosaic_kind: QueueMosaicKind
    mosaic_length_arcsec: QueueQuantity | None
    mosaic_width_arcsec: QueueQuantity | None
    mosaic_pa_deg: QueueQuantity | None
    mosaic_spacing_arcsec: QueueQuantity | None
    coordinate_system_raw: str
    zero_tolerance_arcsec: float


@dataclass(frozen=True, slots=True)
class QueueRequestEvidence:
    """Typed resolution, array, and polarization request."""

    requested_angular_resolution_arcsec: QueueQuantity
    requested_las_arcsec: QueueQuantity
    use_7m: bool
    use_tp: bool
    polarization_raw: str


@dataclass(frozen=True, slots=True)
class RegularSpwEvidence:
    """One row's complete regular-SPW setup."""

    spws: tuple[QueueSpw, ...]
    velocity: QueueVelocityContext
    sensitivity: QueueSensitivityRequest


@dataclass(frozen=True, slots=True)
class SpectralScanEvidence:
    """One row's complete spectral-scan setup."""

    start_frequency_ghz: QueueQuantity
    end_frequency_ghz: QueueQuantity
    per_window_bandwidth_mhz: QueueQuantity
    spectral_resolution_mhz: QueueQuantity
    lower_sky_frequency_ghz: float
    upper_sky_frequency_ghz: float
    doppler_factor: float
    velocity: QueueVelocityContext
    sensitivity: QueueSensitivityRequest
    window_expansion_status: str = "UNAVAILABLE"


QueueSpectralEvidence: TypeAlias = (
    RegularSpwEvidence | SpectralScanEvidence
)


@dataclass(frozen=True, slots=True)
class QueueRowInput:
    """One fully typed row ready for deterministic reconstruction."""

    raw_row: RawQueueRow
    group_key: QueueGroupKey
    spatial: QueueSpatialEvidence
    spectral: QueueSpectralEvidence
    request: QueueRequestEvidence


@dataclass(frozen=True, slots=True)
class QueueCapabilities:
    """Scientific capabilities exposed by the current source schema."""

    authoritative_correlator_mode: QueueCapabilityStatus
    moving_object_classification: QueueCapabilityStatus
    sps_window_expansion: QueueCapabilityStatus
    archive_frame_alignment: QueueCapabilityStatus


@dataclass(frozen=True, slots=True)
class QueueCsvParseResult:
    """Complete source-neutral result of Queue CSV ingestion."""

    status: QueueParseStatus
    snapshot: QueueSnapshot
    field_metadata: tuple[QueueFieldMetadata, ...]
    raw_rows: tuple[RawQueueRow, ...]
    row_inputs: tuple[QueueRowInput, ...]
    issues: tuple[QueueParseIssue, ...]
    capabilities: QueueCapabilities

    @property
    def is_complete(self) -> bool:
        return self.status in {
            QueueParseStatus.COMPLETE,
            QueueParseStatus.COMPLETE_WITH_WARNINGS,
        }

    @property
    def can_reconstruct(self) -> bool:
        return (
            self.is_complete
            and len(self.raw_rows) == len(self.row_inputs)
        )


@dataclass(frozen=True, slots=True)
class QueueSpatialComponent:
    """One factored spatial component and its source rows."""

    component_id: str
    group_key: QueueGroupKey
    evidence: QueueSpatialEvidence
    source_row_ids: tuple[QueueRawRowId, ...]


@dataclass(frozen=True, slots=True)
class QueueSpectralSetup:
    """One factored spectral setup and its source rows."""

    setup_id: str
    group_key: QueueGroupKey
    evidence: QueueSpectralEvidence
    source_row_ids: tuple[QueueRawRowId, ...]


@dataclass(frozen=True, slots=True)
class QueueRequestContext:
    """One factored request context and its source rows."""

    context_id: str
    group_key: QueueGroupKey
    evidence: QueueRequestEvidence
    source_row_ids: tuple[QueueRawRowId, ...]


@dataclass(frozen=True, slots=True)
class QueueRowAssociation:
    """The only observed spatial-spectral-request link for one row."""

    raw_row_id: QueueRawRowId
    group_key: QueueGroupKey
    spatial_component_id: str
    spectral_setup_id: str
    request_context_id: str
    content_fingerprint: str


@dataclass(frozen=True, slots=True)
class QueueFactorizationSummary:
    """Observed-versus-potential association census for one group."""

    group_key: QueueGroupKey
    raw_row_count: int
    spatial_component_count: int
    spectral_setup_count: int
    observed_pair_count: int
    potential_pair_count: int
    repeated_association_count: int

    @property
    def is_sparse(self) -> bool:
        return self.observed_pair_count < self.potential_pair_count


@dataclass(frozen=True, slots=True)
class QueueReconstructionBatch:
    """Canonical observed-association reconstruction output."""

    spatial_components: tuple[QueueSpatialComponent, ...]
    spectral_setups: tuple[QueueSpectralSetup, ...]
    request_contexts: tuple[QueueRequestContext, ...]
    associations: tuple[QueueRowAssociation, ...]
    factorization: tuple[QueueFactorizationSummary, ...]
    reconstruction_version: str

    @property
    def sparse_group_count(self) -> int:
        return sum(summary.is_sparse for summary in self.factorization)


@dataclass(frozen=True, slots=True)
class QueuePipelineBatch:
    """Completed Queue ingestion and reconstruction evidence."""

    parse_result: QueueCsvParseResult
    reconstruction: QueueReconstructionBatch
    adapter_version: str
