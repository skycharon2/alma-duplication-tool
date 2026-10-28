"""Independent REST conversion for submitted LINE requirements."""
from copy import deepcopy

import pytest

from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
from tests.integration.test_submitted_line_context_evaluation_step04b import _wire, _evaluate
from tests.integration.test_submitted_line_assessment_step04c import _single


def request(geometry="SINGLE_POINTING"):
    document = _wire("450.2", geometry=geometry)
    raw = document["request"]
    raw["source_redshift"] = 9
    first = raw["line_requirements"][0]
    first["window_center"]["kind"] = "REST"
    first["source_redshift"] = 1
    second = deepcopy(first)
    second.update(requirement_id="line-b", source_redshift=0)
    raw["line_requirements"].append(second)
    return document


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
def test_independent_redshifts_reach_real_pair_evaluation(geometry):
    document = request(geometry)
    original = deepcopy(document)
    result = _evaluate(document, mosaic=geometry == "MOSAIC")
    assert [p.truth for p in result.result.pairs] == [Truth.TRUE, Truth.FALSE]
    assert result.result.branch.truth is Truth.TRUE
    assert document == original


def test_report_preserves_each_redshift_and_pair_result():
    document = request()
    report = _single(document)
    assert report["request"]["raw"] == document["request"]
    pairs = report["context_evaluations"][0]["line_pairs"]
    assert [p["truth"] for p in pairs] == ["TRUE", "FALSE"]


def test_shared_fallback_and_sky_are_not_double_converted():
    document = request()
    raw = document["request"]
    raw["source_redshift"] = 1
    del raw["line_requirements"][0]["source_redshift"]
    second = raw["line_requirements"][1]
    second["window_center"].update(kind="SKY", value="225.1")
    second["source_redshift"] = 10
    prepared = prepare_submitted_line_request(raw).line_request
    values = [prepare_line_window(w, prepared.sensitivities, prepared.source_redshift)
              .sky_frequency_ghz_exact for w in prepared.spectral_windows]
    assert values == ["2251/10", "2251/10"]


@pytest.mark.parametrize("value", [None, True, -1, -2, "nan", "inf", {}, []])
def test_invalid_local_redshift_cannot_fall_back_to_shared(value):
    document = request()
    document["request"]["line_requirements"][0]["source_redshift"] = value
    with pytest.raises(ValueError):
        prepare_submitted_line_request(document["request"])
