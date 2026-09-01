"""Runtime unit contract for Archive comparison evidence."""

from __future__ import annotations

from dataclasses import dataclass
import math

from astropy import units as u

from alma_duplicate.clients.archive_contract import (
    RawArchiveRow,
    TapFieldMetadata,
)
from alma_duplicate.domain.archive_evidence import (
    ArchiveAngularResolution,
    ArchiveComparisonEvidence,
    ArchiveEvidenceIssue,
    ArchiveEvidenceIssueKind,
    ArchiveEvidenceProvenance,
    ArchiveFrequencyFrameStatus,
    ArchiveFrequencyInterval,
    ArchiveQuantity,
    ArchiveQuantityStatus,
    ArchiveSensitivityEstimate,
    ArchiveSensitivityKind,
    ArchiveSpectralResolution,
    ArchiveUnitConformance,
)


ARCHIVE_COMPARISON_CONTRACT_VERSION = "1"


@dataclass(frozen=True, slots=True)
class ArchiveFieldSpec:
    """Expected live unit and canonical unit for one Archive field."""

    name: str
    expected_unit: str
    canonical_unit: str
    expected_datatypes: tuple[str, ...] = ("double",)
    minimum_value: float | None = 0.0


ARCHIVE_COMPARISON_FIELD_SPECS = (
    ArchiveFieldSpec("frequency", "GHz", "GHz"),
    ArchiveFieldSpec("bandwidth", "Hz", "GHz"),
    ArchiveFieldSpec(
        "spectral_resolution",
        "kHz",
        "kHz",
    ),
    ArchiveFieldSpec(
        "spatial_resolution",
        "arcsec",
        "arcsec",
    ),
    ArchiveFieldSpec(
        "sensitivity_10kms",
        "mJy / beam",
        "mJy / beam",
    ),
    ArchiveFieldSpec(
        "cont_sensitivity_bandwidth",
        "mJy / beam",
        "mJy / beam",
    ),
)


@dataclass(frozen=True, slots=True)
class ArchiveFieldValidation:
    """Live descriptor validation for one comparison field."""

    spec: ArchiveFieldSpec
    metadata: TapFieldMetadata | None
    datatype_usable: bool
    unit_conformance: ArchiveUnitConformance
    conversion_factor: float | None
    message: str | None = None

    @property
    def is_usable(self) -> bool:
        return (
            self.datatype_usable
            and self.unit_conformance in {
                ArchiveUnitConformance.EXACT,
                ArchiveUnitConformance.COMPATIBLE_CONVERSION,
            }
        )


@dataclass(frozen=True, slots=True)
class ArchiveFieldContractValidation:
    """Validated unit conversion plan for one TAP retrieval."""

    fields: tuple[ArchiveFieldValidation, ...]
    contract_version: str = ARCHIVE_COMPARISON_CONTRACT_VERSION

    def field(self, name: str) -> ArchiveFieldValidation:
        for field in self.fields:
            if field.spec.name == name:
                return field
        raise KeyError(name)

    @property
    def is_usable(self) -> bool:
        return all(field.is_usable for field in self.fields)

    @property
    def changed_compatible_units(self) -> tuple[str, ...]:
        return tuple(
            field.spec.name
            for field in self.fields
            if field.unit_conformance
            is ArchiveUnitConformance.COMPATIBLE_CONVERSION
        )

    @property
    def unusable_fields(self) -> tuple[str, ...]:
        return tuple(
            field.spec.name
            for field in self.fields
            if not field.is_usable
        )


def _validate_field(
    spec: ArchiveFieldSpec,
    metadata: TapFieldMetadata | None,
) -> ArchiveFieldValidation:
    if metadata is None:
        return ArchiveFieldValidation(
            spec=spec,
            metadata=None,
            datatype_usable=False,
            unit_conformance=(
                ArchiveUnitConformance.MISSING_FIELD_METADATA
            ),
            conversion_factor=None,
            message="TAP response omitted the field descriptor",
        )

    datatype_usable = (
        metadata.datatype.strip().casefold()
        in {
            datatype.casefold()
            for datatype in spec.expected_datatypes
        }
    )

    if metadata.unit is None or not metadata.unit.strip():
        return ArchiveFieldValidation(
            spec=spec,
            metadata=metadata,
            datatype_usable=datatype_usable,
            unit_conformance=(
                ArchiveUnitConformance.MISSING_SOURCE_UNIT
            ),
            conversion_factor=None,
            message="TAP field descriptor omitted its unit",
        )

    try:
        source_unit = u.Unit(metadata.unit)
        expected_unit = u.Unit(spec.expected_unit)
        canonical_unit = u.Unit(spec.canonical_unit)
        conversion_factor = float(
            (1.0 * source_unit).to_value(canonical_unit)
        )
    except (TypeError, ValueError, u.UnitConversionError) as exc:
        return ArchiveFieldValidation(
            spec=spec,
            metadata=metadata,
            datatype_usable=datatype_usable,
            unit_conformance=(
                ArchiveUnitConformance.INCOMPATIBLE_SOURCE_UNIT
            ),
            conversion_factor=None,
            message=str(exc),
        )

    conformance = (
        ArchiveUnitConformance.EXACT
        if source_unit == expected_unit
        else ArchiveUnitConformance.COMPATIBLE_CONVERSION
    )
    return ArchiveFieldValidation(
        spec=spec,
        metadata=metadata,
        datatype_usable=datatype_usable,
        unit_conformance=conformance,
        conversion_factor=conversion_factor,
    )


def validate_archive_comparison_metadata(
    field_metadata: tuple[TapFieldMetadata, ...],
) -> ArchiveFieldContractValidation:
    """Validate live units without relying on hard-coded row assumptions."""

    by_name = {
        field.name.casefold(): field
        for field in field_metadata
    }
    return ArchiveFieldContractValidation(
        fields=tuple(
            _validate_field(
                spec,
                by_name.get(spec.name.casefold()),
            )
            for spec in ARCHIVE_COMPARISON_FIELD_SPECS
        )
    )


def _is_masked(value: object) -> bool:
    mask = getattr(value, "mask", False)
    try:
        return bool(mask)
    except (TypeError, ValueError):
        return False


def _quantity_status_for_unit(
    conformance: ArchiveUnitConformance,
) -> ArchiveQuantityStatus:
    return {
        ArchiveUnitConformance.MISSING_FIELD_METADATA: (
            ArchiveQuantityStatus.MISSING_FIELD_METADATA
        ),
        ArchiveUnitConformance.MISSING_SOURCE_UNIT: (
            ArchiveQuantityStatus.MISSING_SOURCE_UNIT
        ),
        ArchiveUnitConformance.INCOMPATIBLE_SOURCE_UNIT: (
            ArchiveQuantityStatus.INCOMPATIBLE_SOURCE_UNIT
        ),
    }[conformance]


def _quantity(
    raw_value: object,
    validation: ArchiveFieldValidation,
    *,
    query_run_id: str,
    raw_row_id: str,
    result_index: int,
) -> ArchiveQuantity:
    metadata = validation.metadata
    provenance = ArchiveEvidenceProvenance(
        query_run_id=query_run_id,
        raw_row_id=raw_row_id,
        result_index=result_index,
        source_field=validation.spec.name,
        source_ucd=(
            metadata.ucd
            if metadata is not None
            else None
        ),
    )

    if not validation.is_usable:
        if (
            validation.metadata is not None
            and not validation.datatype_usable
        ):
            status = (
                ArchiveQuantityStatus
                .INCOMPATIBLE_SOURCE_DATATYPE
            )
        else:
            status = _quantity_status_for_unit(
                validation.unit_conformance
            )
        return ArchiveQuantity(
            raw_value=raw_value,
            source_unit=(
                metadata.unit
                if metadata is not None
                else None
            ),
            canonical_value=None,
            canonical_unit=validation.spec.canonical_unit,
            status=status,
            unit_conformance=validation.unit_conformance,
            provenance=provenance,
        )

    if raw_value is None or _is_masked(raw_value):
        return ArchiveQuantity(
            raw_value=raw_value,
            source_unit=metadata.unit,
            canonical_value=None,
            canonical_unit=validation.spec.canonical_unit,
            status=ArchiveQuantityStatus.MISSING_VALUE,
            unit_conformance=validation.unit_conformance,
            provenance=provenance,
        )

    try:
        numeric = float(raw_value)
    except (TypeError, ValueError):
        numeric = math.nan

    if (
        not math.isfinite(numeric)
        or (
            validation.spec.minimum_value is not None
            and numeric < validation.spec.minimum_value
        )
    ):
        return ArchiveQuantity(
            raw_value=raw_value,
            source_unit=metadata.unit,
            canonical_value=None,
            canonical_unit=validation.spec.canonical_unit,
            status=ArchiveQuantityStatus.INVALID_VALUE,
            unit_conformance=validation.unit_conformance,
            provenance=provenance,
        )

    assert validation.conversion_factor is not None
    return ArchiveQuantity(
        raw_value=raw_value,
        source_unit=metadata.unit,
        canonical_value=(
            numeric * validation.conversion_factor
        ),
        canonical_unit=validation.spec.canonical_unit,
        status=ArchiveQuantityStatus.AVAILABLE,
        unit_conformance=validation.unit_conformance,
        provenance=provenance,
    )


def _issue_for_quantity(
    quantity: ArchiveQuantity,
) -> ArchiveEvidenceIssue | None:
    if quantity.status is ArchiveQuantityStatus.AVAILABLE:
        return None
    if quantity.status is ArchiveQuantityStatus.MISSING_VALUE:
        kind = ArchiveEvidenceIssueKind.VALUE_MISSING
    elif quantity.status is ArchiveQuantityStatus.INVALID_VALUE:
        kind = ArchiveEvidenceIssueKind.VALUE_INVALID
    else:
        kind = ArchiveEvidenceIssueKind.FIELD_METADATA_UNUSABLE
    return ArchiveEvidenceIssue(
        kind=kind,
        message=(
            f"{quantity.provenance.source_field} is "
            f"{quantity.status.value}"
        ),
        source_field=quantity.provenance.source_field,
    )


def build_archive_comparison_evidence(
    row: RawArchiveRow,
    validation: ArchiveFieldContractValidation,
    *,
    query_run_id: str,
    raw_row_id: str,
    result_index: int,
) -> ArchiveComparisonEvidence:
    """Project one raw Archive row through the validated unit plan."""

    quantities = {
        name: _quantity(
            row.get(name),
            validation.field(name),
            query_run_id=query_run_id,
            raw_row_id=raw_row_id,
            result_index=result_index,
        )
        for name in (
            field.spec.name
            for field in validation.fields
        )
    }

    centre = quantities["frequency"]
    bandwidth = quantities["bandwidth"]
    lower_ghz: float | None = None
    upper_ghz: float | None = None
    issues = tuple(
        issue
        for issue in (
            _issue_for_quantity(quantity)
            for quantity in quantities.values()
        )
        if issue is not None
    )

    if centre.is_available and bandwidth.is_available:
        assert centre.canonical_value is not None
        assert bandwidth.canonical_value is not None
        half_bandwidth = bandwidth.canonical_value / 2.0
        lower_ghz = centre.canonical_value - half_bandwidth
        upper_ghz = centre.canonical_value + half_bandwidth

    issues += (
        ArchiveEvidenceIssue(
            kind=ArchiveEvidenceIssueKind.ARCHIVE_FRAME_UNSPECIFIED,
            message=(
                "The public Archive documentation calls frequency a "
                "sky frequency but does not identify a comparison-ready "
                "reference frame for the TAP value."
            ),
            source_field="frequency",
        ),
    )

    return ArchiveComparisonEvidence(
        frequency=ArchiveFrequencyInterval(
            centre=centre,
            bandwidth=bandwidth,
            lower_ghz=lower_ghz,
            upper_ghz=upper_ghz,
            frame_status=(
                ArchiveFrequencyFrameStatus
                .SKY_FREQUENCY_FRAME_UNSPECIFIED
            ),
        ),
        spectral_resolution=ArchiveSpectralResolution(
            quantities["spectral_resolution"]
        ),
        angular_resolution=ArchiveAngularResolution(
            quantities["spatial_resolution"]
        ),
        line_sensitivity=ArchiveSensitivityEstimate(
            quantity=quantities["sensitivity_10kms"],
            kind=ArchiveSensitivityKind.LINE_10_KMS,
        ),
        continuum_sensitivity=ArchiveSensitivityEstimate(
            quantity=quantities[
                "cont_sensitivity_bandwidth"
            ],
            kind=(
                ArchiveSensitivityKind
                .CONTINUUM_AGGREGATE_BANDWIDTH
            ),
        ),
        issues=issues,
    )
