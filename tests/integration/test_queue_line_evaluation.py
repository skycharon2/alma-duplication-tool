"""Formal Queue LINE numerical evaluation and same-pair aggregation acceptance."""

import json
from pathlib import Path

from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.model import (
    CriterionOutcome as O,
    CriterionResult,
    EvaluationStatus as E,
    MethodApplicability as A,
    MethodApproval,
)
from alma_duplicate.rules.queue_line import evaluate_queue_line
from tests.integration.test_queue_line_pairing import contexts

ROOT = Path(__file__).parents[2]


def request(*, center_ghz=222.0, resolution_kms=2.0, setup_complete=True):
    payload = json.loads((ROOT / "examples/confirmed_line/request.json").read_text())
    payload["request"]["setup_complete"] = setup_complete
    payload["request"]["spectral_windows"][0]["center"] = {
        "value": center_ghz,
        "unit": "GHz",
        "kind": "SKY",
        "frame": "UNKNOWN",
    }
    payload["request"]["sensitivities"][0]["smoothing_resolution"] = {
        "value": resolution_kms,
        "unit": "km/s",
    }
    result = validate_proposed_observation(payload["request"], payload["search_options"])
    assert result.is_valid and result.request is not None, result.issues
    return result.request


def common(context):
    def result(name, method):
        return CriterionResult(
            criterion_id=name,
            policy_ref="test common Queue scope",
            method_version=method,
            approval=MethodApproval.APPROVED,
            applicability=A.APPLICABLE,
            evaluation=E.EVALUATED,
            outcome=O.SATISFIED,
            context_id=context.context_id,
            proposed=None,
            candidate=None,
            details=(("common_scope", "SUPPORTED"),),
            decision_refs=("tests:queue-common",),
        )

    return (
        result("ANGULAR", "queue_angular_factor_7"),
        result("POS-SINGLE", "queue_pos_single_5"),
    )


def criteria(pair):
    return {r.criterion_id: r for r in pair.criteria}


def test_cross_spw_borrowing_cannot_create_a_pass():
    # SPW1 covers 222 GHz but is a known TDM setup. SPW4 is a known FDM
    # setup with adequate spectral resolution, but is centred at 228 GHz and
    # therefore does not cover the proposed line. No condition may be borrowed
    # across those two SPWs to synthesize a passing pair.
    context = contexts({"Spec.Res. SPW 1": "31.25"})[0]
    pairing, pairs, branch = evaluate_queue_line(request(), context, common(context))
    assert pairing.candidate_enumeration_complete
    by_spw = {p.attempt.reference.spw_number: p for p in pairs}

    a = criteria(by_spw[1])
    assert a["LINE-COVERAGE"].outcome is O.SATISFIED
    assert a["LINE-FDM"].outcome is O.NOT_SATISFIED

    b = criteria(by_spw[4])
    assert b["LINE-FDM"].outcome is O.SATISFIED
    assert b["LINE-COVERAGE"].outcome is O.NOT_SATISFIED
    assert b["LINE-RESOLUTION-COMPATIBILITY"].outcome is O.SATISFIED

    assert not any(p.truth is Truth.TRUE for p in pairs)
    assert branch.truth is Truth.FALSE
    assert branch.status == "CRITERIA_NOT_MET"


def test_incomplete_proposed_enumeration_prevents_negative_context_result():
    context = contexts({"Spec.Res. SPW 1": "7.8125"})[0]
    _, pairs, branch = evaluate_queue_line(
        request(setup_complete=False), context, common(context)
    )
    assert not any(p.truth is Truth.TRUE for p in pairs)
    assert branch.truth is Truth.UNKNOWN
    assert branch.status == "INDETERMINATE"
    assert "PROPOSED_ENUMERATION_INCOMPLETE" in branch.reasons


def test_queue_line_rms_does_not_require_positive_reference_frequency():
    context = contexts({"Ref.Frequency": "0", "Spec.Res. SPW 1": "0.9765625"})[0]
    _, pairs, _ = evaluate_queue_line(request(resolution_kms=20.0), context, common(context))
    first = criteria(next(p for p in pairs if p.attempt.reference.spw_number == 1))
    assert "QUEUE_REFERENCE_FREQUENCY_UNRESOLVED" not in first["LINE-RMS"].reasons
