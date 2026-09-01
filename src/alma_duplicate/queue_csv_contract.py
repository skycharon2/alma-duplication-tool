"""Versioned schema and metadata contract for the Queue CSV."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

QUEUE_SCHEMA_VERSION: Final = "cycle13-queue-csv-v1"
QUEUE_CONTRACT_VERSION: Final = "1"
QUEUE_SPW_SLOT_COUNT: Final = 16
QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC: Final = 1e-6
QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ: Final = 1e-12
QUEUE_EVIDENCE_SNAPSHOT_SHA256: Final = (
    "8657108b59295c62d3f1f6635bf35714"
    "04f5d43bc5800c4a2e7ea3ba51a111b5"
)


class QueueFieldKind(StrEnum):
    """Syntactic value kind expected from an operational column."""

    TEXT = "TEXT"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    CATEGORY = "CATEGORY"


class QueueFieldScope(StrEnum):
    """Reconstruction scope to which a field contributes."""

    IDENTITY = "IDENTITY"
    SPATIAL = "SPATIAL"
    VELOCITY = "VELOCITY"
    REQUEST = "REQUEST"
    SENSITIVITY = "SENSITIVITY"
    SPS = "SPS"
    REGULAR_SPW = "REGULAR_SPW"


class QueueMetadataStatus(StrEnum):
    """Relationship between the two source metadata representations."""

    AGREED = "AGREED"
    NO_UNIT = "NO_UNIT"
    HEADER_CONTINUATION = "HEADER_CONTINUATION"
    LEXICAL_VARIANT = "LEXICAL_VARIANT"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"
    CONFLICTING_UNITS = "CONFLICTING_UNITS"


class SecondaryTokenKind(StrEnum):
    """Lexical role of a token below the operational header."""

    BLANK = "BLANK"
    UNIT = "UNIT"
    HEADER_CONTINUATION = "HEADER_CONTINUATION"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True, slots=True)
class QueueFieldSpec:
    """One operational field and its preserved metadata evidence."""

    source_name: str
    canonical_name: str
    kind: QueueFieldKind
    scope: QueueFieldScope
    canonical_unit: str | None
    dictionary_name: str
    dictionary_declaration: str | None
    secondary_token: str | None
    metadata_status: QueueMetadataStatus
    value_nullable: bool

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ValueError("source_name must not be blank")
        if not self.canonical_name.strip():
            raise ValueError("canonical_name must not be blank")
        if not self.dictionary_name.strip():
            raise ValueError("dictionary_name must not be blank")
        if (
            self.metadata_status
            is QueueMetadataStatus.HEADER_CONTINUATION
            and not self.secondary_token
        ):
            raise ValueError(
                "header-continuation metadata requires a token"
            )


@dataclass(frozen=True, slots=True)
class QueueSpwColumns:
    """The three operational columns aligned to one SPW number."""

    number: int
    frequency: str
    bandwidth: str
    spectral_resolution: str

    def __post_init__(self) -> None:
        if not 1 <= self.number <= QUEUE_SPW_SLOT_COUNT:
            raise ValueError("SPW number is outside the v1 contract")


QUEUE_SCALAR_COLUMNS: Final = (
    "Project Code",
    "Target Name",
    "RA",
    "Dec",
    "RA_HMS",
    "Dec_DMS",
    "Long Offset",
    "Lat Offset",
    "Velocity",
    "Vel. Frame",
    "Vel. Convention",
    "Mosaic",
    "Mos. Length",
    "Mos. Width",
    "Mos. PA",
    "Mos. Spacing",
    "Mos. Coord.",
    "Band",
    "Req. Ang. Res.",
    "Req. LAS",
    "Use 7-m?",
    "Use TP?",
    "Polarization",
    "Ref.Frequency",
    "Ref.Freq.Width",
    "Req.Sensitivity",
    "Is Sky Freq?",
    "SPS Start Freq.",
    "SPS End Freq.",
    "SPS Bandwidth",
    "SPS Spec. Res.",
)

QUEUE_FREQUENCY_COLUMNS: Final = tuple(
    f"Freq SPW {number}"
    for number in range(1, QUEUE_SPW_SLOT_COUNT + 1)
)
QUEUE_BANDWIDTH_COLUMNS: Final = tuple(
    f"Bandwidth SPW {number}"
    for number in range(1, QUEUE_SPW_SLOT_COUNT + 1)
)
QUEUE_SPECTRAL_RESOLUTION_COLUMNS: Final = tuple(
    f"Spec.Res. SPW {number}"
    for number in range(1, QUEUE_SPW_SLOT_COUNT + 1)
)

QUEUE_EXPECTED_COLUMNS: Final = (
    QUEUE_SCALAR_COLUMNS
    + QUEUE_FREQUENCY_COLUMNS
    + QUEUE_BANDWIDTH_COLUMNS
    + QUEUE_SPECTRAL_RESOLUTION_COLUMNS
)

QUEUE_SPS_COLUMNS: Final = (
    "SPS Start Freq.",
    "SPS End Freq.",
    "SPS Bandwidth",
    "SPS Spec. Res.",
)

QUEUE_DICTIONARY_ONLY_FIELDS: Final = (
    "standAlone_ACA",
)

QUEUE_DICTIONARY_ALIASES = MappingProxyType(
    {
        "Mos. Coord. Ref. Sys": "Mos. Coord.",
        "Req.LAS": "Req. LAS",
        "Spec.Res SPW [N]": "Spec.Res. SPW N",
    }
)


def spw_columns(number: int) -> QueueSpwColumns:
    """Return the aligned fields for one numbered SPW slot."""

    return QueueSpwColumns(
        number=number,
        frequency=f"Freq SPW {number}",
        bandwidth=f"Bandwidth SPW {number}",
        spectral_resolution=f"Spec.Res. SPW {number}",
    )


QUEUE_SPW_COLUMNS: Final = tuple(
    spw_columns(number)
    for number in range(1, QUEUE_SPW_SLOT_COUNT + 1)
)


def _spec(
    source_name: str,
    canonical_name: str,
    kind: QueueFieldKind,
    scope: QueueFieldScope,
    *,
    canonical_unit: str | None = None,
    dictionary_name: str | None = None,
    dictionary_declaration: str | None = None,
    secondary_token: str | None = None,
    metadata_status: QueueMetadataStatus,
    value_nullable: bool = False,
) -> QueueFieldSpec:
    return QueueFieldSpec(
        source_name=source_name,
        canonical_name=canonical_name,
        kind=kind,
        scope=scope,
        canonical_unit=canonical_unit,
        dictionary_name=dictionary_name or source_name,
        dictionary_declaration=dictionary_declaration,
        secondary_token=secondary_token,
        metadata_status=metadata_status,
        value_nullable=value_nullable,
    )


def _scalar_specs() -> tuple[QueueFieldSpec, ...]:
    no_unit = QueueMetadataStatus.NO_UNIT
    agreed = QueueMetadataStatus.AGREED

    return (
        _spec(
            "Project Code", "project_code",
            QueueFieldKind.TEXT, QueueFieldScope.IDENTITY,
            dictionary_declaration="string",
            metadata_status=no_unit,
        ),
        _spec(
            "Target Name", "target_name",
            QueueFieldKind.TEXT, QueueFieldScope.IDENTITY,
            dictionary_declaration="string",
            metadata_status=no_unit,
        ),
        _spec(
            "RA", "ra_deg",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="deg",
            dictionary_declaration="[deg]",
            secondary_token="[deg]",
            metadata_status=agreed,
        ),
        _spec(
            "Dec", "dec_deg",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="deg",
            dictionary_declaration="[deg]",
            secondary_token="[deg]",
            metadata_status=agreed,
        ),
        _spec(
            "RA_HMS", "ra_hms",
            QueueFieldKind.TEXT, QueueFieldScope.SPATIAL,
            dictionary_declaration="[h:m:s]",
            metadata_status=no_unit,
        ),
        _spec(
            "Dec_DMS", "dec_dms",
            QueueFieldKind.TEXT, QueueFieldScope.SPATIAL,
            dictionary_declaration="[d:m:s]",
            metadata_status=no_unit,
        ),
        _spec(
            "Long Offset", "long_offset_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="arcsec",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
        ),
        _spec(
            "Lat Offset", "lat_offset_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="arcsec",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
        ),
        _spec(
            "Velocity", "velocity_kms",
            QueueFieldKind.NUMBER, QueueFieldScope.VELOCITY,
            canonical_unit="km/s",
            dictionary_declaration="[km/s]",
            secondary_token="[kms/s]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
        ),
        _spec(
            "Vel. Frame", "velocity_frame",
            QueueFieldKind.CATEGORY, QueueFieldScope.VELOCITY,
            dictionary_declaration="string",
            metadata_status=no_unit,
        ),
        _spec(
            "Vel. Convention", "velocity_convention",
            QueueFieldKind.CATEGORY, QueueFieldScope.VELOCITY,
            dictionary_declaration="string",
            metadata_status=no_unit,
        ),
        _spec(
            "Mosaic", "mosaic_kind",
            QueueFieldKind.CATEGORY, QueueFieldScope.SPATIAL,
            dictionary_declaration="[boolean]",
            metadata_status=QueueMetadataStatus.SEMANTIC_CONFLICT,
            value_nullable=True,
        ),
        _spec(
            "Mos. Length", "mosaic_length_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="arcsec",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
            value_nullable=True,
        ),
        _spec(
            "Mos. Width", "mosaic_width_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="arcsec",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
            value_nullable=True,
        ),
        _spec(
            "Mos. PA", "mosaic_pa_deg",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="deg",
            dictionary_declaration="[deg]",
            secondary_token="[deg]",
            metadata_status=agreed,
            value_nullable=True,
        ),
        _spec(
            "Mos. Spacing", "mosaic_spacing_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.SPATIAL,
            canonical_unit="arcsec",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
            value_nullable=True,
        ),
        _spec(
            "Mos. Coord.", "mosaic_coordinate_system",
            QueueFieldKind.CATEGORY, QueueFieldScope.SPATIAL,
            dictionary_name="Mos. Coord. Ref. Sys",
            dictionary_declaration="string",
            secondary_token="Ref. Sys.",
            metadata_status=QueueMetadataStatus.HEADER_CONTINUATION,
            value_nullable=True,
        ),
        _spec(
            "Band", "band",
            QueueFieldKind.CATEGORY, QueueFieldScope.IDENTITY,
            dictionary_declaration="string",
            metadata_status=no_unit,
        ),
        _spec(
            "Req. Ang. Res.", "requested_angular_resolution_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.REQUEST,
            canonical_unit="arcsec",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
        ),
        _spec(
            "Req. LAS", "requested_las_arcsec",
            QueueFieldKind.NUMBER, QueueFieldScope.REQUEST,
            canonical_unit="arcsec",
            dictionary_name="Req.LAS",
            dictionary_declaration='["]',
            secondary_token="[arcsec]",
            metadata_status=QueueMetadataStatus.LEXICAL_VARIANT,
        ),
        _spec(
            "Use 7-m?", "use_7m",
            QueueFieldKind.BOOLEAN, QueueFieldScope.REQUEST,
            dictionary_declaration="[boolean]",
            metadata_status=no_unit,
        ),
        _spec(
            "Use TP?", "use_tp",
            QueueFieldKind.BOOLEAN, QueueFieldScope.REQUEST,
            dictionary_declaration="[boolean]",
            metadata_status=no_unit,
        ),
        _spec(
            "Polarization", "polarization",
            QueueFieldKind.CATEGORY, QueueFieldScope.REQUEST,
            dictionary_declaration="[FULL/DOUBLE/SINGLE]",
            metadata_status=no_unit,
        ),
        _spec(
            "Ref.Frequency", "reference_frequency_ghz",
            QueueFieldKind.NUMBER, QueueFieldScope.SENSITIVITY,
            canonical_unit="GHz",
            dictionary_declaration="[GHz]",
            secondary_token="[GHz]",
            metadata_status=agreed,
        ),
        _spec(
            "Ref.Freq.Width", "reference_width_mhz",
            QueueFieldKind.NUMBER, QueueFieldScope.SENSITIVITY,
            canonical_unit="MHz",
            dictionary_declaration="[MHz]",
            secondary_token="[MHz]",
            metadata_status=agreed,
        ),
        _spec(
            "Req.Sensitivity", "requested_sensitivity_mjy",
            QueueFieldKind.NUMBER, QueueFieldScope.SENSITIVITY,
            canonical_unit="mJy",
            dictionary_declaration="[mJy]",
            secondary_token="[mJy]",
            metadata_status=agreed,
        ),
        _spec(
            "Is Sky Freq?", "is_sky_frequency",
            QueueFieldKind.BOOLEAN, QueueFieldScope.VELOCITY,
            dictionary_declaration="[boolean]",
            metadata_status=no_unit,
        ),
        _spec(
            "SPS Start Freq.", "sps_start_frequency_ghz",
            QueueFieldKind.NUMBER, QueueFieldScope.SPS,
            canonical_unit="GHz",
            dictionary_declaration="[GHz]",
            secondary_token="[GHz]",
            metadata_status=agreed,
            value_nullable=True,
        ),
        _spec(
            "SPS End Freq.", "sps_end_frequency_ghz",
            QueueFieldKind.NUMBER, QueueFieldScope.SPS,
            canonical_unit="GHz",
            dictionary_declaration="[GHz]",
            secondary_token="[GHz]",
            metadata_status=agreed,
            value_nullable=True,
        ),
        _spec(
            "SPS Bandwidth", "sps_bandwidth_mhz",
            QueueFieldKind.NUMBER, QueueFieldScope.SPS,
            canonical_unit="MHz",
            dictionary_declaration="[MHz]",
            secondary_token="[GHz]",
            metadata_status=QueueMetadataStatus.CONFLICTING_UNITS,
            value_nullable=True,
        ),
        _spec(
            "SPS Spec. Res.", "sps_spectral_resolution_mhz",
            QueueFieldKind.NUMBER, QueueFieldScope.SPS,
            canonical_unit="MHz",
            dictionary_declaration="[MHz]",
            secondary_token="[MHz]",
            metadata_status=agreed,
            value_nullable=True,
        ),
    )


def _spw_specs() -> tuple[QueueFieldSpec, ...]:
    frequency_specs = tuple(
        _spec(
            columns.frequency,
            f"spw_{columns.number:02d}_frequency_ghz",
            QueueFieldKind.NUMBER,
            QueueFieldScope.REGULAR_SPW,
            canonical_unit="GHz",
            dictionary_name="Freq SPW [N]",
            dictionary_declaration="[GHz]",
            secondary_token="[GHz]",
            metadata_status=QueueMetadataStatus.AGREED,
            value_nullable=True,
        )
        for columns in QUEUE_SPW_COLUMNS
    )
    bandwidth_specs = tuple(
        _spec(
            columns.bandwidth,
            f"spw_{columns.number:02d}_bandwidth_mhz",
            QueueFieldKind.NUMBER,
            QueueFieldScope.REGULAR_SPW,
            canonical_unit="MHz",
            dictionary_name="Bandwidth SPW [N]",
            dictionary_declaration="[MHz]",
            secondary_token="[MHz]",
            metadata_status=QueueMetadataStatus.AGREED,
            value_nullable=True,
        )
        for columns in QUEUE_SPW_COLUMNS
    )
    resolution_specs = tuple(
        _spec(
            columns.spectral_resolution,
            f"spw_{columns.number:02d}_spectral_resolution_mhz",
            QueueFieldKind.NUMBER,
            QueueFieldScope.REGULAR_SPW,
            canonical_unit="MHz",
            dictionary_name="Spec.Res SPW [N]",
            dictionary_declaration="[MHz]",
            secondary_token="[MHz]",
            metadata_status=QueueMetadataStatus.AGREED,
            value_nullable=True,
        )
        for columns in QUEUE_SPW_COLUMNS
    )
    return (
        frequency_specs
        + bandwidth_specs
        + resolution_specs
    )


_QUEUE_FIELD_SPEC_SEQUENCE: Final = (
    _scalar_specs() + _spw_specs()
)
QUEUE_FIELD_SPECS = MappingProxyType(
    {
        spec.source_name: spec
        for spec in _QUEUE_FIELD_SPEC_SEQUENCE
    }
)

QUEUE_EXPECTED_SECONDARY_HEADER: Final = tuple(
    spec.secondary_token or ""
    for spec in _QUEUE_FIELD_SPEC_SEQUENCE
)


def classify_secondary_token(
    source_name: str,
    token: str,
) -> SecondaryTokenKind:
    """Classify one raw secondary-header token without coercion."""

    stripped = token.strip()
    if not stripped:
        return SecondaryTokenKind.BLANK
    if (
        source_name == "Mos. Coord."
        and stripped == "Ref. Sys."
    ):
        return SecondaryTokenKind.HEADER_CONTINUATION
    if stripped.startswith("[") and stripped.endswith("]"):
        return SecondaryTokenKind.UNIT
    return SecondaryTokenKind.UNEXPECTED


if len(QUEUE_EXPECTED_COLUMNS) != 79:
    raise RuntimeError("Queue v1 schema must contain 79 columns")
if len(set(QUEUE_EXPECTED_COLUMNS)) != 79:
    raise RuntimeError("Queue v1 schema contains duplicate columns")
if tuple(QUEUE_FIELD_SPECS) != QUEUE_EXPECTED_COLUMNS:
    raise RuntimeError(
        "Queue field specifications must match source column order"
    )
if len(QUEUE_EXPECTED_SECONDARY_HEADER) != 79:
    raise RuntimeError(
        "Queue secondary-header contract must contain 79 tokens"
    )
