"""Source-independent domain objects."""

from .spectral import (
    FrequencyInterval,
    FrequencySupportComponent,
    FrequencySupportParseResult,
    ParseStatus,
    ParsedQuantity,
    SensitivityEntry,
    ValidationIssue,
)

__all__ = [
    "FrequencyInterval",
    "FrequencySupportComponent",
    "FrequencySupportParseResult",
    "ParseStatus",
    "ParsedQuantity",
    "SensitivityEntry",
    "ValidationIssue",
]
