from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import numpy.ma as ma
import pandas as pd
import pytest

from alma_duplicate.domain import (
    ArchiveMetadataInput,
    BooleanParseStatus,
    MissingValueStatus,
    PublisherDidMappingStatus,
    TimestampParseStatus,
)
from alma_duplicate.normalization import (
    normalize_archive_boolean,
    normalize_archive_metadata,
    normalize_archive_timestamp,
    normalize_optional_text,
    validate_publisher_did,
)


def test_present_text_is_trimmed_and_raw_value_is_preserved() -> None:
    result = normalize_optional_text("  uid://A001/X1/X2  ")

    assert result.raw_value == "  uid://A001/X1/X2  "
    assert result.value == "uid://A001/X1/X2"
    assert result.missing_status is MissingValueStatus.PRESENT
    assert result.is_present


def test_blank_text_is_normalized_to_missing() -> None:
    result = normalize_optional_text("   \t")

    assert result.value is None
    assert result.missing_status is MissingValueStatus.BLANK_NORMALIZED
    assert not result.is_present


@pytest.mark.parametrize(
    "raw_value",
    [None, float("nan"), pd.NA],
    ids=["none", "nan", "pandas_na"],
)
def test_null_scalars_are_classified(raw_value: object) -> None:
    result = normalize_optional_text(raw_value)

    assert result.value is None
    assert result.missing_status is MissingValueStatus.NULL


def test_masked_scalar_remains_distinct_from_null() -> None:
    result = normalize_optional_text(ma.masked)

    assert result.value is None
    assert result.missing_status is MissingValueStatus.MASKED


@pytest.mark.parametrize(
    ("raw_value", "expected_value", "expected_status"),
    [
        ("T", True, BooleanParseStatus.TRUE),
        (" t ", True, BooleanParseStatus.TRUE),
        ("F", False, BooleanParseStatus.FALSE),
        (" f ", False, BooleanParseStatus.FALSE),
    ],
)
def test_archive_boolean_values_are_normalized(
    raw_value: str,
    expected_value: bool,
    expected_status: BooleanParseStatus,
) -> None:
    result = normalize_archive_boolean(raw_value)

    assert result.value is expected_value
    assert result.status is expected_status
    assert result.missing_status is MissingValueStatus.PRESENT


def test_unknown_boolean_is_not_coerced() -> None:
    result = normalize_archive_boolean("unknown")

    assert result.normalized_text == "unknown"
    assert result.value is None
    assert result.status is BooleanParseStatus.UNKNOWN
    assert result.missing_status is MissingValueStatus.PRESENT


def test_missing_boolean_preserves_missing_reason() -> None:
    result = normalize_archive_boolean(" ")

    assert result.value is None
    assert result.status is BooleanParseStatus.MISSING
    assert result.missing_status is MissingValueStatus.BLANK_NORMALIZED


def test_exact_publisher_did_mapping_is_accepted() -> None:
    result = validate_publisher_did(
        "2022.1.00506.S",
        "ADS/JAO.ALMA#2022.1.00506.S",
    )

    assert result.expected_publisher_did == (
        "ADS/JAO.ALMA#2022.1.00506.S"
    )
    assert result.status is PublisherDidMappingStatus.MATCH
    assert result.is_match


def test_publisher_did_match_after_trimming_is_visible() -> None:
    result = validate_publisher_did(
        " 2022.1.00506.S ",
        " ADS/JAO.ALMA#2022.1.00506.S ",
    )

    assert result.status is (
        PublisherDidMappingStatus.MATCH_AFTER_NORMALIZATION
    )
    assert result.is_match


def test_publisher_did_mismatch_is_reported() -> None:
    result = validate_publisher_did(
        "2022.1.00506.S",
        "ADS/JAO.ALMA#2021.1.00001.S",
    )

    assert result.status is PublisherDidMappingStatus.MISMATCH
    assert not result.is_match


@pytest.mark.parametrize(
    ("proposal_id", "publisher_did", "expected_status"),
    [
        (
            None,
            "ADS/JAO.ALMA#2022.1.00506.S",
            PublisherDidMappingStatus.MISSING_PROPOSAL_ID,
        ),
        (
            "2022.1.00506.S",
            None,
            PublisherDidMappingStatus.MISSING_PUBLISHER_DID,
        ),
    ],
)
def test_missing_publisher_mapping_inputs_are_reported(
    proposal_id: object,
    publisher_did: object,
    expected_status: PublisherDidMappingStatus,
) -> None:
    result = validate_publisher_did(proposal_id, publisher_did)

    assert result.status is expected_status
    assert not result.is_match


def test_valid_timestamp_is_parsed() -> None:
    result = normalize_archive_timestamp("2026-08-25T12:30:45Z")

    assert result.status is TimestampParseStatus.PARSED
    assert result.value == datetime(
        2026,
        8,
        25,
        12,
        30,
        45,
        tzinfo=timezone.utc,
    )
    assert result.missing_status is MissingValueStatus.PRESENT


def test_release_date_3000_is_classified_as_sentinel() -> None:
    result = normalize_archive_timestamp(
        "3000-01-01 00:00:00.000",
        classify_release_sentinel=True,
    )

    assert result.normalized_text == "3000-01-01 00:00:00.000"
    assert result.value is None
    assert result.status is TimestampParseStatus.SENTINEL_3000_DATE
    assert result.missing_status is MissingValueStatus.SENTINEL_3000_DATE


def test_year_3000_is_not_sentinel_for_other_timestamp_fields() -> None:
    result = normalize_archive_timestamp(
        "3000-01-01 00:00:00.000",
        classify_release_sentinel=False,
    )

    assert result.status is TimestampParseStatus.PARSED
    assert result.value == datetime(3000, 1, 1)


def test_invalid_timestamp_is_preserved_and_reported() -> None:
    result = normalize_archive_timestamp("not-a-timestamp")

    assert result.raw_value == "not-a-timestamp"
    assert result.normalized_text == "not-a-timestamp"
    assert result.value is None
    assert result.status is TimestampParseStatus.INVALID
    assert result.missing_status is MissingValueStatus.PRESENT


def test_complete_metadata_normalization_contract() -> None:
    result = normalize_archive_metadata(
        ArchiveMetadataInput(
            proposal_id="2022.1.00506.S",
            obs_publisher_did=(
                "ADS/JAO.ALMA#2022.1.00506.S"
            ),
            group_ous_uid=" ",
            science_observation="T",
            is_mosaic="F",
            qa2_passed="unexpected",
            obs_release_date="3000-01-01 00:00:00.000",
            last_modified="2026-08-25T13:03:55",
        )
    )

    assert result.normalization_version == "1"
    assert result.publisher_did.is_match
    assert result.group_ous_uid.value is None
    assert result.group_ous_uid.missing_status is (
        MissingValueStatus.BLANK_NORMALIZED
    )
    assert result.science_observation.value is True
    assert result.is_mosaic.value is False
    assert result.qa2_passed.status is BooleanParseStatus.UNKNOWN
    assert result.obs_release_date.status is (
        TimestampParseStatus.SENTINEL_3000_DATE
    )
    assert result.last_modified.status is TimestampParseStatus.PARSED


def test_normalized_domain_values_are_immutable() -> None:
    result = normalize_optional_text("value")

    with pytest.raises(FrozenInstanceError):
        result.value = "changed"
