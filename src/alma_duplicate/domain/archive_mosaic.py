"""Execution-local Archive science fields; no policy or completeness inference."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScienceScan:
    scan_id: int
    spw_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ScienceField:
    field_id: int
    source_id: int
    target_name: str
    frame: str
    ra_original: str
    dec_original: str
    ra_deg: float
    dec_deg: float
    scans: tuple[ScienceScan, ...]


@dataclass(frozen=True, slots=True)
class ParsedScienceFields:
    measurement_set: str
    source_sha256: str
    fields: tuple[ScienceField, ...]
    declared_field_count: int
    parser_version: str = "archive_listobs_icrs_1"
    direction_kind: str = "LISTOBS_REPORTED_FIELD_CENTRE"
    scope: str = "SUPPORTED_SINGLE_TARGET_LISTOBS"


@dataclass(frozen=True, slots=True)
class ArchiveMosaicExecution:
    project_code: str
    member_ous_uid: str
    asdm_uid: str
    source_name: str
    metadata_reference: str
    evidence: ParsedScienceFields
    array_label: str | None
    array_evidence_reference: str | None
    metadata_status: str = "CALLER_SUPPLIED_REFERENCE_NOT_VERIFIED"
    array_status: str = "NOT_INDEPENDENTLY_VERIFIED"
    binding_status: str = "MS_BASENAME_AND_TARGET_MATCHED"
    acquisition_status: str = "LOCAL_INPUT_ONLY"
    execution_inventory_status: str = "UNKNOWN"
    completeness: str = "MEMBER_COMPLETENESS_NOT_ESTABLISHED"
    policy_status: str = "NOT_EVALUATED"
    reconstruction_version: str = "archive_mosaic_execution_1"
