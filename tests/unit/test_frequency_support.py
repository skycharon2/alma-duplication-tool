from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from alma_duplicate.domain.spectral import (
    BraceTokenSemanticStatus,
    FrequencySupportGrammar,
    ParseStatus,
)
from alma_duplicate.parsers.frequency_support import (
    parse_frequency_support,
    parse_frequency_support_component,
)

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

BRACKET_EXAMPLE = (
    "[214.32..216.21GHz, 976.56kHz, "
    "1mJy/beam@10km/s, "
    "0.2mJy/beam@native, XX YY]"
)

BRACE_EXAMPLE = (
    "{229.98GHz,2000000.00kHz,"
    "20.8mJy/beam@10km/s,"
    "1.3mJy/beam@native, XX YY}"
)


def test_bracket_parser_remains_backward_compatible() -> None:
    result = parse_frequency_support(
        BRACKET_EXAMPLE
    )

    assert result.parser_version == "2"
    assert (
        result.grammar_family
        is FrequencySupportGrammar.BRACKET
    )
    assert result.parse_status is ParseStatus.PARSED
    assert result.is_valid

    component = result.components[0]

    assert component.frequency_interval is not None
    assert component.resolution is not None
    assert component.displayed_center is None
    assert component.brace_token_2 is None

    legacy_component = (
        parse_frequency_support_component(
            BRACKET_EXAMPLE[1:-1]
        )
    )

    assert legacy_component == component


def test_canonical_brace_value_is_parsed() -> None:
    result = parse_frequency_support(
        BRACE_EXAMPLE
    )

    assert result.parser_version == "2"
    assert (
        result.grammar_family
        is FrequencySupportGrammar.BRACE
    )
    assert result.parse_status is ParseStatus.PARSED
    assert result.is_valid
    assert len(result.components) == 1

    component = result.components[0]

    assert component.frequency_interval is None
    assert component.resolution is None

    assert component.displayed_center is not None
    assert component.displayed_center.value == pytest.approx(
        229.98
    )
    assert component.displayed_center.unit == "GHz"

    assert component.brace_token_2 is not None
    assert component.brace_token_2.value == pytest.approx(
        2_000_000.0
    )
    assert component.brace_token_2.unit == "kHz"

    assert (
        component.representation_tolerance_mhz
        == pytest.approx(5.0)
    )

    assert (
        component.brace_token_semantic_status
        is BraceTokenSemanticStatus.UNRESOLVED
    )


def test_multiple_brace_components_are_supported() -> None:
    result = parse_frequency_support(
        f"{BRACE_EXAMPLE} U {BRACE_EXAMPLE}"
    )

    assert result.parse_status is ParseStatus.PARSED
    assert (
        result.grammar_family
        is FrequencySupportGrammar.BRACE
    )
    assert len(result.components) == 2
    assert result.is_valid


@pytest.mark.parametrize(
    ("raw", "expected_grammar", "expected_issue"),
    [
        (
            None,
            FrequencySupportGrammar.MISSING,
            "frequency_support_missing",
        ),
        (
            "   ",
            FrequencySupportGrammar.BLANK,
            "frequency_support_blank",
        ),
        (
            "not an Archive frequency support",
            FrequencySupportGrammar.UNKNOWN,
            "frequency_support_grammar_unknown",
        ),
        (
            "{229.98GHz",
            FrequencySupportGrammar.BRACE,
            "braced_component_missing",
        ),
    ],
)
def test_frequency_support_grammar_failures(
    raw: str | None,
    expected_grammar: FrequencySupportGrammar,
    expected_issue: str,
) -> None:
    result = parse_frequency_support(raw)

    assert result.parse_status is ParseStatus.FAILED
    assert result.grammar_family is expected_grammar
    assert expected_issue in _issue_codes(result)


def test_component_separator_is_validated() -> None:
    result = parse_frequency_support(
        f"{BRACKET_EXAMPLE} garbage "
        f"{BRACKET_EXAMPLE}"
    )

    assert result.parse_status is ParseStatus.PARTIAL
    assert (
        "unexpected_component_separator"
        in _issue_codes(result)
    )
