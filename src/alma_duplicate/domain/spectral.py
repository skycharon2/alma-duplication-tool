"""Domain objects for parsed ALMA spectral metadata.

These objects preserve parsed values and original unit text. Unit conversion and
duplication-policy decisions belong to later normalization and rule layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ParseStatus(StrEnum):
    """Syntactic parser outcome; separate from semantic validation."""

    PARSED = "PARSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class FrequencySupportGrammar(StrEnum):
    """Observed top-level grammar family of frequency_support."""

    BRACKET = "BRACKET"
    BRACE = "BRACE"
    MISSING = "MISSING"
    BLANK = "BLANK"
    UNKNOWN = "UNKNOWN"


class BraceTokenSemanticStatus(StrEnum):
    """Evidence status for the second token in a brace component."""

    UNRESOLVED = "UNRESOLVED"



@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One traceable parser or validation issue."""

    code: str
    message: str
    component_index: int | None = None
    token: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedQuantity:
    """A numeric value with its unmodified unit text and source token."""

    value: float
    unit: str
    raw_token: str


@dataclass(frozen=True, slots=True)
class FrequencyInterval:
    """Parsed frequency bounds sharing one original unit."""

    low: float
    high: float
    unit: str
    raw_token: str


@dataclass(frozen=True, slots=True)
class SensitivityEntry:
    """One component-level sensitivity and its measurement basis."""

    value: float
    unit: str
    basis: str
    raw_token: str


@dataclass(frozen=True, slots=True)
class FrequencySupportComponent:
    """One component from an Archive frequency_support value."""

    component_index: int
    raw_text: str
    frequency_interval: FrequencyInterval | None
    resolution: ParsedQuantity | None
    sensitivities: tuple[SensitivityEntry, ...]
    polarization_products: tuple[str, ...]
    unknown_tokens: tuple[str, ...]
    parse_status: ParseStatus
    parse_issues: tuple[ValidationIssue, ...]
    validation_issues: tuple[ValidationIssue, ...]
    grammar_family: FrequencySupportGrammar = (
        FrequencySupportGrammar.BRACKET
    )
    displayed_center: ParsedQuantity | None = None
    brace_token_2: ParsedQuantity | None = None
    representation_tolerance_mhz: float | None = None
    brace_token_semantic_status: (
        BraceTokenSemanticStatus | None
    ) = None

    @property
    def is_valid(self) -> bool:
        return (
            self.parse_status is ParseStatus.PARSED
            and not self.validation_issues
        )


@dataclass(frozen=True, slots=True)
class FrequencySupportParseResult:
    """Structured result for one complete raw frequency_support value."""

    raw_value: str | bytes | None
    normalized_value: str | None
    components: tuple[FrequencySupportComponent, ...]
    parse_status: ParseStatus
    parse_issues: tuple[ValidationIssue, ...]
    parser_version: str
    grammar_family: FrequencySupportGrammar = (
        FrequencySupportGrammar.UNKNOWN
    )

    @property
    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(
            issue
            for component in self.components
            for issue in component.validation_issues
        )

    @property
    def is_valid(self) -> bool:
        return (
            self.parse_status is ParseStatus.PARSED
            and bool(self.components)
            and all(component.is_valid for component in self.components)
        )
