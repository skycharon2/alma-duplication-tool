"""Parse only explicit Queue source-date declarations, without local guesses."""

import re
from datetime import date

_MONTHS = {name.casefold(): index for index, name in enumerate((
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
), start=1)}


def parse_source_as_of(description: str) -> tuple[date | None, str | None, str]:
    """Return date, raw declaration and status for a recognized as-of clause.

    Support English full-month dates and ISO dates only. Preserve unfamiliar
    declarations as evidence, without choosing among conflicting statements.
    """
    clauses = re.findall(r"\bas\s+of\s+([^\r\n.]*)", description, flags=re.I)
    if not clauses:
        return None, None, "MISSING"
    raw = "\n".join(clauses)
    if len(clauses) != 1:
        return None, raw, "AMBIGUOUS"
    value = clauses[0].strip()
    english = re.fullmatch(r"(\d{4})\s+([A-Za-z]+)\s+(\d{1,2})", value)
    iso = re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    try:
        if iso:
            return date.fromisoformat(value), raw, "PARSED"
        if english and english[2].casefold() in _MONTHS:
            return date(int(english[1]), _MONTHS[english[2].casefold()], int(english[3])), raw, "PARSED"
    except ValueError:
        return None, raw, "INVALID"
    return None, raw, "UNRECOGNIZED"
