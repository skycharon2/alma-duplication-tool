"""Classify an Archive ``antenna_arrays`` value into an ALMA array family.

The live TAP_SCHEMA describes ``antenna_arrays`` as a "Blank-separated list of
Pad:Antenna pairs" (for example ``A109:DV09 J504:DV02``). A 2026-09-10 census
found no row using the literal labels ``12-m``/``7-m`` that the first spatial
selectors expected, so those selectors never resolved an array on real data.

Rules (method ``array_family_1``):

* any antenna on a ``T`` pad (T701-T704) acts as a Total Power antenna;
* otherwise ``CM`` antennas are 7-m ACA dishes;
* otherwise ``DA``/``DV``/``PM`` antennas are 12-m main-array dishes
  (``PM`` antennas are regularly correlated in the 12-m array);
* the row family is the dominant family only when it holds at least
  ``DOMINANT_FAMILY_MIN_FRACTION`` of all tokens, unrecognized tokens included;
  anything less is ``MIXED`` and resolves no diameter.

Validation on 2026-09-11: 1,192 live rows (10 arcsec around CASE1/CASE2) whose
Member OUS carries a single ALMA Archive Query (AQ) ``array`` label. With these
exact rules, 1,175 rows were classified and all 1,175 agreed with the AQ label;
the remaining 17 were MIXED (no diameter). This is sample-supported,
application-derived evidence, not an authoritative Archive classification.

The legacy literal labels (``12-m``, ``7-m``, ``TP``) are still accepted so
older fixtures keep their meaning; they are reported with basis LEGACY_LABEL.
The function never raises.
"""
from __future__ import annotations

import re
from collections import Counter

from alma_duplicate.domain.array_classification import (
    ArrayClassification,
    ArrayClassificationBasis as B,
    ArrayFamily as F,
)

DOMINANT_FAMILY_MIN_FRACTION = 0.9

_TOKEN = re.compile(r"^([A-Z]+)(\d+):([A-Z]+)(\d+)$")
_LEGACY = {
    "12-m": F.MAIN_ARRAY_12M,
    "7-m": F.ACA_7M,
    "TP": F.TOTAL_POWER,
}
_ANTENNA_FAMILY = {
    "DA": F.MAIN_ARRAY_12M,
    "DV": F.MAIN_ARRAY_12M,
    "PM": F.MAIN_ARRAY_12M,
    "CM": F.ACA_7M,
}


def _text(value) -> str | None:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(value, str):
        return None
    return value.strip()


def _token_family(token: str) -> F | None:
    match = _TOKEN.match(token)
    if match is None:
        return None
    pad_prefix, _, antenna_prefix, _ = match.groups()
    if pad_prefix == "T":
        return F.TOTAL_POWER
    return _ANTENNA_FAMILY.get(antenna_prefix)


def classify_array_type(antenna_arrays_raw: object) -> ArrayClassification:
    """Return array-family evidence; unknown or mixed input never gains a diameter."""
    text = _text(antenna_arrays_raw)
    if text is None and antenna_arrays_raw is not None:
        return ArrayClassification(antenna_arrays_raw, F.UNRECOGNIZED, B.NONE, 0, (), None, (),
                                   ("ARRAY_VALUE_NOT_TEXT",))
    if not text:
        return ArrayClassification(antenna_arrays_raw, F.MISSING, B.NONE, 0, (), None, (),
                                   ("ARRAY_VALUE_MISSING",))
    if text in _LEGACY:
        return ArrayClassification(antenna_arrays_raw, _LEGACY[text], B.LEGACY_LABEL, 0, (), None,
                                   (), ("LEGACY_ARRAY_LABEL",))
    tokens = text.split()
    counts: Counter[F] = Counter()
    unrecognized = []
    for token in tokens:
        family = _token_family(token)
        if family is None:
            unrecognized.append(token)
        else:
            counts[family] += 1
    family_counts = tuple(sorted((family.value, n) for family, n in counts.items()))
    if not counts:
        return ArrayClassification(antenna_arrays_raw, F.UNRECOGNIZED, B.NONE, len(tokens),
                                   family_counts, None, tuple(unrecognized),
                                   ("NO_RECOGNIZED_PAD_ANTENNA_TOKEN",))
    # Deterministic tie-break by name; a tie can never reach the threshold anyway.
    dominant, dominant_count = sorted(counts.items(), key=lambda item: (-item[1], item[0].value))[0]
    fraction = dominant_count / len(tokens)
    reasons = ["UNRECOGNIZED_TOKENS_PRESENT"] if unrecognized else []
    if fraction < DOMINANT_FAMILY_MIN_FRACTION:
        reasons.append("NO_DOMINANT_ARRAY_FAMILY")
        family = F.MIXED
    else:
        family = dominant
    return ArrayClassification(antenna_arrays_raw, family, B.PAD_ANTENNA_MAJORITY, len(tokens),
                               family_counts, fraction, tuple(unrecognized), tuple(reasons))
