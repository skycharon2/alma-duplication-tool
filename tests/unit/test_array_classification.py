"""Array-family evidence from real antenna_arrays values; never a policy result."""
import pytest

from alma_duplicate.domain.array_classification import ArrayClassificationBasis as B, ArrayFamily as F
from alma_duplicate.parsers.array_classification import (
    DOMINANT_FAMILY_MIN_FRACTION,
    classify_array_type,
)

# Live TAP values retrieved 2026-09-11 (CASE1 neighbourhood, ivoa.obscore).
CASE1_12M = (
    "A007:DV04 A008:DA52 A011:DV25 A015:DV21 A016:DA64 A022:DV02 A023:DA63 A024:DV10 "
    "A027:DV03 A033:DV01 A035:DA61 A042:DA60 A043:DA55 A044:DA44 A045:DA58 A047:DA42 "
    "A048:DV19 A049:DA47 A058:DV12 A060:DV20 A062:DA65 A066:DA62 A068:DA54 A070:DA48 "
    "A072:DA53 A073:DA43 A074:DA56 A075:DV09 A076:DA50 A082:DA41 A083:DV22 A086:DV13 "
    "A087:DV05 A088:DV11 A089:DV23 A090:DV17 A091:DV14 A092:DV18 A093:DV07 A094:DV16 "
    "A096:DA45 A097:DV24 A101:DV15 A104:DA57 A105:DA46 A111:DV08"
)
ACA_7M = "J502:CM02 J503:CM03 J504:CM12 N602:CM01 N603:CM09 N604:CM11 N605:CM04 N606:CM06"
# PM antenna correlated on an A pad inside a 12-m array (2011.0.00405.S row).
MAIN_WITH_PM = ("A003:DA41 A011:DV12 A025:DV14 A037:PM01 A045:DV11 A046:DV09 A053:DV18 A069:DV16 "
                "A071:DV10 A072:DV13 A074:DV15 A075:DA43 A076:DV07 A082:DV05 A137:DV03 A138:DV17")
# Weekly report Week 1, LMC example (2025.1.00342.S): Total Power.
TOTAL_POWER = "T701:PM04 T702:PM03 T703:PM01 T704:PM02"
# Modelled on a 2012.1.00635.S calibrator row: mostly 12-m, plus 8 ACA and
# 4 T-pad antennas (56/68 = 0.82 < 0.9) -> no dominant family.
MIXED_ROW = " ".join(
    [f"A{i:03d}:DV{i:02d}" for i in range(1, 57)]
    + [f"J50{i}:CM0{i}" for i in range(1, 9)]
    + ["T701:PM03", "T702:DA62", "T703:PM04", "T704:PM01"]
)


@pytest.mark.parametrize("raw,family,diameter", [
    (CASE1_12M, F.MAIN_ARRAY_12M, 12.0),
    (ACA_7M, F.ACA_7M, 7.0),
    (MAIN_WITH_PM, F.MAIN_ARRAY_12M, 12.0),
    (TOTAL_POWER, F.TOTAL_POWER, None),
    (MIXED_ROW, F.MIXED, None),
    (CASE1_12M.encode(), F.MAIN_ARRAY_12M, 12.0),
    ("  " + ACA_7M + "  ", F.ACA_7M, 7.0),
])
def test_real_pad_antenna_lists(raw, family, diameter):
    result = classify_array_type(raw)
    assert result.family is family
    assert result.interferometric_diameter_m == diameter
    assert result.basis is B.PAD_ANTENNA_MAJORITY
    assert result.raw_value is raw
    assert result.evidence_level == "application-derived"
    assert result.method_version == "array_family_1"


def test_main_array_with_a_few_total_power_pads_stays_main_array():
    raw = CASE1_12M + " T701:PM03 T703:PM04"
    result = classify_array_type(raw)
    assert result.family is F.MAIN_ARRAY_12M
    assert dict(result.family_counts) == {"MAIN_ARRAY_12M": 46, "TOTAL_POWER": 2}
    assert result.dominant_fraction == pytest.approx(46 / 48)


def test_dominance_threshold_is_inclusive_and_counts_unrecognized_tokens():
    nine_main = " ".join(f"A{i:03d}:DA{i:02d}" for i in range(1, 10))
    assert classify_array_type(nine_main + " J501:CM01").family is F.MAIN_ARRAY_12M
    assert DOMINANT_FAMILY_MIN_FRACTION == 0.9
    eight_main = " ".join(f"A{i:03d}:DA{i:02d}" for i in range(1, 9))
    result = classify_array_type(eight_main + " J501:CM01 J502:CM02")
    assert result.family is F.MIXED
    assert "NO_DOMINANT_ARRAY_FAMILY" in result.reasons
    noisy = classify_array_type(eight_main + " garbage X1:ZZ9")
    assert noisy.family is F.MIXED
    assert noisy.unrecognized_tokens == ("garbage", "X1:ZZ9")
    assert "UNRECOGNIZED_TOKENS_PRESENT" in noisy.reasons


@pytest.mark.parametrize("raw,family,basis", [
    ("12-m", F.MAIN_ARRAY_12M, B.LEGACY_LABEL),
    ("7-m", F.ACA_7M, B.LEGACY_LABEL),
    ("TP", F.TOTAL_POWER, B.LEGACY_LABEL),
    ("12-m 7-m", F.UNRECOGNIZED, B.NONE),
    ("unrecognized", F.UNRECOGNIZED, B.NONE),
    ("12m", F.UNRECOGNIZED, B.NONE),
    ("", F.MISSING, B.NONE),
    ("   ", F.MISSING, B.NONE),
    (None, F.MISSING, B.NONE),
    (b"\xff\xfe", F.UNRECOGNIZED, B.NONE),
    (12, F.UNRECOGNIZED, B.NONE),
])
def test_legacy_missing_and_unrecognized_values_never_guess(raw, family, basis):
    result = classify_array_type(raw)
    assert result.family is family
    assert result.basis is basis
    if family is not F.MAIN_ARRAY_12M and family is not F.ACA_7M:
        assert result.interferometric_diameter_m is None
