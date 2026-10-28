"""Step 03b-A: separate scientific inputs; no premature new-form verdicts."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from alma_duplicate.assessment import (
    AssessmentSources, AssessmentStatus, assess_observation,
)
from alma_duplicate.domain.proposed_observation import LINE_SCOPE_LEGACY
from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.request_validation import _Validator, validate_proposed_observation
from alma_duplicate.rules.continuum_setup import (
    NOT_QUALIFIED, QUALIFIED, qualify_window, evaluate_continuum_setup,
)
from alma_duplicate.separated_setup_input import (
    SEPARATED_INPUT_CONTRACT, parse_separated_setup,
)
from tests.integration.test_line_evaluation import sky_request
from tests.integration.test_line_preparation import payload


def new_wire():
    document = deepcopy(payload())
    request = document["request"]
    for key in ("spectral_windows", "sensitivities", "setup_complete"):
        request.pop(key, None)
    request.update({
        "line_input_contract": SEPARATED_INPUT_CONTRACT,
        "line_requirements": [{
            "requirement_id": "line-a",
            "window_center": {"value": "225.1", "unit": "GHz", "kind": "SKY"},
            "correlator_mode": "FDM",
            "spectral_resolution": {"value": "20", "unit": "km/s"},
            "rms": {"value": "0.3", "unit": "mJy/beam"},
        }],
        "physical_spw_evidence": [{
            "spw_id": "physical-a", "linked_line_requirement_id": "line-a",
            "center": {"value": "225.1", "unit": "GHz", "kind": "SKY"},
            "bandwidth": {"value": "1875", "unit": "MHz"},
            "bandwidth_kind": "USABLE",
        }, {
            "spw_id": "physical-b",
            "center": {"value": "225.1", "unit": "GHz", "kind": "SKY"},
            "bandwidth": {"value": "1800", "unit": "MHz"},
            "bandwidth_kind": "USABLE",
        }],
        "physical_spw_inventory_complete": False,
    })
    return document


def parsed(wire):
    validator = _Validator()
    detached = validator.snapshot(wire["request"], "request")
    result = parse_separated_setup(validator, detached)
    return result, tuple(validator.issues)


def errors(document):
    result = validate_proposed_observation(document["request"], document["search_options"])
    assert not result.is_valid and not result.can_search
    assert result.request is None and result.search_options is None
    return {(issue.code, issue.path) for issue in result.errors}


def test_typed_operands_are_independent_and_never_clone_bandwidth():
    document = new_wire()
    adapted, issues = parsed(document)
    assert not any(i.category == "ERROR" for i in issues), issues
    assert [w.window_id for w in adapted.line_windows] == ["line-a"]
    assert [w.window_id for w in adapted.continuum_window_evidence] == ["physical-a", "physical-b"]
    assert len(adapted.line_sensitivities) == 1
    assert adapted.line_windows[0].bandwidth is None
    assert adapted.physical_links[0].line_requirement_id == "line-a"
    assert adapted.physical_links[1].line_requirement_id is None
    assert [qualify_window(w)[0] for w in adapted.continuum_window_evidence] == [
        QUALIFIED, NOT_QUALIFIED,
    ]
    windows, sensitivities = adapted.line_comparison_operands
    planned = prepare_line_window(windows[0], sensitivities, None)
    assert planned.sky_frequency_ghz_exact is not None
    assert planned.planned_resolution_kms_exact is not None
    assert adapted.physical_inventory_complete is False


def test_second_explicit_line_requirement_without_rms_is_rejected():
    document = new_wire()
    document["request"]["line_requirements"].append({
        "requirement_id": "line-b",
        "window_center": {"value": "230", "unit": "GHz", "kind": "SKY"},
        "correlator_mode": "FDM",
        "spectral_resolution": {"value": "20", "unit": "km/s"},
    })
    assert ("LINE_RMS_REQUIRED", "request.line_requirements[1].rms") in errors(document)


def test_continuum_only_new_contract_still_uses_physical_port_but_cannot_run():
    document = new_wire()
    request = document["request"]
    request["intents"] = ["CONTINUUM"]
    request["line_requirements"] = []
    request["physical_spw_evidence"][0].pop("linked_line_requirement_id")
    adapter, issues = parsed(document)
    assert not any(i.category == "ERROR" for i in issues)
    assert adapter.line_windows == ()
    assert len(adapter.continuum_window_evidence) == 2
    assert "SEPARATED_INPUT_NOT_EXECUTABLE" in {c for c, _ in errors(document)}


def test_physical_inventory_true_never_authorizes_a_new_line_verdict():
    document = new_wire()
    document["request"]["physical_spw_inventory_complete"] = True
    adapted, issues = parsed(document)
    assert not any(i.category == "ERROR" for i in issues)
    assert adapted.physical_inventory_complete is True
    assert ("SEPARATED_INPUT_NOT_EXECUTABLE", "request.line_input_contract") in errors(document)
    assert "setup_complete" not in document["request"]


def test_duplicate_physical_frequencies_do_not_merge_window_identity():
    document = new_wire()
    physical = document["request"]["physical_spw_evidence"]
    physical[1]["bandwidth"]["value"] = "1875"
    adapted, issues = parsed(document)
    assert not any(i.category == "ERROR" for i in issues)
    assert len(adapted.continuum_window_evidence) == 2
    assert [w.window_id for w in adapted.continuum_window_evidence] == ["physical-a", "physical-b"]
    assert [qualify_window(w)[0] for w in adapted.continuum_window_evidence] == [QUALIFIED, QUALIFIED]


@pytest.mark.parametrize("change,code", [
    (lambda r: r["line_requirements"].append(deepcopy(r["line_requirements"][0])), "DUPLICATE_ID"),
    (lambda r: r["physical_spw_evidence"].append(deepcopy(r["physical_spw_evidence"][0])), "DUPLICATE_ID"),
    (lambda r: r["physical_spw_evidence"][0].update(linked_line_requirement_id="missing"), "DANGLING_REFERENCE"),
    (lambda r: r["physical_spw_evidence"][1].update(linked_line_requirement_id="line-a"), "AMBIGUOUS_PHYSICAL_SPW_LINK"),
    (lambda r: r.update(setup_complete=False), "MIXED_INPUT_CONTRACTS"),
    (lambda r: r.update(spectral_windows=[]), "MIXED_INPUT_CONTRACTS"),
    (lambda r: r.update(sensitivities=[]), "MIXED_INPUT_CONTRACTS"),
    (lambda r: r.update(line_evaluation_scope=LINE_SCOPE_LEGACY), "MIXED_INPUT_CONTRACTS"),
    (lambda r: r.update(physical_spw_inventory_complete="on"), "INVALID_TYPE"),
    (lambda r: r.pop("physical_spw_inventory_complete"), "REQUIRED_FIELD"),
    (lambda r: r["line_requirements"][0].update(validated=True), "UNKNOWN_FIELD"),
    (lambda r: r["physical_spw_evidence"][0].update(validated=True), "UNKNOWN_FIELD"),
    (lambda r: r["line_requirements"][0].pop("rms"), "LINE_RMS_REQUIRED"),
    (lambda r: r["line_requirements"][0].update(correlator_mode="UNKNOWN"), "INVALID_CHOICE"),
    (lambda r: r["physical_spw_evidence"][0].pop("bandwidth_kind"), "BANDWIDTH_KIND_REQUIRED"),
    (lambda r: r.update(line_input_contract="UNKNOWN"), "INVALID_CHOICE"),
])
def test_invalid_or_mixed_new_contract_is_rejected(change, code):
    document = new_wire()
    change(document["request"])
    assert code in {c for c, _ in errors(document)}


def test_new_fields_without_contract_cannot_fall_back_to_legacy():
    document = new_wire()
    document["request"].pop("line_input_contract")
    assert "REQUIRED_FIELD" in {c for c, _ in errors(document)}


def test_no_new_line_requirements_when_line_intent_selected_is_invalid():
    document = new_wire()
    document["request"]["line_requirements"] = []
    document["request"]["physical_spw_evidence"][0].pop("linked_line_requirement_id")
    assert "LINE_REQUIREMENT_REQUIRED" in {c for c, _ in errors(document)}


def test_new_contract_blocks_before_provider_for_single_and_mosaic():
    document = new_wire()
    def forbidden():
        pytest.fail("Archive provider must not be accessed")
    sources = AssessmentSources(archive_kind="LIVE", archive_provider=forbidden)
    for geometry, mosaic in (("SINGLE_POINTING", None), ("MOSAIC", SimpleNamespace())):
        document["request"]["geometry"] = geometry
        result = assess_observation(
            document["request"], document["search_options"],
            sources=sources, mosaic=mosaic,
        )
        assert result.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY
        assert result.document is None
        assert any(i.code == "SEPARATED_INPUT_NOT_EXECUTABLE" for i in result.validation.errors)


def test_direct_old_evaluators_cannot_be_given_separated_raw_contract():
    legacy = sky_request(225.134765625)
    old = validate_proposed_observation(legacy["request"], legacy["search_options"])
    assert old.is_valid
    redirected = replace(old.request, raw_input={
        **old.request.raw_input, "line_input_contract": SEPARATED_INPUT_CONTRACT,
    })
    with pytest.raises(ValueError, match="SEPARATED_INPUT_NOT_EXECUTABLE"):
        redirected.require_implemented_line_scope()
    with pytest.raises(ValueError, match="SEPARATED_INPUT_NOT_EXECUTABLE"):
        evaluate_continuum_setup(redirected)


def test_old_request_contract_and_serialization_stay_unchanged():
    from alma_duplicate.reporting import json_value
    legacy = sky_request(225.134765625)
    old = validate_proposed_observation(legacy["request"], legacy["search_options"])
    assert old.is_valid and old.can_search
    assert old.request.line_evaluation_scope == LINE_SCOPE_LEGACY
    result = json_value(old.request)
    for key in ("line_input_contract", "line_requirements", "physical_spw_evidence",
                "physical_spw_inventory_complete"):
        assert key not in result and key not in result["raw_input"]
