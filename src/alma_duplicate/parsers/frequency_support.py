"""Parse ALMA Archive ``frequency_support`` values without policy decisions."""

from __future__ import annotations

import math
import re

from astropy import units as u

from alma_duplicate.domain.spectral import (
    FrequencyInterval,
    FrequencySupportComponent,
    FrequencySupportParseResult,
    ParseStatus,
    ParsedQuantity,
    SensitivityEntry,
    ValidationIssue,
)

PARSER_VERSION = "1"

NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
BRACKET_COMPONENT_PATTERN = re.compile(r"\[([^\[\]]*)\]")
FREQUENCY_RANGE_PATTERN = re.compile(
    rf"^\s*(?P<low>{NUMBER_PATTERN})\s*\.\.\s*"
    rf"(?P<high>{NUMBER_PATTERN})\s*(?P<unit>[A-Za-z]+)\s*$"
)
QUANTITY_PATTERN = re.compile(
    rf"^\s*(?P<value>{NUMBER_PATTERN})\s*(?P<unit>.+?)\s*$"
)
SENSITIVITY_PATTERN = re.compile(
    rf"^\s*(?P<value>{NUMBER_PATTERN})\s*(?P<unit>[^@]+?)"
    rf"\s*@\s*(?P<basis>.+?)\s*$"
)

VALID_POLARIZATION_PRODUCTS = frozenset({"XX", "YY", "XY", "YX"})
REQUIRED_SENSITIVITY_BASES = frozenset({"10km/s", "native"})


def _issue(
    code: str,
    message: str,
    component_index: int | None = None,
    token: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(code, message, component_index, token)


def normalize_frequency_support_text(
    value: str | bytes | None,
) -> str | None:
    """Decode and trim input while treating blank and floating NaN as missing."""

    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = text.strip()
    return text or None


def _unit_is_convertible(unit_text: str, target: u.UnitBase) -> bool:
    try:
        (1 * u.Unit(unit_text)).to(target)
    except (TypeError, ValueError, u.UnitConversionError):
        return False
    return True


def parse_frequency_support_component(
    component_text: str,
    component_index: int = 1,
) -> FrequencySupportComponent:
    """Parse one bracket payload and validate its structural contract."""

    tokens = tuple(
        token.strip() for token in component_text.split(",") if token.strip()
    )
    parse_issues: list[ValidationIssue] = []
    validation_issues: list[ValidationIssue] = []
    sensitivities: list[SensitivityEntry] = []
    polarization_products: list[str] = []
    unknown_tokens: list[str] = []
    interval: FrequencyInterval | None = None
    resolution: ParsedQuantity | None = None

    if not tokens:
        parse_issues.append(
            _issue(
                "empty_component",
                "Component contains no tokens.",
                component_index,
            )
        )
    else:
        frequency_match = FREQUENCY_RANGE_PATTERN.fullmatch(tokens[0])
        if frequency_match is None:
            parse_issues.append(
                _issue(
                    "frequency_range_unparsed",
                    "Frequency range could not be parsed.",
                    component_index,
                    tokens[0],
                )
            )
        else:
            interval = FrequencyInterval(
                low=float(frequency_match.group("low")),
                high=float(frequency_match.group("high")),
                unit=frequency_match.group("unit"),
                raw_token=tokens[0],
            )

    if len(tokens) < 2:
        parse_issues.append(
            _issue(
                "resolution_missing",
                "Frequency resolution token is missing.",
                component_index,
            )
        )
    else:
        resolution_match = QUANTITY_PATTERN.fullmatch(tokens[1])
        if resolution_match is None:
            parse_issues.append(
                _issue(
                    "resolution_unparsed",
                    "Frequency resolution could not be parsed.",
                    component_index,
                    tokens[1],
                )
            )
        else:
            resolution = ParsedQuantity(
                value=float(resolution_match.group("value")),
                unit=resolution_match.group("unit").strip(),
                raw_token=tokens[1],
            )

    for token in tokens[2:]:
        if "@" in token:
            sensitivity_match = SENSITIVITY_PATTERN.fullmatch(token)
            if sensitivity_match is None:
                parse_issues.append(
                    _issue(
                        "sensitivity_unparsed",
                        "Sensitivity token could not be parsed.",
                        component_index,
                        token,
                    )
                )
                unknown_tokens.append(token)
                continue
            sensitivities.append(
                SensitivityEntry(
                    value=float(sensitivity_match.group("value")),
                    unit=sensitivity_match.group("unit").strip(),
                    basis=sensitivity_match.group("basis").strip(),
                    raw_token=token,
                )
            )
            continue

        products = token.split()
        for product in products:
            if product in VALID_POLARIZATION_PRODUCTS:
                polarization_products.append(product)
            else:
                unknown_tokens.append(product)

    if interval is not None:
        if interval.low >= interval.high:
            validation_issues.append(
                _issue(
                    "frequency_range_order",
                    "Frequency lower bound must be smaller than the upper bound.",
                    component_index,
                    interval.raw_token,
                )
            )
        if not _unit_is_convertible(interval.unit, u.GHz):
            validation_issues.append(
                _issue(
                    "frequency_unit_incompatible",
                    "Frequency unit is not convertible to GHz.",
                    component_index,
                    interval.unit,
                )
            )

    if resolution is not None and not _unit_is_convertible(
        resolution.unit, u.MHz
    ):
        validation_issues.append(
            _issue(
                "resolution_unit_incompatible",
                "Resolution unit is not convertible to MHz.",
                component_index,
                resolution.unit,
            )
        )

    sensitivity_bases = {entry.basis.lower() for entry in sensitivities}
    for required_basis in sorted(REQUIRED_SENSITIVITY_BASES):
        if required_basis not in sensitivity_bases:
            validation_issues.append(
                _issue(
                    "sensitivity_basis_missing",
                    f"Missing sensitivity basis: {required_basis}.",
                    component_index,
                    required_basis,
                )
            )

    for entry in sensitivities:
        if not _unit_is_convertible(entry.unit, u.mJy / u.beam):
            validation_issues.append(
                _issue(
                    "sensitivity_unit_incompatible",
                    "Sensitivity unit is not convertible to mJy/beam.",
                    component_index,
                    entry.unit,
                )
            )

    if not polarization_products:
        validation_issues.append(
            _issue(
                "polarization_missing",
                "No recognized polarization product was found.",
                component_index,
            )
        )
    if unknown_tokens:
        validation_issues.append(
            _issue(
                "unknown_token",
                "One or more component tokens are unknown.",
                component_index,
                " ".join(unknown_tokens),
            )
        )

    if interval is None:
        parse_status = ParseStatus.FAILED
    elif parse_issues:
        parse_status = ParseStatus.PARTIAL
    else:
        parse_status = ParseStatus.PARSED

    return FrequencySupportComponent(
        component_index=component_index,
        raw_text=component_text,
        frequency_interval=interval,
        resolution=resolution,
        sensitivities=tuple(sensitivities),
        polarization_products=tuple(polarization_products),
        unknown_tokens=tuple(unknown_tokens),
        parse_status=parse_status,
        parse_issues=tuple(parse_issues),
        validation_issues=tuple(validation_issues),
    )


def parse_frequency_support(
    raw_value: str | bytes | None,
) -> FrequencySupportParseResult:
    """Parse a complete Archive frequency_support value without discarding raw text."""

    normalized = normalize_frequency_support_text(raw_value)
    if normalized is None:
        issue = _issue("frequency_support_missing", "Frequency support is missing.")
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=None,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
        )

    matches = tuple(BRACKET_COMPONENT_PATTERN.finditer(normalized))
    if not matches:
        issue = _issue(
            "bracketed_component_missing",
            "No bracketed frequency-support component was found.",
            token=normalized,
        )
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=normalized,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
        )

    components = tuple(
        parse_frequency_support_component(match.group(1).strip(), index)
        for index, match in enumerate(matches, start=1)
    )

    residual = BRACKET_COMPONENT_PATTERN.sub("", normalized)
    residual = re.sub(r"\s*U\s*", "", residual).strip()
    result_issues: list[ValidationIssue] = []
    if residual:
        result_issues.append(
            _issue(
                "unexpected_residual_text",
                "Unexpected text remains outside bracketed components.",
                token=residual,
            )
        )

    if all(component.parse_status is ParseStatus.FAILED for component in components):
        status = ParseStatus.FAILED
    elif result_issues or any(
        component.parse_status is not ParseStatus.PARSED
        for component in components
    ):
        status = ParseStatus.PARTIAL
    else:
        status = ParseStatus.PARSED

    return FrequencySupportParseResult(
        raw_value=raw_value,
        normalized_value=normalized,
        components=components,
        parse_status=status,
        parse_issues=tuple(result_issues),
        parser_version=PARSER_VERSION,
    )
