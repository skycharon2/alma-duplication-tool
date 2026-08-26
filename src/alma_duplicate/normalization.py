"""Normalize selected ALMA Archive metadata without applying policy rules."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from alma_duplicate.domain.normalization import (
    ArchiveMetadataInput,
    ArchiveMetadataNormalization,
    BooleanParseStatus,
    MissingValueStatus,
    NormalizedBoolean,
    NormalizedText,
    NormalizedTimestamp,
    PublisherDidMappingStatus,
    PublisherDidValidation,
    TimestampParseStatus,
)

NORMALIZATION_VERSION = "1"
PUBLISHER_DID_PREFIX = "ADS/JAO.ALMA#"
RELEASE_DATE_SENTINEL = date(3000, 1, 1)


def _is_masked(value: object) -> bool:
    """Return whether a scalar carries an active NumPy/Astropy mask."""

    mask = getattr(value, "mask", False)
    try:
        return bool(mask)
    except (TypeError, ValueError):
        raise TypeError("Archive normalization expects scalar values.") from None


def _is_null(value: object) -> bool:
    """Recognize scalar null values, including pandas NA and floating NaN."""

    marker = pd.isna(value)
    try:
        return bool(marker)
    except (TypeError, ValueError):
        raise TypeError("Archive normalization expects scalar values.") from None


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def normalize_optional_text(value: object) -> NormalizedText:
    """Normalize one optional scalar while preserving its unmodified input."""

    if _is_masked(value):
        return NormalizedText(
            raw_value=value,
            value=None,
            missing_status=MissingValueStatus.MASKED,
        )

    if value is None or _is_null(value):
        return NormalizedText(
            raw_value=value,
            value=None,
            missing_status=MissingValueStatus.NULL,
        )

    normalized = _as_text(value).strip()
    if not normalized:
        return NormalizedText(
            raw_value=value,
            value=None,
            missing_status=MissingValueStatus.BLANK_NORMALIZED,
        )

    return NormalizedText(
        raw_value=value,
        value=normalized,
        missing_status=MissingValueStatus.PRESENT,
    )


def normalize_archive_boolean(value: object) -> NormalizedBoolean:
    """Normalize Archive T/F scalars and retain unknown values explicitly."""

    text = normalize_optional_text(value)
    if text.value is None:
        return NormalizedBoolean(
            raw_value=value,
            normalized_text=None,
            value=None,
            status=BooleanParseStatus.MISSING,
            missing_status=text.missing_status,
        )

    token = text.value.upper()
    if token == "T":
        status = BooleanParseStatus.TRUE
        normalized_value: bool | None = True
    elif token == "F":
        status = BooleanParseStatus.FALSE
        normalized_value = False
    else:
        status = BooleanParseStatus.UNKNOWN
        normalized_value = None

    return NormalizedBoolean(
        raw_value=value,
        normalized_text=text.value,
        value=normalized_value,
        status=status,
        missing_status=text.missing_status,
    )


def _parse_iso_datetime(text: str) -> datetime:
    candidate = text
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    return datetime.fromisoformat(candidate)


def normalize_archive_timestamp(
    value: object,
    *,
    classify_release_sentinel: bool = False,
) -> NormalizedTimestamp:
    """Parse an Archive timestamp and optionally classify the release sentinel."""

    text = normalize_optional_text(value)
    if text.value is None:
        return NormalizedTimestamp(
            raw_value=value,
            normalized_text=None,
            value=None,
            status=TimestampParseStatus.MISSING,
            missing_status=text.missing_status,
        )

    try:
        parsed = _parse_iso_datetime(text.value)
    except ValueError:
        return NormalizedTimestamp(
            raw_value=value,
            normalized_text=text.value,
            value=None,
            status=TimestampParseStatus.INVALID,
            missing_status=MissingValueStatus.PRESENT,
        )

    if classify_release_sentinel and parsed.date() == RELEASE_DATE_SENTINEL:
        return NormalizedTimestamp(
            raw_value=value,
            normalized_text=text.value,
            value=None,
            status=TimestampParseStatus.SENTINEL_3000_DATE,
            missing_status=MissingValueStatus.SENTINEL_3000_DATE,
        )

    return NormalizedTimestamp(
        raw_value=value,
        normalized_text=text.value,
        value=parsed,
        status=TimestampParseStatus.PARSED,
        missing_status=MissingValueStatus.PRESENT,
    )


def validate_publisher_did(
    proposal_id: object,
    obs_publisher_did: object,
) -> PublisherDidValidation:
    """Validate the current project-level ALMA publisher-DID convention."""

    proposal = normalize_optional_text(proposal_id)
    publisher = normalize_optional_text(obs_publisher_did)

    if proposal.value is None:
        return PublisherDidValidation(
            proposal_id=proposal,
            obs_publisher_did=publisher,
            expected_publisher_did=None,
            status=PublisherDidMappingStatus.MISSING_PROPOSAL_ID,
        )

    expected = f"{PUBLISHER_DID_PREFIX}{proposal.value}"
    if publisher.value is None:
        status = PublisherDidMappingStatus.MISSING_PUBLISHER_DID
    elif publisher.value != expected:
        status = PublisherDidMappingStatus.MISMATCH
    else:
        raw_proposal = _as_text(proposal_id)
        raw_publisher = _as_text(obs_publisher_did)
        if raw_proposal == proposal.value and raw_publisher == expected:
            status = PublisherDidMappingStatus.MATCH
        else:
            status = PublisherDidMappingStatus.MATCH_AFTER_NORMALIZATION

    return PublisherDidValidation(
        proposal_id=proposal,
        obs_publisher_did=publisher,
        expected_publisher_did=expected,
        status=status,
    )


def normalize_archive_metadata(
    metadata: ArchiveMetadataInput,
) -> ArchiveMetadataNormalization:
    """Normalize the v0.4 metadata subset required before reconstruction."""

    return ArchiveMetadataNormalization(
        publisher_did=validate_publisher_did(
            metadata.proposal_id,
            metadata.obs_publisher_did,
        ),
        group_ous_uid=normalize_optional_text(metadata.group_ous_uid),
        science_observation=normalize_archive_boolean(
            metadata.science_observation
        ),
        is_mosaic=normalize_archive_boolean(metadata.is_mosaic),
        qa2_passed=normalize_archive_boolean(metadata.qa2_passed),
        obs_release_date=normalize_archive_timestamp(
            metadata.obs_release_date,
            classify_release_sentinel=True,
        ),
        last_modified=normalize_archive_timestamp(metadata.last_modified),
        normalization_version=NORMALIZATION_VERSION,
    )
