"""CONT-SETUP against the acceptance table in docs/evidence/scientific_feedback.md."""
import pytest

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules import CriterionOutcome as O, EvidenceSide, evaluate_continuum_setup
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
    ([window("a", 1.875), window("b", None, center=102)], True, O.INSUFFICIENT_INFORMATION),
    ([window("a", 0.9375), window("b", 0.9375, center=102)], False, O.INSUFFICIENT_INFORMATION),
    ([window("a", 1.875), window("b", 0.9375, center=102)], True, O.NOT_SATISFIED),
    ([], True, O.NOT_SATISFIED),
    ([], False, O.INSUFFICIENT_INFORMATION),
])
def test_prepared_acceptance_table(windows, complete, outcome):
    result = evaluate_continuum_setup(request(windows, complete=complete))
    assert result.outcome is outcome
    assert result.criterion_id == "CONT-SETUP"
    assert result.context_id is None
    if outcome is O.INSUFFICIENT_INFORMATION:
        assert result.missing_side is EvidenceSide.PROPOSED
        assert not result.is_definite


def test_nominal_widths_are_unresolved_without_an_approved_conversion():
    windows = [window("a", 2.0, kind="NOMINAL"), window("b", 2.0, kind="NOMINAL", center=102)]
    result = evaluate_continuum_setup(request(windows))
    assert result.outcome is O.INSUFFICIENT_INFORMATION
    assert "WINDOW_WIDTH_UNRESOLVED" in result.reasons
    converted = evaluate_continuum_setup(request(windows), nominal_conversion=PORTAL_SCRIPT_V1)
    assert converted.outcome is O.SATISFIED
    assert "nominal-conversion:PORTAL_SCRIPT_V1" in converted.decision_refs
    assert dict(converted.details)["a"] == "QUALIFIED:NOMINAL_2_GHZ_PORTAL_USABLE_1.875_GHZ"


@pytest.mark.parametrize("kind", ["NOMINAL", "UNKNOWN"])
def test_narrow_nominal_or_unknown_width_bounds_the_usable_width(kind):
    windows = [window("a", 1.0, kind=kind), window("b", 0.5, kind=kind, center=102)]
    result = evaluate_continuum_setup(request(windows))
    assert result.outcome is O.NOT_SATISFIED
    assert all(v.startswith("NOT_QUALIFIED:") for _, v in result.details)


def test_unknown_kind_wide_window_is_unresolved():
    windows = [window("a", 1.875, kind="UNKNOWN"), window("b", 1.875, kind="UNKNOWN", center=102)]
    assert evaluate_continuum_setup(request(windows)).outcome is O.INSUFFICIENT_INFORMATION


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
