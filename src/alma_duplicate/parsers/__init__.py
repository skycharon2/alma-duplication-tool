"""Parsers for structured ALMA metadata."""

from .frequency_support import (
    parse_frequency_support,
    parse_frequency_support_component,
)

__all__ = [
    "parse_frequency_support",
    "parse_frequency_support_component",
]
