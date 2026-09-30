"""Explicit researcher evidence, independent of intent and window completeness."""

from dataclasses import replace

import pytest

from alma_duplicate.domain.proposed_observation import CONTINUUM_SETUP_DECLARATION as DECLARATION
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.confirmed import approve_setup
from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup, PORTAL_SCRIPT_V1
from alma_duplicate.rules.aggregation import criterion_truth, Truth
from tests.unit.test_rules_continuum_setup import request, window


def declared(windows=(), complete=False):
    return replace(request(windows, complete=complete), continuum_setup_declaration=DECLARATION)


def test_explicit_declaration_can_qualify_without_windows():
    r = evaluate_continuum_setup(declared())
    assert r.outcome == "SATISFIED"
    assert criterion_truth(r) is Truth.TRUE
    assert r.method_version == "continuum_setup_declaration_1"
    assert dict(r.details)["evidence_basis"] == "USER_DECLARED"
    assert dict(r.derived)["evidenced_qualifying_windows"] == 0
    assert not r.issues
    assert r.decision_refs == ("docs/continuum_setup_declaration.md",)
    assert approve_setup(r, nominal_conversion=None) == r
    assert approve_setup(r, nominal_conversion=PORTAL_SCRIPT_V1) == r


@pytest.mark.parametrize("windows", [
    [], [window("a", 1.875)],
    [window("a", 1.8), window("b", 1.875)],
    [window("a", 0.5, kind="NOMINAL"), window("b", None)],
])
def test_complete_list_that_cannot_contain_two_qualifiers_conflicts(windows):
    r = evaluate_continuum_setup(declared(windows, complete=True))
    assert r.outcome is None and criterion_truth(r) is Truth.UNKNOWN
    assert r.reasons == ("CONTINUUM_SETUP_DECLARATION_CONFLICT",)
    assert r.issues[0].path == "request.continuum_setup_declaration"
    assert r.issues[0].code == "CONFLICTING_EVIDENCE"


@pytest.mark.parametrize("windows,complete", [
    ([window("a", 0.5)], False),
    ([window("a", None), window("b", None)], True),
    ([window("a", 2, kind="NOMINAL"), window("b", 2, kind="NOMINAL")], True),
    ([window("a", 1.875), window("b", 1.875)], True),
])
def test_absence_of_detail_is_not_a_contradiction(windows, complete):
    r = evaluate_continuum_setup(declared(windows, complete))
    assert r.outcome == "SATISFIED"
    assert evaluate_continuum_setup(declared(windows, complete), nominal_conversion=PORTAL_SCRIPT_V1) == r


def test_no_declaration_keeps_original_methods_and_outcomes():
    r = evaluate_continuum_setup(request([], complete=False))
    assert r.outcome is None and r.method_version == "continuum_setup_2"
    assert approve_setup(r, nominal_conversion=None).method_version == "continuum_setup_3"


@pytest.mark.parametrize("value", [True, False, 1, "CONTINUUM", "", {}, []])
def test_generic_boolean_or_intent_is_not_a_valid_declaration(value):
    payload = dict(request([], complete=False).raw_input)
    payload["continuum_setup_declaration"] = value
    v = validate_proposed_observation(payload)
    assert not v.is_valid
    assert any(i.path == "request.continuum_setup_declaration" for i in v.errors)


def test_validator_preserves_statement_and_other_missing_evidence():
    payload = dict(request([], complete=False).raw_input)
    payload["continuum_setup_declaration"] = DECLARATION
    v = validate_proposed_observation(payload)
    assert v.is_valid
    assert v.validation_version == "7" and v.request.model_version == "3"
    assert v.request.continuum_setup_declaration == DECLARATION
    assert any(i.code == "CONTINUUM_SETUP_USER_DECLARED" and i.category == "EVIDENCE" for i in v.issues)
    assert not any(i.rule_id == "CONT-SETUP" and i.category == "MISSING" for i in v.issues)
    assert {"CONT-FREQ", "CONT-RMS"} <= {i.rule_id for i in v.issues if i.category == "MISSING"}


def test_invalid_supplied_width_is_not_overridden_by_declaration():
    payload = dict(request([], complete=False).raw_input)
    payload.update(continuum_setup_declaration=DECLARATION, spectral_windows=[window("a", -1)])
    assert not validate_proposed_observation(payload).is_valid
