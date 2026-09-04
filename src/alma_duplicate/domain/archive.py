"""Domain objects for ALMA Archive row identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ObsIdParseStatus(StrEnum):


    PARSED = "PARSED"
    FAILED = "FAILED"


class ObsIdConfidence(StrEnum):

    PARSED_BELOW_DECLARED_WIDTH = (
        "PARSED_BELOW_DECLARED_WIDTH"
    )
    PARSED_AT_DECLARED_WIDTH_TRUNCATION_POSSIBLE = (
        "PARSED_AT_DECLARED_WIDTH_TRUNCATION_POSSIBLE"
    )
    PARSED_ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT = (
        "PARSED_ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT"
    )
    FAILED_AT_DECLARED_WIDTH_TRUNCATION_LIKELY = (
        "FAILED_AT_DECLARED_WIDTH_TRUNCATION_LIKELY"
    )
    FAILED_OTHER = "FAILED_OTHER"


class ObsIdWidthStatus(StrEnum):
    """Relationship between one value and the declared TAP width."""

    NOT_AVAILABLE = "NOT_AVAILABLE"
    BELOW_DECLARED_WIDTH = "BELOW_DECLARED_WIDTH"
    AT_DECLARED_WIDTH = "AT_DECLARED_WIDTH"
    ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT = (
        "ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT"
    )


class ObsIdFailureClass(StrEnum):

    MISSING = "MISSING"
    BLANK = "BLANK"
    TRUNCATED_AFTER_SPW_MARKER_AT_WIDTH = (
        "TRUNCATED_AFTER_SPW_MARKER_AT_WIDTH"
    )
    TRUNCATED_IN_SOURCE_SEGMENT_AT_WIDTH = (
        "TRUNCATED_IN_SOURCE_SEGMENT_AT_WIDTH"
    )
    TRUNCATED_OTHER_SUFFIX_AT_WIDTH = (
        "TRUNCATED_OTHER_SUFFIX_AT_WIDTH"
    )
    WIDTH_LIMIT_WITHOUT_SOURCE_MARKER = (
        "WIDTH_LIMIT_WITHOUT_SOURCE_MARKER"
    )
    NON_WIDTH_GRAMMAR_EXCEPTION = (
        "NON_WIDTH_GRAMMAR_EXCEPTION"
    )


@dataclass(frozen=True, slots=True)
class ObsIdIssue:


    code: str
    message: str
    token: str | None = None


@dataclass(frozen=True, slots=True)
class ObsIdParseResult:


    raw_value: str | bytes | float | None
    normalized_value: str | None

    member_ous_uid: str | None
    source_name: str | None
    spw_token: str | None
    spw_index: int | None

    obs_id_length: int | None
    declared_width: int
    at_declared_width: bool
    width_status: ObsIdWidthStatus

    parse_status: ObsIdParseStatus
    confidence: ObsIdConfidence
    failure_class: ObsIdFailureClass | None
    issues: tuple[ObsIdIssue, ...]

    parser_version: str

    @property
    def is_parsed(self) -> bool:
        return self.parse_status is ObsIdParseStatus.PARSED

    @property
    def has_truncation_risk(self) -> bool:
        return self.confidence in {
            ObsIdConfidence
            .PARSED_AT_DECLARED_WIDTH_TRUNCATION_POSSIBLE,
            ObsIdConfidence
            .FAILED_AT_DECLARED_WIDTH_TRUNCATION_LIKELY,
        }

    @property
    def has_width_schema_drift(self) -> bool:
        """Return whether the value exceeds the declared TAP width."""

        return (
            self.width_status
            is ObsIdWidthStatus.ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT
        )

    @property
    def is_safe_for_reconstruction(self) -> bool:
        """Return whether parsed identity candidates may be cross-checked.

        A complete value above the declared width is usable because its
        grammar is intact; the independently retained width status still
        records the TAP schema drift.  A value exactly at the declared width
        remains unsafe because the observed service has truncated values at
        that boundary.
        """

        return (
            self.parse_status is ObsIdParseStatus.PARSED
            and self.confidence in {
                ObsIdConfidence.PARSED_BELOW_DECLARED_WIDTH,
                ObsIdConfidence
                .PARSED_ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT,
            }
            and self.member_ous_uid is not None
            and self.source_name is not None
            and self.spw_token is not None
            and self.spw_index is not None
        )
