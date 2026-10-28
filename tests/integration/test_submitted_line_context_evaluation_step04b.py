"""Step 04B: real reference-bound six-criterion V2 context evaluation.

These are deliberately offline internal evaluations, NOT a new public report
or search-wide no-duplication decision. Existing endpoints stay fail-closed.
"""

from copy import deepcopy
from dataclasses import replace

import pytest

from alma_duplicate.assessment import AssessmentSources, AssessmentStatus, assess_observation
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.model import MethodApproval
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from alma_duplicate.rules.submitted_line_evaluation import (
    evaluate_submitted_line_context_v2, prepare_submitted_line_request,
)
from tests.integration.test_line_preparation import report as archive_report
from tests.integration.test_mosaic_scientific_acceptance import _line_case
from tests.integration.test_separated_setup_contract_step03ba import new_wire


def _wire(frequency="225.1", *, inventory=False, geometry="SINGLE_POINTING"):
    document = new_wire()
    raw = document["request"]
    raw["geometry"] = geometry
    raw["physical_spw_inventory_complete"] = inventory
    raw["line_requirements"][0]["window_center"]["value"] = frequency
    if geometry == "MOSAIC":
        raw["target_name"] = "proposed"
        raw["position"] = None
    return document


def _single_context():
    r = archive_report()
    item = r.context_evaluations[0]
    return item.candidate.context, item.criteria


def _mosaic_context():
    request, context, pointings, execution, array_evidence = _line_case()
    original = evaluate_mosaic_context(
        request, context, pointings, executions=[execution], array_evidence=array_evidence,
    )
    return context, original["criteria"][:2]


def _evaluate(document, *, mosaic=False, context=None, common=None):
    if context is None:
        context, common = _mosaic_context() if mosaic else _single_context()
    prepared = prepare_submitted_line_request(document["request"])
    return evaluate_submitted_line_context_v2(prepared, context, common)


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
@pytest.mark.parametrize("inventory", [False, True])
@pytest.mark.parametrize("frequency,expected", [("240", Truth.FALSE), ("225.1", Truth.TRUE)])
def test_reused_six_criteria_and_physical_inventory_independence(geometry, inventory, frequency, expected):
    document = _wire(frequency, inventory=inventory, geometry=geometry)
    result = _evaluate(document, mosaic=geometry == "MOSAIC")
    assert result.result.branch.truth is expected
    assert result.result.branch.method_version == "archive_line_context_submitted_or_2"
    assert result.result.branch.scope == "ONE_CANDIDATE_CONTEXT_SUBMITTED_LINE_REQUIREMENTS_ONLY"
    assert result.pairing.proposed_enumeration_complete is False
    assert result.pairing.builder_version == "archive_line_pair_builder_submitted_2"
    assert result.pairing.scope == "ONE_CONTEXT_SUBMITTED_LINE_REQUIREMENTS_ONLY"
    assert result.result.missing_requirement_ids == ()
    assert len(result.result.pairs) == 1
    pair = result.result.pairs[0]
    assert pair.method_version == "archive_line_pair_and_1"
    assert len(pair.criteria) == 6
    assert pair.attempt.reference is not None
    assert pair.attempt.reference.candidate_context_id == result.result.branch.context_id
    assert pair.attempt.proposed_window_id == "line-a"
    assert "PROPOSED_ENUMERATION_INCOMPLETE" not in result.result.branch.reasons
    if frequency == "240":
        assert next(c for c in pair.criteria if c.criterion_id == "LINE-COVERAGE").outcome == "NOT_SATISFIED"


def test_two_submitted_requirements_cannot_splice_criteria_and_do_not_use_physical_spws():
    document = _wire("240")
    raw = document["request"]
    raw["line_requirements"].append({
        "requirement_id": "line-b",
        "window_center": {"value": "225.1", "unit": "GHz", "kind": "SKY"},
        "correlator_mode": "FDM", "spectral_resolution": {"value": "20", "unit": "km/s"},
        "rms": {"value": "0.01", "unit": "mJy/beam"},
    })
    raw["physical_spw_evidence"].append({
        "spw_id": "unlinked-extra", "bandwidth": {"value": "2000", "unit": "MHz"},
        "bandwidth_kind": "USABLE",
    })
    failed = _evaluate(document)
    assert failed.result.submitted_requirement_ids == ("line-a", "line-b")
    assert len(failed.result.pairs) == 2
    assert [p.truth for p in failed.result.pairs] == [Truth.FALSE, Truth.FALSE]
    assert failed.result.branch.truth is Truth.FALSE
    first, second = failed.result.pairs
    first_rules = {r.criterion_id: r for r in first.criteria}
    second_rules = {r.criterion_id: r for r in second.criteria}
    assert first_rules["LINE-COVERAGE"].outcome == "NOT_SATISFIED"
    assert second_rules["LINE-COVERAGE"].outcome == "SATISFIED"
    assert second_rules["LINE-RMS"].outcome == "NOT_SATISFIED"

    raw["line_requirements"][1]["rms"]["value"] = "0.3"
    passing = _evaluate(document)
    assert [p.truth for p in passing.result.pairs] == [Truth.FALSE, Truth.TRUE]
    assert passing.result.branch.truth is Truth.TRUE
    assert len(passing.pairing.attempts) == 2  # never 3 physical SPW rows


def test_unapproved_scientific_evidence_preserves_real_unknown():
    context, common = _single_context()
    modified = tuple(replace(c, approval=MethodApproval.PROVISIONAL) if c.criterion_id == "ANGULAR"
                     else c for c in common)
    prepared = prepare_submitted_line_request(_wire("240")["request"])
    result = evaluate_submitted_line_context_v2(prepared, context, modified)
    assert result.result.branch.truth is Truth.FALSE  # definitive coverage failure dominates AND
    assert result.result.pairs[0].truth is Truth.FALSE

    prepared = prepare_submitted_line_request(_wire("225.1")["request"])
    unknown = evaluate_submitted_line_context_v2(prepared, context, modified)
    assert unknown.result.branch.truth is Truth.UNKNOWN
    assert "UNRESOLVED_SUBMITTED_LINE_PAIRS" in unknown.result.branch.reasons


def test_unresolved_candidate_context_does_not_allow_false_verdict():
    context, common = _single_context()
    context = replace(context, alternative_context_ids=("candidate-alternative",))
    prepared = prepare_submitted_line_request(_wire("240")["request"])
    output = evaluate_submitted_line_context_v2(prepared, context, common)
    assert output.result.branch.truth is Truth.UNKNOWN
    assert "BRANCH_SCOPE_UNSUPPORTED" in output.result.branch.reasons



def test_missing_archive_mode_is_real_unknown_not_invented_false():
    context, common = _single_context()
    evidence = replace(context.evidence, mode_evidence=None)
    context = replace(context, evidence=evidence)
    result = evaluate_submitted_line_context_v2(
        prepare_submitted_line_request(_wire("225.1")["request"]),
        context, common,
    )
    assert result.result.branch.truth is Truth.UNKNOWN
    assert result.result.pairs[0].truth is Truth.UNKNOWN
    fdm = next(c for c in result.result.pairs[0].criteria if c.criterion_id == "LINE-FDM")
    assert fdm.outcome is None


def test_rest_redshift_is_prepared_from_submitted_center_not_spw_frequency():
    document = _wire("230.538")
    entry = document["request"]["line_requirements"][0]
    entry["window_center"]["kind"] = "REST"
    document["request"]["source_redshift"] = "0.024"
    output = _evaluate(document)
    assert output.result.branch.truth is Truth.TRUE
    assert output.result.pairs[0].attempt.proposed.sky_frequency_ghz_exact is not None


@pytest.mark.parametrize("change", [
    lambda r: r["line_requirements"].append({
        "requirement_id": "line-b", "window_center": {"value": "225", "unit": "GHz", "kind": "SKY"},
        "correlator_mode": "FDM", "spectral_resolution": {"value": "20", "unit": "km/s"},
    }),
    lambda r: r.update(setup_complete=True),
    lambda r: r.update(line_evaluation_scope="SUBMITTED_LINE_REQUIREMENTS_V2"),
    lambda r: r.update(intents=["LINE", "CONTINUUM"]),
    lambda r: r.update(physical_spw_inventory_complete="on"),
])
def test_invalid_mixed_or_unsupported_requests_are_rejected(change):
    document = _wire()
    change(document["request"])
    with pytest.raises(ValueError, match="Invalid or unsupported|supports FIXED"):
        prepare_submitted_line_request(document["request"])


def test_cross_context_common_evidence_rejected():
    context, _ = _single_context()
    different = archive_report().context_evaluations[1]
    assert context.context_id != different.candidate.context.context_id
    prepared = prepare_submitted_line_request(_wire()["request"])
    with pytest.raises(ValueError, match="another candidate context"):
        evaluate_submitted_line_context_v2(prepared, context, different.criteria)


def test_old_wire_and_public_assessment_remain_fail_closed():
    document = _wire()
    validated = validate_proposed_observation(document["request"], document["search_options"])
    assert not validated.is_valid and not validated.can_search
    assert any(i.code == "SEPARATED_INPUT_NOT_EXECUTABLE" for i in validated.errors)
    sources = AssessmentSources(archive_kind="LIVE", archive_provider=lambda: pytest.fail("Archive accessed"))
    for geometry in ("SINGLE_POINTING", "MOSAIC"):
        request = deepcopy(document["request"])
        request["geometry"] = geometry
        report = assess_observation(request, document["search_options"], sources=sources)
        assert report.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY
        assert report.document is None
