"""Parse ALMA Archive ``frequency_support`` values without policy decisions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
import re

from astropy import units as u

from alma_duplicate.domain.spectral import (
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
PARSER_VERSION = "2"

NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
BRACKET_COMPONENT_PATTERN = re.compile(r"\[([^\[\]]*)\]")
BRACE_COMPONENT_PATTERN = re.compile(r"\{([^{}]*)\}")
UNION_SEPARATOR_PATTERN = re.compile(r"\s*U\s*")
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


def _is_float_nan(value: object) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _classify_frequency_support(
    value: str | bytes | None,
) -> tuple[FrequencySupportGrammar, str | None]:
    """Classify the input without losing missing-versus-blank state."""

    if value is None or _is_float_nan(value):
        return FrequencySupportGrammar.MISSING, None

    if isinstance(value, bytes):
        text = value.decode(
            "utf-8",
            errors="replace",
        ).strip()
    else:
        text = str(value).strip()

    if not text:
        return FrequencySupportGrammar.BLANK, None

    if text.startswith("["):
        return FrequencySupportGrammar.BRACKET, text

    if text.startswith("{"):
        return FrequencySupportGrammar.BRACE, text

    if BRACKET_COMPONENT_PATTERN.search(text):
        return FrequencySupportGrammar.BRACKET, text

    if BRACE_COMPONENT_PATTERN.search(text):
        return FrequencySupportGrammar.BRACE, text

    return FrequencySupportGrammar.UNKNOWN, text




def _unit_is_convertible(unit_text: str, target: u.UnitBase) -> bool:
    try:
        (1 * u.Unit(unit_text)).to(target)
    except (TypeError, ValueError, u.UnitConversionError):
        return False
    return True

def _parse_quantity(
    token: str,
) -> ParsedQuantity | None:
    match = QUANTITY_PATTERN.fullmatch(token)

    if match is None:
        return None

    return ParsedQuantity(
        value=float(match.group("value")),
        unit=match.group("unit").strip(),
        raw_token=token,
    )


def _display_tolerance_mhz(
    token: str,
) -> float | None:
    """Return half of the displayed centre-frequency quantum.

    Example:
        229.98 GHz has a displayed quantum of 0.01 GHz.
        Half a quantum is 0.005 GHz = 5 MHz.
    """

    match = QUANTITY_PATTERN.fullmatch(token)

    if match is None:
        return None

    unit_text = match.group("unit").strip()

    if not _unit_is_convertible(
        unit_text,
        u.MHz,
    ):
        return None

    try:
        displayed_value = Decimal(
            match.group("value")
        )
        quantum = Decimal(1).scaleb(
            displayed_value.as_tuple().exponent
        )
        half_quantum = abs(quantum) / Decimal(2)
    except (InvalidOperation, ValueError):
        return None

    return (
        float(half_quantum) * u.Unit(unit_text)
    ).to_value(u.MHz)



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

def _parse_brace_component(
    component_text: str,
    component_index: int,
) -> FrequencySupportComponent:
    """Parse one brace-family frequency-support component."""

    tokens = tuple(
        token.strip()
        for token in component_text.split(",")
        if token.strip()
    )

    parse_issues: list[ValidationIssue] = []
    validation_issues: list[ValidationIssue] = []
    sensitivities: list[SensitivityEntry] = []
    polarization_products: list[str] = []
    unknown_tokens: list[str] = []

    displayed_center: ParsedQuantity | None = None
    brace_token_2: ParsedQuantity | None = None

    if not tokens:
        parse_issues.append(
            _issue(
                "empty_component",
                "Component contains no tokens.",
                component_index,
            )
        )
    else:
        displayed_center = _parse_quantity(tokens[0])

        if displayed_center is None:
            parse_issues.append(
                _issue(
                    "brace_center_unparsed",
                    "Displayed brace centre could not be parsed.",
                    component_index,
                    tokens[0],
                )
            )

    if len(tokens) < 2:
        parse_issues.append(
            _issue(
                "brace_token_2_missing",
                "Second brace token is missing.",
                component_index,
            )
        )
    else:
        brace_token_2 = _parse_quantity(tokens[1])

        if brace_token_2 is None:
            parse_issues.append(
                _issue(
                    "brace_token_2_unparsed",
                    "Second brace token could not be parsed.",
                    component_index,
                    tokens[1],
                )
            )

    for token in tokens[2:]:
        if "@" in token:
            sensitivity_match = (
                SENSITIVITY_PATTERN.fullmatch(token)
            )

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
                    value=float(
                        sensitivity_match.group("value")
                    ),
                    unit=sensitivity_match.group(
                        "unit"
                    ).strip(),
                    basis=sensitivity_match.group(
                        "basis"
                    ).strip(),
                    raw_token=token,
                )
            )
            continue

        for product in token.split():
            if product in VALID_POLARIZATION_PRODUCTS:
                polarization_products.append(product)
            else:
                unknown_tokens.append(product)

    if displayed_center is not None:
        if not _unit_is_convertible(
            displayed_center.unit,
            u.GHz,
        ):
            validation_issues.append(
                _issue(
                    "brace_center_unit_incompatible",
                    (
                        "Displayed brace centre unit is "
                        "not convertible to GHz."
                    ),
                    component_index,
                    displayed_center.unit,
                )
            )

    if brace_token_2 is not None:
        if not _unit_is_convertible(
            brace_token_2.unit,
            u.MHz,
        ):
            validation_issues.append(
                _issue(
                    "brace_token_2_unit_incompatible",
                    (
                        "Second brace token unit is not "
                        "frequency-like."
                    ),
                    component_index,
                    brace_token_2.unit,
                )
            )

    sensitivity_bases = {
        entry.basis.lower()
        for entry in sensitivities
    }

    for required_basis in sorted(
        REQUIRED_SENSITIVITY_BASES
    ):
        if required_basis not in sensitivity_bases:
            validation_issues.append(
                _issue(
                    "sensitivity_basis_missing",
                    (
                        "Missing sensitivity basis: "
                        f"{required_basis}."
                    ),
                    component_index,
                    required_basis,
                )
            )

    for entry in sensitivities:
        if not _unit_is_convertible(
            entry.unit,
            u.mJy / u.beam,
        ):
            validation_issues.append(
                _issue(
                    "sensitivity_unit_incompatible",
                    (
                        "Sensitivity unit is not "
                        "convertible to mJy/beam."
                    ),
                    component_index,
                    entry.unit,
                )
            )

    if not polarization_products:
        validation_issues.append(
            _issue(
                "polarization_missing",
                (
                    "No recognized polarization product "
                    "was found."
                ),
                component_index,
            )
        )

    if unknown_tokens:
        validation_issues.append(
            _issue(
                "unknown_token",
                (
                    "One or more component tokens "
                    "are unknown."
                ),
                component_index,
                " ".join(unknown_tokens),
            )
        )

    if displayed_center is None:
        parse_status = ParseStatus.FAILED
    elif parse_issues:
        parse_status = ParseStatus.PARTIAL
    else:
        parse_status = ParseStatus.PARSED

    return FrequencySupportComponent(
        component_index=component_index,
        raw_text=component_text,
        frequency_interval=None,

        # Do not write brace token 2 into resolution.
        # Its precise semantics remain unresolved.
        resolution=None,

        sensitivities=tuple(sensitivities),
        polarization_products=tuple(
            polarization_products
        ),
        unknown_tokens=tuple(unknown_tokens),
        parse_status=parse_status,
        parse_issues=tuple(parse_issues),
        validation_issues=tuple(validation_issues),
        grammar_family=FrequencySupportGrammar.BRACE,
        displayed_center=displayed_center,
        brace_token_2=brace_token_2,
        representation_tolerance_mhz=(
            _display_tolerance_mhz(tokens[0])
            if tokens
            else None
        ),
        brace_token_semantic_status=(
            BraceTokenSemanticStatus.UNRESOLVED
            if brace_token_2 is not None
            else None
        ),
    )

def _component_separator_issues(
    normalized: str,
    matches: tuple[re.Match[str], ...],
) -> tuple[ValidationIssue, ...]:
    """Validate leading, inter-component and trailing text."""

    if not matches:
        return ()

    issues: list[ValidationIssue] = []

    leading = normalized[: matches[0].start()]
    trailing = normalized[matches[-1].end() :]

    if leading.strip():
        issues.append(
            _issue(
                "unexpected_residual_text",
                (
                    "Unexpected text appears before "
                    "the first component."
                ),
                token=leading.strip(),
            )
        )

    for left, right in zip(
        matches[:-1],
        matches[1:],
        strict=True,
    ):
        separator = normalized[
            left.end() : right.start()
        ]

        if (
            UNION_SEPARATOR_PATTERN.fullmatch(
                separator
            )
            is None
        ):
            issues.append(
                _issue(
                    "unexpected_component_separator",
                    (
                        "Components must be separated by "
                        "the Archive union token U."
                    ),
                    token=separator,
                )
            )

    if trailing.strip():
        issues.append(
            _issue(
                "unexpected_residual_text",
                (
                    "Unexpected text appears after "
                    "the final component."
                ),
                token=trailing.strip(),
            )
        )

    return tuple(issues)

def _parse_bracket_frequency_support(
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
            grammar_family=FrequencySupportGrammar.BRACKET,
        )

    components = tuple(
        parse_frequency_support_component(match.group(1).strip(), index)
        for index, match in enumerate(matches, start=1)
    )

    result_issues = _component_separator_issues(
        normalized,
        matches,
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
        parse_issues=result_issues,
        parser_version=PARSER_VERSION,
        grammar_family=FrequencySupportGrammar.BRACKET,
    )

def _parse_brace_frequency_support(
    raw_value: str | bytes | None,
) -> FrequencySupportParseResult:
    normalized = normalize_frequency_support_text(
        raw_value
    )

    if normalized is None:
        issue = _issue(
            "frequency_support_missing",
            "Frequency support is missing.",
        )
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=None,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
            grammar_family=(
                FrequencySupportGrammar.MISSING
            ),
        )

    matches = tuple(
        BRACE_COMPONENT_PATTERN.finditer(normalized)
    )

    if not matches:
        issue = _issue(
            "braced_component_missing",
            (
                "No braced frequency-support component "
                "was found."
            ),
            token=normalized,
        )
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=normalized,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
            grammar_family=(
                FrequencySupportGrammar.BRACE
            ),
        )

    components = tuple(
        _parse_brace_component(
            match.group(1).strip(),
            index,
        )
        for index, match in enumerate(
            matches,
            start=1,
        )
    )

    result_issues = _component_separator_issues(
        normalized,
        matches,
    )

    if all(
        component.parse_status is ParseStatus.FAILED
        for component in components
    ):
        status = ParseStatus.FAILED
    elif result_issues or any(
        component.parse_status
        is not ParseStatus.PARSED
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
        parse_issues=result_issues,
        parser_version=PARSER_VERSION,
        grammar_family=FrequencySupportGrammar.BRACE,
    )

def parse_frequency_support(
    raw_value: str | bytes | None,
) -> FrequencySupportParseResult:
    """Dispatch and parse one Archive frequency_support value."""

    grammar, normalized = (
        _classify_frequency_support(raw_value)
    )

    if grammar is FrequencySupportGrammar.MISSING:
        issue = _issue(
            "frequency_support_missing",
            "Frequency support is missing.",
        )
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=None,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
            grammar_family=grammar,
        )

    if grammar is FrequencySupportGrammar.BLANK:
        issue = _issue(
            "frequency_support_blank",
            "Frequency support is blank.",
        )
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=None,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
            grammar_family=grammar,
        )

    if grammar is FrequencySupportGrammar.UNKNOWN:
        issue = _issue(
            "frequency_support_grammar_unknown",
            (
                "Frequency-support grammar is "
                "not recognized."
            ),
            token=normalized,
        )
        return FrequencySupportParseResult(
            raw_value=raw_value,
            normalized_value=normalized,
            components=(),
            parse_status=ParseStatus.FAILED,
            parse_issues=(issue,),
            parser_version=PARSER_VERSION,
            grammar_family=grammar,
        )

    if grammar is FrequencySupportGrammar.BRACKET:
        return _parse_bracket_frequency_support(
            raw_value
        )

    return _parse_brace_frequency_support(
        raw_value
    )
