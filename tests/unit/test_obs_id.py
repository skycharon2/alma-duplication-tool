from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from alma_duplicate.domain.archive import (
    ObsIdConfidence,
    ObsIdFailureClass,
    ObsIdParseStatus,
    ObsIdWidthStatus,
)
from alma_duplicate.parsers.obs_id import (
    OBS_ID_DECLARED_WIDTH,
    OBS_ID_PARSER_VERSION,
    parse_obs_id,
)

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "obs_id_cases.json"
)


def _cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open(
        encoding="utf-8"
    ) as fixture_file:
        return json.load(fixture_file)


def _issue_codes(result) -> set[str]:
    return {
        issue.code
        for issue in result.issues
    }


@pytest.mark.parametrize(
    "case",
    _cases(),
    ids=lambda case: str(case["id"]),
)
def test_obs_id_contract(
    case: dict[str, object],
) -> None:
    result = parse_obs_id(case["raw"])

    assert result.parse_status is ObsIdParseStatus(
        case["expected_status"]
    )
    assert result.confidence is ObsIdConfidence(
        case["expected_confidence"]
    )
    assert result.width_status is ObsIdWidthStatus(
        case["expected_width_status"]
    )

    expected_failure_class = case[
        "expected_failure_class"
    ]

    if expected_failure_class is None:
        assert result.failure_class is None
    else:
        assert (
            result.failure_class
            is ObsIdFailureClass(
                expected_failure_class
            )
        )

    assert (
        result.member_ous_uid
        == case["expected_member_ous_uid"]
    )
    assert (
        result.source_name
        == case["expected_source_name"]
    )
    assert (
        result.spw_token
        == case["expected_spw_token"]
    )
    assert (
        result.spw_index
        == case["expected_spw_index"]
    )
    assert (
        result.is_safe_for_reconstruction
        is case["expected_safe"]
    )
    assert result.has_width_schema_drift is (
        result.width_status
        is ObsIdWidthStatus.ABOVE_DECLARED_WIDTH_SCHEMA_DRIFT
    )

    assert set(
        case["expected_issue_codes"]
    ).issubset(_issue_codes(result))
    assert result.parser_version == OBS_ID_PARSER_VERSION == "2"


def test_declared_width_cases_are_exactly_64_chars() -> None:
    width_case_ids = {
        "parsed_at_declared_width",
        "truncated_after_spw_marker",
        "truncated_in_source_segment",
    }

    for case in _cases():
        if case["id"] in width_case_ids:
            assert len(case["raw"]) == (
                OBS_ID_DECLARED_WIDTH
            )


def test_real_schema_drift_case_is_exactly_65_chars() -> None:
    case = next(
        item
        for item in _cases()
        if item["id"]
        == "parsed_above_declared_width_schema_drift"
    )

    assert len(case["raw"]) == OBS_ID_DECLARED_WIDTH + 1


def test_bytes_are_decoded_and_raw_value_is_preserved() -> None:
    raw = (
        b"uid://A001/X1/X1.source.Target.spw.4"
    )

    result = parse_obs_id(raw)

    assert result.raw_value == raw
    assert (
        result.normalized_value
        == "uid://A001/X1/X1.source.Target.spw.4"
    )
    assert result.is_safe_for_reconstruction
    assert result.spw_index == 4


def test_parse_result_is_immutable() -> None:
    result = parse_obs_id(
        "uid://A001/X1/X1.source.Target.spw.4"
    )

    with pytest.raises(FrozenInstanceError):
        result.parser_version = "changed"


@pytest.mark.parametrize(
    "declared_width",
    [0, -1],
)
def test_declared_width_must_be_positive(
    declared_width: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        parse_obs_id(
            "uid://A001/X1/X1.source.Target.spw.4",
            declared_width=declared_width,
        )
