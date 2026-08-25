"""Source-independent domain objects."""

from .spectral import (
    BraceTokenSemanticStatus,
    FrequencyInterval,
    FrequencySupportComponent,
    FrequencySupportGrammar,
    FrequencySupportParseResult,
    ParseStatus,
    ParsedQuantity,
    SensitivityEntry,
    ValidationIssue,
)

__all__ = [
    "BraceTokenSemanticStatus",
    "FrequencyInterval",
    "FrequencySupportComponent",
    "FrequencySupportGrammar",
    "FrequencySupportParseResult",
    "ParseStatus",
    "ParsedQuantity",
    "SensitivityEntry",
    "ValidationIssue",
]