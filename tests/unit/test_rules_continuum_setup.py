"""CONT-SETUP against the acceptance table in docs/evidence/scientific_feedback.md."""
import pytest

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules import CriterionOutcome as O, EvaluationStatus as E, EvidenceSide, evaluate_continuum_setup
from alma_duplicate.rules.continuum_setup import PORTAL_SCRIPT_V1, qualify_window


def window(window_id, width, unit="GHz", kind="USABLE", center=100.0):
    item = {"window_id": window_id, "representation": "CENTER_BANDWIDTH",
            "center": {"value": center, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN"},
            "bandwidth_kind": kind}
    if width is not None:
        item["bandwidth"] = {"value": width, "unit": unit}
    return item


def request(windows, *, complete=True, intents=("CONTINUUM",)):
    payload = {
        "target_kind": "FIXED", "geometry": "SINGLE_POINTING",
        "position": {"ra": "12:00:00", "dec": "-00:30:00", "ra_format": "HMS",
                     "dec_format": "DMS", "frame": "ICRS"},
        "setup_id": "s1", "setup_complete": complete, "intents": list(intents),
        "spectral_windows": windows,
    }
    validation = validate_proposed_observation(payload)
    assert validation.is_valid, validation.errors
    return validation.request


# Rows of the prepared acceptance table (usable widths).
@pytest.mark.parametrize("windows,complete,outcome", [
    ([window("a", 1.8001), window("b", 1.8001, center=102)], True, O.SATISFIED),
    ([window("a", 1.8), window("b", 1.9, center=102)], True, O.NOT_SATISFIED),
    ([window("a", 1800.1, "MHz"), window("b", 1800.1, "MHz", center=102)], True, O.SATISFIED),
    ([window("a", 1800, "MHz"), window("b", 1900, "MHz", center=102)], True, O.NOT_SATISFIED),
    ([window("a", 1.875), window("b", 1.875, center=102)], False, O.SATISFIED),
    ([window("a", 1.875), window("b", None, center=102)], True, None),
    ([window("a", 0.9375), window("b", 0.9375, center=102)], False, None),
    ([window("a", 1.875), window("b", 0.9375, center=102)], True, O.NOT_SATISFIED),
    ([], True, O.NOT_SATISFIED),
    ([], False, None),
])
def test_prepared_acceptance_table(windows, complete, outcome):
    result = evaluate_continuum_setup(request(windows, complete=complete))
    assert result.outcome is outcome
    assert result.criterion_id == "CONT-SETUP"
    assert result.context_id is None
    if outcome is None:
        assert result.issue_sides == (EvidenceSide.PROPOSED,)
        assert result.evaluation is E.INSUFFICIENT_INFORMATION
        assert not result.has_computed_outcome


def test_nominal_widths_are_unresolved_without_an_approved_conversion():
    windows = [window("a", 2.0, kind="NOMINAL"), window("b", 2.0, kind="NOMINAL", center=102)]
    result = evaluate_continuum_setup(request(windows))
    assert result.outcome is None
    assert "WINDOW_WIDTH_UNRESOLVED" in result.reasons
    converted = evaluate_continuum_setup(request(windows), nominal_conversion=PORTAL_SCRIPT_V1)
    assert converted.outcome is O.SATISFIED
    assert "nominal-conversion:PORTAL_SCRIPT_V1" in converted.decision_refs
    assert dict(converted.details)["a"] == "QUALIFIED:NOMINAL_2_GHZ_PORTAL_USABLE_1.875_GHZ"


@pytest.mark.parametrize("kind", ["NOMINAL", "UNKNOWN"])
def test_only_narrow_nominal_width_bounds_the_usable_width(kind):
    windows = [window("a", 1.0, kind=kind), window("b", 0.5, kind=kind, center=102)]
    result = evaluate_continuum_setup(request(windows))
    assert result.outcome is (O.NOT_SATISFIED if kind == "NOMINAL" else None)
    if kind == "UNKNOWN":
        return
    assert all(v.startswith("NOT_QUALIFIED:") for _, v in result.details)


def test_unknown_kind_wide_window_is_unresolved():
    windows = [window("a", 1.875, kind="UNKNOWN"), window("b", 1.875, kind="UNKNOWN", center=102)]
    assert evaluate_continuum_setup(request(windows)).outcome is None


def test_intents_never_decide():
    windows = [window("a", 1.875), window("b", 1.875, center=102)]
    assert evaluate_continuum_setup(request(windows, intents=("LINE",))).outcome is O.SATISFIED
    narrow = [window("a", 0.5), window("b", 0.5, center=102)]
    assert evaluate_continuum_setup(request(narrow, intents=("CONTINUUM",))).outcome is O.NOT_SATISFIED


def test_bounds_representation_uses_its_span():
    bounds = {"window_id": "a", "representation": "BOUNDS", "bandwidth_kind": "USABLE",
              "lower": {"value": 100.0, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN"},
              "upper": {"value": 101.875, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN"}}
    status, _ = qualify_window(request([bounds]).spectral_windows[0])
    assert status == "QUALIFIED"


def test_unknown_conversion_name_is_rejected():
    with pytest.raises(ValueError):
        evaluate_continuum_setup(request([]), nominal_conversion="GUESS")


def bounds(window_id, lower, upper, kind="USABLE"):
    return {"window_id": window_id, "representation": "BOUNDS", "bandwidth_kind": kind,
            "lower": {"value": lower, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN"},
            "upper": {"value": upper, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN"}}


# Endpoint pairs whose exact decimal difference is the same width. Float
# subtraction of these pairs straddles the strict threshold in both directions.
@pytest.mark.parametrize("lower,upper", [
    (98.6, 100.4), (100.0, 101.8), (102.6, 104.4), (215.0, 216.8),
])
def test_threshold_width_from_bounds_matches_the_declared_width(lower, upper):
    width = upper - lower
    assert width != 1.8, "endpoints chosen for their float error"
    derived = request([bounds("a", lower, upper)]).spectral_windows[0]
    assert derived.interval.span_ghz == 1.8
    declared = request([window("a", 1.8)]).spectral_windows[0]
    assert qualify_window(derived) == qualify_window(declared)
    assert qualify_window(derived)[0] == "NOT_QUALIFIED"


def test_width_above_threshold_still_qualifies_from_bounds():
    derived = request([bounds("a", 98.6, 100.4001)]).spectral_windows[0]
    assert derived.interval.span_ghz == 1.8001
    assert qualify_window(derived)[0] == "QUALIFIED"


def test_center_bandwidth_interval_spans_its_declared_width():
    derived = request([window("a", 1.8, kind="NOMINAL", center=99.5)]).spectral_windows[0]
    assert derived.interval.span_ghz == 1.8
    assert derived.interval.midpoint_ghz == 99.5
