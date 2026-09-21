"""Typed preparation evidence; none of these states is a line verdict."""

from dataclasses import dataclass

from alma_duplicate.domain.reconstruction import SourceSpwAssociationKey


@dataclass(frozen=True, slots=True)
class ModeObservation:
    raw_row_id: str
    raw_count: object
    status: str
    channel_count: int | None
    raw_type: str
    ui_type: str = "UNKNOWN"
    operational_mode: str = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ArchiveModeEvidence:
    source_record_id: str
    association: SourceSpwAssociationKey | None
    observations: tuple[ModeObservation, ...]
    metadata_status: str
    status: str
    ui_type: str
    operational_mode: str
    reasons: tuple[str, ...]
    source_datatype: str | None
    source_unit: str | None
    source_arraysize: str | None
    evidence_level: str = "DERIVED"
    method_version: str = "archive_association_mode_1"
    classification_source: str = "ARCHIVE_PORTAL_CHANNEL_COUNT"
    classification_version: str = "ARCHIVE_PORTAL_RULE_V1"
    mapping_source: str = "ALMA_SCIENCE_ARCHIVE_MANUAL"
    mapping_version: str = "CYCLE13_V1"
    decision_ref: str = (
        "docs/evidence/supervisor_confirmation_2026-09-17.md#confirmed-2026-09-21"
    )


@dataclass(frozen=True, slots=True)
class ProposedLineEvidence:
    window_id: str
    sensitivity_id: str | None
    sky_frequency_ghz: float | None
    planned_resolution_kms: float | None
    resolution_sources: tuple[str, ...]
    reasons: tuple[str, ...]
    method_version: str = "proposed_line_preparation_1"
