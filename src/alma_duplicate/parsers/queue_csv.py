"""Safe parser for the public current-cycle Queue CSV."""

from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from alma_duplicate.domain.queue import (
    QueueCapabilities,
    QueueCapabilityStatus,
    QueueCsvParseResult,
    QueueDictionaryEntry,
    QueueFieldMetadata,
    QueueGroupKey,
    QueueIssueKind,
    QueueIssueSeverity,
    QueueMosaicKind,
    QueueParseIssue,
    QueueParseStatus,
    QueueQuantity,
    QueueRawRowId,
    QueueRequestEvidence,
    QueueRowInput,
    QueueSensitivityRequest,
    QueueSnapshot,
    QueueSpatialEvidence,
    QueueSpw,
    QueueUnitInterpretation,
    QueueVelocityContext,
    RawQueueRow,
    RegularSpwEvidence,
    SpectralScanEvidence,
)
from alma_duplicate.queue_csv_contract import (
    QUEUE_DICTIONARY_ONLY_FIELDS,
    QUEUE_EXPECTED_COLUMNS,
    QUEUE_FIELD_SPECS,
    QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC,
    QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ,
    QUEUE_SCHEMA_VERSION,
    QUEUE_SPS_COLUMNS,
    QUEUE_SPW_COLUMNS,
    QueueFieldSpec,
    QueueMetadataStatus,
)
from alma_duplicate.queue_normalization import (
    QUEUE_UNIT_NORMALIZATION_VERSION,
    QueueFrequencyDerivationError,
    derive_sky_frequency,
    derived_sky_interval,
)

QUEUE_CSV_PARSER_VERSION = "1"
DEFAULT_QUEUE_SOURCE_URL = (
    "https://almascience.eso.org/proposing/duplications"
)


@dataclass(frozen=True, slots=True)
class _CsvRecord:
    start_line: int
    end_line: int
    values: tuple[str, ...]

    @property
    def is_blank(self) -> bool:
        return not self.values or not any(
            value.strip() for value in self.values
        )


def _read_records(text: str) -> tuple[_CsvRecord, ...]:
    records: list[_CsvRecord] = []
    previous_end = 0
    reader = csv.reader(io.StringIO(text, newline=""))

    for values in reader:
        start_line = previous_end + 1
        end_line = reader.line_num
        records.append(
            _CsvRecord(
                start_line=start_line,
                end_line=end_line,
                values=tuple(values),
            )
        )
        previous_end = end_line

    return tuple(records)


def _empty_snapshot(
    *,
    source_url: str,
    snapshot_sha256: str,
    captured_at: datetime | None,
    byte_length: int,
) -> QueueSnapshot:
    return QueueSnapshot(
        source_url=source_url,
        snapshot_sha256=snapshot_sha256,
        captured_at=captured_at,
        byte_length=byte_length,
        encoding="utf-8-sig",
        description_raw="",
        operational_columns=(),
        secondary_header_row=(),
        dictionary_entries=(),
        schema_version=QUEUE_SCHEMA_VERSION,
        parser_version=QUEUE_CSV_PARSER_VERSION,
    )


def _capabilities() -> QueueCapabilities:
    unavailable = QueueCapabilityStatus.UNAVAILABLE
    return QueueCapabilities(
        authoritative_correlator_mode=unavailable,
        moving_object_classification=unavailable,
        sps_window_expansion=unavailable,
        archive_frame_alignment=unavailable,
    )


def _error_result(
    snapshot: QueueSnapshot,
    issues: list[QueueParseIssue],
    *,
    raw_rows: tuple[RawQueueRow, ...] = (),
    field_metadata: tuple[QueueFieldMetadata, ...] = (),
) -> QueueCsvParseResult:
    return QueueCsvParseResult(
        status=QueueParseStatus.ERROR,
        snapshot=snapshot,
        field_metadata=field_metadata,
        raw_rows=raw_rows,
        row_inputs=(),
        issues=tuple(issues),
        capabilities=_capabilities(),
    )


def _dictionary_entries(
    records: tuple[_CsvRecord, ...],
    dictionary_index: int,
    operational_index: int,
    issues: list[QueueParseIssue],
) -> tuple[QueueDictionaryEntry, ...]:
    entries: list[QueueDictionaryEntry] = []

    for record in records[
        dictionary_index + 1:operational_index
    ]:
        if record.is_blank:
            continue
        if len(record.values) != 3:
            issues.append(
                QueueParseIssue(
                    kind=QueueIssueKind.MALFORMED_DICTIONARY_ENTRY,
                    severity=QueueIssueSeverity.ERROR,
                    message=(
                        "embedded dictionary record does not contain "
                        "exactly three fields"
                    ),
                    raw_value=str(record.values),
                )
            )
            continue
        entries.append(
            QueueDictionaryEntry(
                physical_start_line=record.start_line,
                source_name=record.values[0],
                declaration=record.values[1],
                description=record.values[2],
            )
        )

    return tuple(entries)


def _find_layout(
    records: tuple[_CsvRecord, ...],
) -> tuple[int, int] | None:
    dictionary_index: int | None = None
    operational_index: int | None = None

    for index, record in enumerate(records):
        if record.values == (
            "Column Heading",
            "Units",
            "Description",
        ):
            dictionary_index = index
            break

    if dictionary_index is None:
        return None

    for index in range(dictionary_index + 1, len(records)):
        values = records[index].values
        value_set = set(values)
        if (
            len(values) >= 31
            and {
                "Project Code",
                "Target Name",
                "RA",
                "Dec",
                "Ref.Frequency",
                "SPS Start Freq.",
                "Freq SPW 1",
                "Bandwidth SPW 1",
                "Spec.Res. SPW 1",
            }.issubset(value_set)
        ):
            operational_index = index
            break

    if operational_index is None:
        return None
    return dictionary_index, operational_index


def _description_before(
    records: tuple[_CsvRecord, ...],
    dictionary_index: int,
) -> str:
    for record in records[:dictionary_index]:
        if not record.is_blank:
            return ",".join(record.values)
    return ""


def _metadata_for_columns(
    columns: tuple[str, ...],
    secondary: tuple[str, ...],
    dictionary: tuple[QueueDictionaryEntry, ...],
    issues: list[QueueParseIssue],
) -> tuple[QueueFieldMetadata, ...]:
    by_name = {
        entry.source_name: entry
        for entry in dictionary
    }
    metadata: list[QueueFieldMetadata] = []

    for index, column in enumerate(columns):
        spec = QUEUE_FIELD_SPECS.get(column)
        if spec is None:
            continue
        entry = by_name.get(spec.dictionary_name)
        actual_secondary = secondary[index].strip()

        if entry is None:
            issues.append(
                QueueParseIssue(
                    kind=(
                        QueueIssueKind
                        .METADATA_DECLARATION_DRIFT
                    ),
                    severity=QueueIssueSeverity.ERROR,
                    message=(
                        "embedded dictionary is missing "
                        f"{spec.dictionary_name!r}"
                    ),
                    column=column,
                )
            )
            description = None
            dictionary_declaration = None
        else:
            description = entry.description
            dictionary_declaration = entry.declaration
            if (
                dictionary_declaration
                != spec.dictionary_declaration
            ):
                issues.append(
                    QueueParseIssue(
                        kind=(
                            QueueIssueKind
                            .METADATA_DECLARATION_DRIFT
                        ),
                        severity=QueueIssueSeverity.ERROR,
                        message=(
                            f"dictionary declaration for {column!r} "
                            "does not match the v1 contract"
                        ),
                        column=column,
                        raw_value=dictionary_declaration,
                    )
                )

        expected_secondary = spec.secondary_token or ""
        if actual_secondary != expected_secondary:
            issues.append(
                QueueParseIssue(
                    kind=(
                        QueueIssueKind
                        .METADATA_DECLARATION_DRIFT
                    ),
                    severity=QueueIssueSeverity.ERROR,
                    message=(
                        f"secondary token for {column!r} does not "
                        "match the v1 contract"
                    ),
                    column=column,
                    raw_value=actual_secondary,
                )
            )

        metadata.append(
            QueueFieldMetadata(
                name=column,
                canonical_name=spec.canonical_name,
                dictionary_name=spec.dictionary_name,
                dictionary_declaration=dictionary_declaration,
                dictionary_description=description,
                secondary_token=actual_secondary or None,
                canonical_unit=spec.canonical_unit,
                metadata_status=str(spec.metadata_status),
            )
        )

    if "SPS Bandwidth" in columns:
        issues.append(
            QueueParseIssue(
                kind=(
                    QueueIssueKind
                    .CONFLICTING_UNIT_DECLARATION
                ),
                severity=QueueIssueSeverity.WARNING,
                message=(
                    "SPS Bandwidth is declared as MHz in the "
                    "dictionary and GHz in the secondary header; "
                    "v1 normalizes the pinned schema as MHz"
                ),
                column="SPS Bandwidth",
            )
        )

    return tuple(metadata)


def _content_fingerprint(values: tuple[str, ...]) -> str:
    payload = json.dumps(
        values,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class _RowParser:
    def __init__(
        self,
        raw_row: RawQueueRow,
        issues: list[QueueParseIssue],
    ) -> None:
        self.raw_row = raw_row
        self.issues = issues
        self.failed = False

    def _issue(
        self,
        kind: QueueIssueKind,
        message: str,
        *,
        column: str | None = None,
        slot_number: int | None = None,
        raw_value: str | None = None,
        severity: QueueIssueSeverity = QueueIssueSeverity.ERROR,
    ) -> None:
        self.issues.append(
            QueueParseIssue(
                kind=kind,
                severity=severity,
                message=message,
                row_id=self.raw_row.row_id,
                column=column,
                slot_number=slot_number,
                raw_value=raw_value,
            )
        )
        if severity is QueueIssueSeverity.ERROR:
            self.failed = True

    def text(self, column: str) -> str:
        raw = self.raw_row.value(column)
        value = raw.strip()
        if not value:
            self._issue(
                QueueIssueKind.MISSING_REQUIRED_VALUE,
                f"required text field {column!r} is blank",
                column=column,
                raw_value=raw,
            )
        return value

    def quantity(
        self,
        column: str,
        *,
        required: bool = True,
        positive: bool = False,
        nonnegative: bool = False,
    ) -> QueueQuantity | None:
        raw = self.raw_row.value(column)
        stripped = raw.strip()
        if not stripped:
            if required:
                self._issue(
                    QueueIssueKind.INVALID_NUMERIC_VALUE,
                    f"required numeric field {column!r} is blank",
                    column=column,
                    raw_value=raw,
                )
            return None

        try:
            value = float(stripped)
        except ValueError:
            self._issue(
                QueueIssueKind.INVALID_NUMERIC_VALUE,
                f"field {column!r} is not numeric",
                column=column,
                raw_value=raw,
            )
            return None

        if not math.isfinite(value):
            self._issue(
                QueueIssueKind.INVALID_NUMERIC_VALUE,
                f"field {column!r} is not finite",
                column=column,
                raw_value=raw,
            )
            return None
        if positive and value <= 0.0:
            self._issue(
                QueueIssueKind.INVALID_NUMERIC_VALUE,
                f"field {column!r} must be positive",
                column=column,
                raw_value=raw,
            )
            return None
        if nonnegative and value < 0.0:
            self._issue(
                QueueIssueKind.INVALID_NUMERIC_VALUE,
                f"field {column!r} must not be negative",
                column=column,
                raw_value=raw,
            )
            return None

        spec: QueueFieldSpec = QUEUE_FIELD_SPECS[column]
        if spec.metadata_status is QueueMetadataStatus.CONFLICTING_UNITS:
            unit_interpretation = (
                QueueUnitInterpretation.DICTIONARY_OVERRIDE
            )
        elif spec.metadata_status is QueueMetadataStatus.LEXICAL_VARIANT:
            unit_interpretation = (
                QueueUnitInterpretation.LEXICAL_NORMALIZATION
            )
        else:
            unit_interpretation = QueueUnitInterpretation.DIRECT
        return QueueQuantity(
            raw_text=raw,
            raw_value=value,
            value=value,
            dictionary_unit=spec.dictionary_declaration,
            secondary_unit=spec.secondary_token,
            canonical_unit=spec.canonical_unit,
            unit_interpretation=unit_interpretation,
            normalization_version=QUEUE_UNIT_NORMALIZATION_VERSION,
        )

    def boolean(self, column: str) -> bool | None:
        raw = self.raw_row.value(column)
        stripped = raw.strip()
        if stripped == "True":
            return True
        if stripped == "False":
            return False
        self._issue(
            QueueIssueKind.INVALID_BOOLEAN_VALUE,
            f"field {column!r} is not True or False",
            column=column,
            raw_value=raw,
        )
        return None

    def parse(self) -> QueueRowInput | None:
        project_code = self.text("Project Code")
        target_name = self.text("Target Name")
        band = self.text("Band")
        group_key = QueueGroupKey(
            project_code=project_code,
            target_name=target_name,
            band=band,
        )

        ra = self.quantity("RA")
        dec = self.quantity("Dec")
        long_offset = self.quantity("Long Offset")
        lat_offset = self.quantity("Lat Offset")
        mosaic_length = self.quantity(
            "Mos. Length",
            required=False,
            nonnegative=True,
        )
        mosaic_width = self.quantity(
            "Mos. Width",
            required=False,
            nonnegative=True,
        )
        mosaic_pa = self.quantity(
            "Mos. PA",
            required=False,
        )
        mosaic_spacing = self.quantity(
            "Mos. Spacing",
            required=False,
            nonnegative=True,
        )

        mosaic_raw = self.raw_row.value("Mosaic").strip()
        offsets_nonzero = False
        if long_offset is not None and lat_offset is not None:
            offsets_nonzero = (
                abs(long_offset.value)
                > QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC
                or abs(lat_offset.value)
                > QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC
            )

        if mosaic_raw == "Custom":
            mosaic_kind = QueueMosaicKind.CUSTOM_POINTING
        elif mosaic_raw == "Rectangle":
            mosaic_kind = QueueMosaicKind.RECTANGULAR_MOSAIC
        elif not mosaic_raw and offsets_nonzero:
            mosaic_kind = (
                QueueMosaicKind.UNSPECIFIED_WITH_OFFSET
            )
        elif not mosaic_raw:
            mosaic_kind = QueueMosaicKind.SINGLE_FIELD
        else:
            mosaic_kind = QueueMosaicKind.UNKNOWN
            self._issue(
                QueueIssueKind.UNSUPPORTED_CATEGORY,
                "unrecognized Mosaic category was preserved",
                column="Mosaic",
                raw_value=mosaic_raw,
                severity=QueueIssueSeverity.WARNING,
            )

        coordinate_system = self.raw_row.value(
            "Mos. Coord."
        ).strip()
        if (
            mosaic_kind is QueueMosaicKind.RECTANGULAR_MOSAIC
            and (
                any(
                    value is None
                    for value in (
                        mosaic_length,
                        mosaic_width,
                        mosaic_pa,
                        mosaic_spacing,
                    )
                )
                or not coordinate_system
            )
        ):
            self._issue(
                QueueIssueKind.INCOMPLETE_RECTANGLE_GEOMETRY,
                "Rectangle mosaic is missing geometry or reference system",
                column="Mosaic",
                raw_value=mosaic_raw,
            )

        velocity_quantity = self.quantity("Velocity")
        velocity_frame = self.text("Vel. Frame")
        velocity_convention = self.text(
            "Vel. Convention"
        ).upper()
        if velocity_convention not in {
            "RADIO", "OPTICAL", "RELATIVISTIC"
        }:
            self._issue(
                QueueIssueKind.UNSUPPORTED_CATEGORY,
                "unsupported velocity convention",
                column="Vel. Convention",
                raw_value=velocity_convention,
            )
        is_sky_frequency = self.boolean("Is Sky Freq?")

        reference_frequency = self.quantity(
            "Ref.Frequency",
            positive=True,
        )
        reference_width = self.quantity(
            "Ref.Freq.Width",
            positive=True,
        )
        requested_sensitivity = self.quantity(
            "Req.Sensitivity",
            positive=True,
        )

        requested_ar = self.quantity(
            "Req. Ang. Res.",
            positive=True,
        )
        requested_las = self.quantity(
            "Req. LAS",
            nonnegative=True,
        )
        use_7m = self.boolean("Use 7-m?")
        use_tp = self.boolean("Use TP?")
        polarization = self.text("Polarization")
        if polarization not in {"FULL", "DOUBLE", "SINGLE"}:
            self._issue(
                QueueIssueKind.UNSUPPORTED_CATEGORY,
                "unrecognized polarization was preserved",
                column="Polarization",
                raw_value=polarization,
                severity=QueueIssueSeverity.WARNING,
            )

        if any(
            value is None
            for value in (
                ra,
                dec,
                long_offset,
                lat_offset,
                velocity_quantity,
                is_sky_frequency,
                reference_frequency,
                reference_width,
                requested_sensitivity,
                requested_ar,
                requested_las,
                use_7m,
                use_tp,
            )
        ):
            return None

        if not 0.0 <= ra.value < 360.0:
            self._issue(
                QueueIssueKind.INVALID_NUMERIC_VALUE,
                "RA must be in the interval [0, 360) deg",
                column="RA",
                raw_value=ra.raw_text,
            )
        if not -90.0 <= dec.value <= 90.0:
            self._issue(
                QueueIssueKind.INVALID_NUMERIC_VALUE,
                "Dec must be in the interval [-90, 90] deg",
                column="Dec",
                raw_value=dec.raw_text,
            )

        velocity = QueueVelocityContext(
            velocity_kms=velocity_quantity,
            frame_raw=velocity_frame,
            convention_raw=velocity_convention,
            is_sky_frequency=is_sky_frequency,
        )
        sensitivity = QueueSensitivityRequest(
            reference_frequency_ghz=reference_frequency,
            reference_width_mhz=reference_width,
            requested_sensitivity_mjy=requested_sensitivity,
        )

        regular_spws = self._regular_spws(velocity)
        sps_values = tuple(
            self.raw_row.value(column).strip()
            for column in QUEUE_SPS_COLUMNS
        )
        sps_populated = tuple(bool(value) for value in sps_values)

        has_regular = bool(regular_spws)
        has_any_sps = any(sps_populated)
        has_complete_sps = all(sps_populated)

        if has_any_sps and not has_complete_sps:
            self._issue(
                QueueIssueKind.PARTIAL_SPS_RECORD,
                "spectral-scan fields are only partially populated",
            )
        if has_regular and has_any_sps:
            self._issue(
                QueueIssueKind.MIXED_REGULAR_AND_SPS,
                "row contains both regular SPW and SPS evidence",
            )
        if not has_regular and not has_any_sps:
            self._issue(
                QueueIssueKind.MISSING_SPECTRAL_REPRESENTATION,
                "row contains neither regular SPW nor SPS evidence",
            )

        spectral = None
        if has_regular and not has_any_sps:
            if not any(
                (
                    reference_frequency.value
                    >= spw.lower_sky_frequency_ghz
                    - QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ
                    and reference_frequency.value
                    <= spw.upper_sky_frequency_ghz
                    + QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ
                )
                for spw in regular_spws
            ):
                self._issue(
                    QueueIssueKind
                    .REFERENCE_FREQUENCY_OUTSIDE_COVERAGE,
                    "Ref.Frequency is outside all derived SPW intervals",
                    column="Ref.Frequency",
                    raw_value=reference_frequency.raw_text,
                )
            spectral = RegularSpwEvidence(
                spws=tuple(regular_spws),
                velocity=velocity,
                sensitivity=sensitivity,
            )
        elif has_complete_sps and not has_regular:
            spectral = self._spectral_scan(
                velocity,
                sensitivity,
            )

        spatial = QueueSpatialEvidence(
            ra_deg=ra,
            dec_deg=dec,
            ra_hms_raw=self.raw_row.value("RA_HMS"),
            dec_dms_raw=self.raw_row.value("Dec_DMS"),
            long_offset_arcsec=long_offset,
            lat_offset_arcsec=lat_offset,
            mosaic_raw=mosaic_raw,
            mosaic_kind=mosaic_kind,
            mosaic_length_arcsec=mosaic_length,
            mosaic_width_arcsec=mosaic_width,
            mosaic_pa_deg=mosaic_pa,
            mosaic_spacing_arcsec=mosaic_spacing,
            coordinate_system_raw=coordinate_system,
            zero_tolerance_arcsec=(
                QUEUE_MOSAIC_ZERO_TOLERANCE_ARCSEC
            ),
        )
        request = QueueRequestEvidence(
            requested_angular_resolution_arcsec=requested_ar,
            requested_las_arcsec=requested_las,
            use_7m=use_7m,
            use_tp=use_tp,
            polarization_raw=polarization,
        )

        if self.failed or spectral is None:
            return None
        return QueueRowInput(
            raw_row=self.raw_row,
            group_key=group_key,
            spatial=spatial,
            spectral=spectral,
            request=request,
        )

    def _regular_spws(
        self,
        velocity: QueueVelocityContext,
    ) -> list[QueueSpw]:
        parsed: list[QueueSpw] = []
        populated_numbers: list[int] = []

        for columns in QUEUE_SPW_COLUMNS:
            raw_values = (
                self.raw_row.value(columns.frequency).strip(),
                self.raw_row.value(columns.bandwidth).strip(),
                self.raw_row.value(
                    columns.spectral_resolution
                ).strip(),
            )
            populated = tuple(bool(value) for value in raw_values)
            if not any(populated):
                continue
            if not all(populated):
                self._issue(
                    QueueIssueKind.PARTIAL_SPW_TRIPLE,
                    "numbered SPW triple is partially populated",
                    slot_number=columns.number,
                )
                continue

            frequency = self.quantity(
                columns.frequency,
                positive=True,
            )
            bandwidth = self.quantity(
                columns.bandwidth,
                positive=True,
            )
            resolution = self.quantity(
                columns.spectral_resolution,
                positive=True,
            )
            if None in (frequency, bandwidth, resolution):
                continue

            try:
                derivation = derive_sky_frequency(
                    frequency,
                    velocity,
                )
                (
                    sky_bandwidth,
                    lower,
                    upper,
                ) = derived_sky_interval(
                    derivation,
                    bandwidth,
                )
            except QueueFrequencyDerivationError as exc:
                self._issue(
                    QueueIssueKind.INVALID_FREQUENCY_INTERVAL,
                    str(exc),
                    slot_number=columns.number,
                )
                continue

            populated_numbers.append(columns.number)
            parsed.append(
                QueueSpw(
                    number=columns.number,
                    frequency_ghz=frequency,
                    bandwidth_mhz=bandwidth,
                    spectral_resolution_mhz=resolution,
                    frequency_derivation=derivation,
                    sky_bandwidth_ghz=sky_bandwidth,
                    lower_sky_frequency_ghz=lower,
                    upper_sky_frequency_ghz=upper,
                )
            )

        if populated_numbers:
            expected = list(
                range(1, max(populated_numbers) + 1)
            )
            if populated_numbers != expected:
                self._issue(
                    QueueIssueKind.NONCONTIGUOUS_SPW_SLOTS,
                    "populated SPW numbers are non-contiguous",
                    raw_value=str(populated_numbers),
                    severity=QueueIssueSeverity.WARNING,
                )

        return parsed

    def _spectral_scan(
        self,
        velocity: QueueVelocityContext,
        sensitivity: QueueSensitivityRequest,
    ) -> SpectralScanEvidence | None:
        start = self.quantity(
            "SPS Start Freq.",
            positive=True,
        )
        end = self.quantity(
            "SPS End Freq.",
            positive=True,
        )
        bandwidth = self.quantity(
            "SPS Bandwidth",
            positive=True,
        )
        resolution = self.quantity(
            "SPS Spec. Res.",
            positive=True,
        )
        if None in (start, end, bandwidth, resolution):
            return None

        try:
            start_derivation = derive_sky_frequency(
                start,
                velocity,
            )
            end_derivation = derive_sky_frequency(
                end,
                velocity,
            )
        except QueueFrequencyDerivationError as exc:
            self._issue(
                QueueIssueKind.INVALID_FREQUENCY_INTERVAL,
                str(exc),
            )
            return None

        lower = min(
            start_derivation.sky_frequency_ghz,
            end_derivation.sky_frequency_ghz,
        )
        upper = max(
            start_derivation.sky_frequency_ghz,
            end_derivation.sky_frequency_ghz,
        )
        if lower >= upper:
            self._issue(
                QueueIssueKind.INVALID_FREQUENCY_INTERVAL,
                "SPS start and end do not define a positive range",
            )
            return None

        reference = sensitivity.reference_frequency_ghz.value
        if not (
            reference
            >= lower - QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ
            and reference
            <= upper + QUEUE_REFERENCE_INTERVAL_TOLERANCE_GHZ
        ):
            self._issue(
                QueueIssueKind
                .REFERENCE_FREQUENCY_OUTSIDE_COVERAGE,
                "Ref.Frequency is outside the derived SPS range",
                column="Ref.Frequency",
                raw_value=(
                    sensitivity.reference_frequency_ghz.raw_text
                ),
            )

        return SpectralScanEvidence(
            start_frequency_ghz=start,
            end_frequency_ghz=end,
            per_window_bandwidth_mhz=bandwidth,
            spectral_resolution_mhz=resolution,
            lower_sky_frequency_ghz=lower,
            upper_sky_frequency_ghz=upper,
            doppler_factor=start_derivation.doppler_factor,
            velocity=velocity,
            sensitivity=sensitivity,
        )


def parse_queue_csv_bytes(
    raw_bytes: bytes,
    *,
    source_url: str = DEFAULT_QUEUE_SOURCE_URL,
    captured_at: datetime | None = None,
) -> QueueCsvParseResult:
    """Parse one exact Queue CSV byte snapshot without policy logic."""

    snapshot_hash = sha256(raw_bytes).hexdigest()
    issues: list[QueueParseIssue] = []

    try:
        text = raw_bytes.decode("utf-8-sig")
        records = _read_records(text)
    except (UnicodeDecodeError, csv.Error) as exc:
        snapshot = _empty_snapshot(
            source_url=source_url,
            snapshot_sha256=snapshot_hash,
            captured_at=captured_at,
            byte_length=len(raw_bytes),
        )
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.LAYOUT_NOT_FOUND,
                severity=QueueIssueSeverity.ERROR,
                message=f"CSV decoding/parsing failed: {exc}",
            )
        )
        return _error_result(snapshot, issues)

    layout = _find_layout(records)
    if layout is None:
        snapshot = _empty_snapshot(
            source_url=source_url,
            snapshot_sha256=snapshot_hash,
            captured_at=captured_at,
            byte_length=len(raw_bytes),
        )
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.LAYOUT_NOT_FOUND,
                severity=QueueIssueSeverity.ERROR,
                message=(
                    "embedded dictionary or operational header "
                    "was not found"
                ),
            )
        )
        return _error_result(snapshot, issues)

    dictionary_index, operational_index = layout
    operational_record = records[operational_index]
    columns = operational_record.values
    dictionary = _dictionary_entries(
        records,
        dictionary_index,
        operational_index,
        issues,
    )

    dictionary_names = tuple(
        entry.source_name for entry in dictionary
    )
    for name, count in Counter(dictionary_names).items():
        if count > 1:
            issues.append(
                QueueParseIssue(
                    kind=QueueIssueKind.DUPLICATE_DICTIONARY_ENTRY,
                    severity=QueueIssueSeverity.ERROR,
                    message=f"duplicate dictionary entry {name!r}",
                    column=name,
                )
            )

    required_dictionary_names = {
        spec.dictionary_name
        for spec in QUEUE_FIELD_SPECS.values()
    } | set(QUEUE_DICTIONARY_ONLY_FIELDS)
    for name in sorted(
        required_dictionary_names - set(dictionary_names)
    ):
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.METADATA_DECLARATION_DRIFT,
                severity=QueueIssueSeverity.ERROR,
                message=f"embedded dictionary is missing {name!r}",
                column=name,
            )
        )

    if operational_index + 1 >= len(records):
        secondary = ()
    else:
        secondary = records[operational_index + 1].values

    snapshot = QueueSnapshot(
        source_url=source_url,
        snapshot_sha256=snapshot_hash,
        captured_at=captured_at,
        byte_length=len(raw_bytes),
        encoding="utf-8-sig",
        description_raw=_description_before(
            records,
            dictionary_index,
        ),
        operational_columns=columns,
        secondary_header_row=secondary,
        dictionary_entries=dictionary,
        schema_version=QUEUE_SCHEMA_VERSION,
        parser_version=QUEUE_CSV_PARSER_VERSION,
    )

    duplicates = tuple(
        column
        for column, count in Counter(columns).items()
        if count > 1
    )
    missing = tuple(
        column
        for column in QUEUE_EXPECTED_COLUMNS
        if column not in columns
    )
    unexpected = tuple(
        column
        for column in columns
        if column not in QUEUE_EXPECTED_COLUMNS
    )

    for column in duplicates:
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.DUPLICATE_COLUMN,
                severity=QueueIssueSeverity.ERROR,
                message=f"duplicate operational column {column!r}",
                column=column,
            )
        )
    for column in missing:
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.MISSING_REQUIRED_COLUMN,
                severity=QueueIssueSeverity.ERROR,
                message=f"missing required column {column!r}",
                column=column,
            )
        )
    for column in unexpected:
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.UNEXPECTED_COLUMN,
                severity=QueueIssueSeverity.ERROR,
                message=f"unexpected operational column {column!r}",
                column=column,
            )
        )

    if (
        not missing
        and not unexpected
        and not duplicates
        and columns != QUEUE_EXPECTED_COLUMNS
    ):
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.REORDERED_COLUMNS,
                severity=QueueIssueSeverity.WARNING,
                message=(
                    "known columns are reordered; values are read by name"
                ),
            )
        )

    if len(secondary) != len(columns):
        issues.append(
            QueueParseIssue(
                kind=QueueIssueKind.ROW_WIDTH_MISMATCH,
                severity=QueueIssueSeverity.ERROR,
                message=(
                    "secondary-header width differs from the "
                    "operational header"
                ),
            )
        )

    field_metadata: tuple[QueueFieldMetadata, ...] = ()
    if len(secondary) == len(columns):
        field_metadata = _metadata_for_columns(
            columns,
            secondary,
            dictionary,
            issues,
        )

    data_start = operational_index + 2
    raw_rows: list[RawQueueRow] = []
    for record in records[data_start:]:
        if record.is_blank:
            continue
        row_id = QueueRawRowId(
            snapshot_sha256=snapshot_hash,
            physical_start_line=record.start_line,
            physical_end_line=record.end_line,
        )
        raw_row = RawQueueRow(
            row_id=row_id,
            source_ordinal=len(raw_rows),
            declared_columns=columns,
            raw_values=record.values,
            content_fingerprint=_content_fingerprint(
                record.values
            ),
        )
        raw_rows.append(raw_row)
        if len(record.values) != len(columns):
            issues.append(
                QueueParseIssue(
                    kind=QueueIssueKind.ROW_WIDTH_MISMATCH,
                    severity=QueueIssueSeverity.ERROR,
                    message=(
                        "data-row width differs from the "
                        "operational header"
                    ),
                    row_id=row_id,
                    raw_value=str(len(record.values)),
                )
            )

    has_global_error = any(
        issue.severity is QueueIssueSeverity.ERROR
        and issue.row_id is None
        for issue in issues
    )
    row_inputs: list[QueueRowInput] = []
    if not has_global_error:
        for raw_row in raw_rows:
            if len(raw_row.raw_values) != len(columns):
                continue
            parsed = _RowParser(raw_row, issues).parse()
            if parsed is not None:
                row_inputs.append(parsed)

    has_error = any(
        issue.severity is QueueIssueSeverity.ERROR
        for issue in issues
    )
    has_warning = any(
        issue.severity is QueueIssueSeverity.WARNING
        for issue in issues
    )
    if has_error or len(row_inputs) != len(raw_rows):
        status = QueueParseStatus.ERROR
    elif has_warning:
        status = QueueParseStatus.COMPLETE_WITH_WARNINGS
    else:
        status = QueueParseStatus.COMPLETE

    return QueueCsvParseResult(
        status=status,
        snapshot=snapshot,
        field_metadata=field_metadata,
        raw_rows=tuple(raw_rows),
        row_inputs=tuple(row_inputs),
        issues=tuple(issues),
        capabilities=_capabilities(),
    )
