"""Domain values for normalized ALMA Archive metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MissingValueStatus(StrEnum):
    """How an optional Archive scalar became present or missing."""

    PRESENT = "PRESENT"
    MASKED = "MASKED"
    NULL = "NULL"
    BLANK_NORMALIZED = "BLANK_NORMALIZED"
    SENTINEL_3000_DATE = "SENTINEL_3000_DATE"


class BooleanParseStatus(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class TimestampParseStatus(StrEnum):
    PARSED = "PARSED"
    MISSING = "MISSING"
    SENTINEL_3000_DATE = "SENTINEL_3000_DATE"
    INVALID = "INVALID"


class PublisherDidMappingStatus(StrEnum):
    MATCH = "MATCH"
    MATCH_AFTER_NORMALIZATION = "MATCH_AFTER_NORMALIZATION"
    MISSING_PROPOSAL_ID = "MISSING_PROPOSAL_ID"
    MISSING_PUBLISHER_DID = "MISSING_PUBLISHER_DID"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True, slots=True)
class NormalizedText:
    raw_value: object
    value: str | None
    missing_status: MissingValueStatus

    @property
    def is_present(self) -> bool:
        return self.missing_status is MissingValueStatus.PRESENT


@dataclass(frozen=True, slots=True)
class NormalizedBoolean:
    raw_value: object
    normalized_text: str | None
    value: bool | None
    status: BooleanParseStatus
    missing_status: MissingValueStatus


@dataclass(frozen=True, slots=True)
class NormalizedTimestamp:
    raw_value: object
    normalized_text: str | None
    value: datetime | None
    status: TimestampParseStatus
    missing_status: MissingValueStatus


@dataclass(frozen=True, slots=True)
class PublisherDidValidation:
    proposal_id: NormalizedText
    obs_publisher_did: NormalizedText
    expected_publisher_did: str | None
    status: PublisherDidMappingStatus

    @property
    def is_match(self) -> bool:
        return self.status in {
            PublisherDidMappingStatus.MATCH,
            PublisherDidMappingStatus.MATCH_AFTER_NORMALIZATION,
        }


@dataclass(frozen=True, slots=True)
class ArchiveMetadataInput:
    proposal_id: object = None
    obs_publisher_did: object = None
    group_ous_uid: object = None
    science_observation: object = None
    is_mosaic: object = None
    qa2_passed: object = None
    obs_release_date: object = None
    last_modified: object = None


@dataclass(frozen=True, slots=True)
class ArchiveMetadataNormalization:
    publisher_did: PublisherDidValidation
    group_ous_uid: NormalizedText
    science_observation: NormalizedBoolean
    is_mosaic: NormalizedBoolean
    qa2_passed: NormalizedBoolean
    obs_release_date: NormalizedTimestamp
    last_modified: NormalizedTimestamp
    normalization_version: str
