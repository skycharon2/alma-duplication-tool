from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from alma_duplicate.domain.spectral import ParseStatus
from alma_duplicate.parsers.frequency_support import parse_frequency_support

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "frequency_support_cases.json"
)


def _cases() -> list[dict[str, object]]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _issue_codes(result) -> set[str]:
    return {
        issue.code
        for issue in (
            *result.parse_issues,
            *(
                issue
                for component in result.components
                for issue in (
                    *component.parse_issues,
                    *component.validation_issues,
                )
            ),
        )
    }


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["id"]))
def test_frequency_support_contract(case: dict[str, object]) -> None:
    result = parse_frequency_support(case["raw"])

    assert result.parse_status == ParseStatus(case["expected_status"])
    assert len(result.components) == case["expected_components"]
    assert result.is_valid is case["expected_valid"]
    assert set(case["expected_issue_codes"]).issubset(_issue_codes(result))


def test_complete_raw_value_and_component_text_are_preserved() -> None:
    raw = (
        "  [214.32..216.21GHz, 976.56kHz, "
        "1mJy/beam@10km/s, 0.2mJy/beam@native, XX YY]  "
    )

    result = parse_frequency_support(raw)

    assert result.raw_value == raw
    assert result.normalized_value == raw.strip()
    assert result.components[0].raw_text.startswith("214.32..216.21GHz")


def test_sensitivity_basis_and_unit_remain_separate() -> None:
    result = parse_frequency_support(
        "[214.32..216.21GHz, 976.56kHz, "
        "872.8uJy/beam@10km/s, 200uJy/beam@native, XX YY]"
    )

    entries = result.components[0].sensitivities
    assert [(entry.unit, entry.basis) for entry in entries] == [
        ("uJy/beam", "10km/s"),
        ("uJy/beam", "native"),
    ]


def test_domain_result_is_immutable() -> None:
    result = parse_frequency_support(
        "[214.32..216.21GHz, 976.56kHz, "
        "1mJy/beam@10km/s, 0.2mJy/beam@native, XX YY]"
    )

    with pytest.raises(FrozenInstanceError):
        result.parser_version = "changed"
