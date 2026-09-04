"""Domain objects for ALMA Archive row identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

OBS_ID_WIDTH_CONTRACT_VERSION = "1"
OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY = 64


class ObsIdParseStatus(StrEnum):
    """Whether the visible identifier grammar was parsed."""

    PARSED = "PARSED"
    FAILED = "FAILED"


class ObsIdConfidence(StrEnum):
    """Grammar confidence kept separate from live width conformance."""

    PARSED_COMPLETE = "PARSED_COMPLETE"
    PARSED_AT_HISTORICAL_TRUNCATION_BOUNDARY = (
        "PARSED_AT_HISTORICAL_TRUNCATION_BOUNDARY"
    )
    FAILED_AT_HISTORICAL_TRUNCATION_BOUNDARY = (
        "FAILED_AT_HISTORICAL_TRUNCATION_BOUNDARY"
    )
    FAILED_OTHER = "FAILED_OTHER"


class ObsIdWidthMetadataStatus(StrEnum):
    """Interpretation of one response VOTable FIELD descriptor."""

    BOUNDED_VARIABLE = "BOUNDED_VARIABLE"
    FIXED = "FIXED"
    UNBOUNDED = "UNBOUNDED"
    MISSING = "MISSING"
    INVALID = "INVALID"
    INCOMPATIBLE_DATATYPE = "INCOMPATIBLE_DATATYPE"


class ObsIdWidthMetadataSource(StrEnum):
    """Origin of the width descriptor used for one reconstruction."""

    RETRIEVAL_VOTABLE_FIELD = "RETRIEVAL_VOTABLE_FIELD"
    DIRECT_RECONSTRUCTION_FALLBACK = (
        "DIRECT_RECONSTRUCTION_FALLBACK"
    )


class ObsIdWidthStatus(StrEnum):
    """Relationship between one value and the live reported maximum."""

    NOT_EVALUABLE = "NOT_EVALUABLE"
    WITHIN_UNBOUNDED = "WITHIN_UNBOUNDED"
    BELOW_REPORTED_MAXIMUM = "BELOW_REPORTED_MAXIMUM"
    AT_REPORTED_MAXIMUM = "AT_REPORTED_MAXIMUM"
    ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT = (
        "ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT"
    )


class ObsIdFailureClass(StrEnum):
    """Structured reason why the visible identifier grammar failed."""

    MISSING = "MISSING"
    BLANK = "BLANK"
    TRUNCATED_AFTER_SPW_MARKER_AT_HISTORICAL_BOUNDARY = (
        "TRUNCATED_AFTER_SPW_MARKER_AT_HISTORICAL_BOUNDARY"
    )
    TRUNCATED_IN_SOURCE_SEGMENT_AT_HISTORICAL_BOUNDARY = (
        "TRUNCATED_IN_SOURCE_SEGMENT_AT_HISTORICAL_BOUNDARY"
    )
    TRUNCATED_OTHER_SUFFIX_AT_HISTORICAL_BOUNDARY = (
        "TRUNCATED_OTHER_SUFFIX_AT_HISTORICAL_BOUNDARY"
    )
    HISTORICAL_BOUNDARY_WITHOUT_SOURCE_MARKER = (
        "HISTORICAL_BOUNDARY_WITHOUT_SOURCE_MARKER"
    )
    NON_BOUNDARY_GRAMMAR_EXCEPTION = (
        "NON_BOUNDARY_GRAMMAR_EXCEPTION"
    )


@dataclass(frozen=True, slots=True)
class ObsIdIssue:
    """One diagnostic attached to identifier evidence."""

    code: str
    message: str
    token: str | None = None


@dataclass(frozen=True, slots=True)
class ObsIdWidthContract:
    """Live VOTable width metadata plus independent historical evidence."""

    raw_datatype: str | None
    raw_arraysize: str | None
    reported_max_length: int | None
    metadata_status: ObsIdWidthMetadataStatus
    metadata_source: ObsIdWidthMetadataSource
    historical_truncation_boundary: int
    issues: tuple[str, ...]
    contract_version: str

    def __post_init__(self) -> None:
        if self.reported_max_length is not None:
            if self.reported_max_length <= 0:
                raise ValueError(
                    "reported_max_length must be positive"
                )
            if self.metadata_status not in {
                ObsIdWidthMetadataStatus.BOUNDED_VARIABLE,
                ObsIdWidthMetadataStatus.FIXED,
            }:
                raise ValueError(
                    "reported_max_length requires bounded metadata"
                )
        elif self.metadata_status in {
            ObsIdWidthMetadataStatus.BOUNDED_VARIABLE,
            ObsIdWidthMetadataStatus.FIXED,
        }:
            raise ValueError(
                "bounded metadata requires reported_max_length"
            )

        if self.historical_truncation_boundary <= 0:
            raise ValueError(
                "historical_truncation_boundary must be positive"
            )
        if not self.contract_version.strip():
            raise ValueError(
                "contract_version must not be blank"
            )


def unavailable_obs_id_width_contract() -> ObsIdWidthContract:
    """Return an explicit fallback for direct reconstruction calls."""

    return ObsIdWidthContract(
        raw_datatype=None,
        raw_arraysize=None,
        reported_max_length=None,
        metadata_status=ObsIdWidthMetadataStatus.MISSING,
        metadata_source=(
            ObsIdWidthMetadataSource
            .DIRECT_RECONSTRUCTION_FALLBACK
        ),
        historical_truncation_boundary=(
            OBS_ID_HISTORICAL_TRUNCATION_BOUNDARY
        ),
        issues=("obs_id_width_metadata_unavailable",),
        contract_version=OBS_ID_WIDTH_CONTRACT_VERSION,
    )


@dataclass(frozen=True, slots=True)
class ObsIdParseResult:
    """Parsed identifier evidence with independent width diagnostics."""

    raw_value: str | bytes | float | None
    normalized_value: str | None

    member_ous_uid: str | None
    source_name: str | None
    spw_token: str | None
    spw_index: int | None

    obs_id_length: int | None
    width_contract: ObsIdWidthContract
    width_status: ObsIdWidthStatus
    at_historical_truncation_boundary: bool

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
            .PARSED_AT_HISTORICAL_TRUNCATION_BOUNDARY,
            ObsIdConfidence
            .FAILED_AT_HISTORICAL_TRUNCATION_BOUNDARY,
        }

    @property
    def has_width_schema_drift(self) -> bool:
        """Return whether a value exceeds the live reported maximum."""

        return (
            self.width_status
            is ObsIdWidthStatus
            .ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT
        )

    @property
    def is_safe_for_reconstruction(self) -> bool:
        """Return whether parsed identity candidates may be cross-checked.

        Live schema drift is diagnostic and does not invalidate complete
        visible grammar. A value exactly at the independently recorded
        historical truncation boundary remains unsafe.
        """

        return (
            self.parse_status is ObsIdParseStatus.PARSED
            and self.confidence is ObsIdConfidence.PARSED_COMPLETE
            and self.member_ous_uid is not None
            and self.source_name is not None
            and self.spw_token is not None
            and self.spw_index is not None
        )
