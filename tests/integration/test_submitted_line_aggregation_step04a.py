"""Step 04A: V2 context-local science aggregation; no new run entrypoint.

Use existing offline Guide B Archive and Mosaic pair evaluations. The V2 OR
reuses their approved *whole-pair* outcomes, not individually OR-ed criteria.
"""

from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.domain.line_pairing import LinePairBuildResult
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from alma_duplicate.rules.submitted_line import (
    METHOD_VERSION, SCOPE, aggregate_submitted_line_context,
)
from alma_duplicate.separated_setup_input import parse_separated_setup
from alma_duplicate.request_validation import _Validator, validate_proposed_observation
from tests.integration.test_line_evaluation import (
    evaluate as evaluate_single, sky_request, two_windows,
)
from tests.integration.test_line_preparation import EXAMPLE, validate
from tests.integration.test_mosaic_scientific_acceptance import _line_case
from tests.integration.test_separated_setup_contract_step03ba import new_wire


@pytest.fixture(scope="module")
def single_source():
    return search_candidates(
        validate(),
        archive_client=RecordedArchiveClient(EXAMPLE / "archive/manifest.json"),
    ).archive.source_record


def single_item(source, *, frequency=240, missing_rms=False, complete=False):
    wire = sky_request(frequency)
    wire["request"]["setup_complete"] = complete
    if missing_rms:
        wire["request"]["sensitivities"][0].pop("rms")
    return evaluate_single(source, wire).context_evaluations[0]


def mosaic_item(*, frequency_misses=False, missing_rms=False, complete=False):
    request, context, proposed, execution, array_evidence = _line_case()
    request = replace(request, setup_complete=complete)
    if frequency_misses:
        window = request.spectral_windows[0]
        quantity = replace(window.center.quantity, value=500.0, raw_value=500.0)
        request = replace(request, spectral_windows=(replace(
            window, center=replace(window.center, quantity=quantity)),))
    if missing_rms:
        request = replace(request, sensitivities=tuple(
            (replace(sensitivity, rms=None)
             if sensitivity.purpose == "LINE" else sensitivity)
            for sensitivity in request.sensitivities
        ))
    return evaluate_mosaic_context(
        request, context, proposed, executions=[execution],
        array_evidence=array_evidence,
    )


def v2(item, *, geometry="SINGLE_POINTING", submitted=None,
       pair_evaluations=None, pairing=None, context_supported=True):
    pairs = item.line_pairs if hasattr(item, "line_pairs") else item["line_pairs"]
    built = item.line_pairing if hasattr(item, "line_pairing") else item["line_pairing"]
    ids = (tuple(p.attempt.proposed_window_id for p in pairs)
           if submitted is None else submitted)
    return aggregate_submitted_line_context(
        submitted_requirement_ids=ids,
        pairing=built if pairing is None else pairing,
        pairs=pairs if pair_evaluations is None else pair_evaluations,
        geometry=geometry,
        context_supported=context_supported,
    )


@pytest.mark.parametrize("complete", [False, True])
def test_v2_negative_scopes_to_submitted_not_physical_inventory(
    single_source, complete,
):
    item = single_item(single_source, complete=complete)
    assert item.line_pairs[0].truth is Truth.FALSE
    result = v2(item)
    assert result.branch.truth is Truth.FALSE
    assert result.branch.status == "CRITERIA_NOT_MET"
    assert result.branch.method_version == METHOD_VERSION
    assert result.branch.scope == SCOPE
    assert "PROPOSED_ENUMERATION_INCOMPLETE" not in result.branch.reasons
    assert result.submitted_requirement_ids == (
        item.line_pairs[0].attempt.proposed_window_id,
    )
    assert result.pairs[0] is item.line_pairs[0]
    # The actual unchanged legacy branch still requires physical enumeration.
    assert item.branches[0].truth is (Truth.FALSE if complete else Truth.UNKNOWN)
    assert item.branches[0].method_version == "archive_line_context_or_1"


@pytest.mark.parametrize("case,expected", [
    ("true", Truth.TRUE), ("false", Truth.FALSE), ("unknown", Truth.UNKNOWN),
])
def test_single_point_science_outcomes(single_source, case, expected):
    item = single_item(single_source,
                       frequency=240 if case == "false" else 225.134765625,
                       missing_rms=case == "unknown")
    result = v2(item)
    assert result.pairs[0].truth is expected
    assert result.branch.truth is expected
    assert (
        "UNRESOLVED_SUBMITTED_LINE_PAIRS" in result.branch.reasons
    ) is (case == "unknown")
    assert result.branch.required_criteria[0] == "POS-SINGLE"


@pytest.mark.parametrize("case,expected", [
    ("true", Truth.TRUE), ("false", Truth.FALSE), ("unknown", Truth.UNKNOWN),
])
def test_mosaic_science_outcomes_remain_in_one_context(case, expected):
    item = mosaic_item(frequency_misses=case == "false", missing_rms=case == "unknown")
    result = v2(item, geometry="MOSAIC")
    assert result.pairs[0].truth is expected
    assert result.branch.truth is expected
    assert result.branch.required_criteria[0] == "POS-MOSAIC"
    assert result.branch.context_id == item["line_pairing"].candidate_context_id
    assert result.branch.method_version == METHOD_VERSION
    assert item["branches"][0].method_version == "archive_line_context_or_1"


@pytest.mark.parametrize("second_rms,remove_rms,expected", [
    (0.3, False, Truth.TRUE),
    (0.01, False, Truth.FALSE),
    (0.3, True, Truth.UNKNOWN),
])
def test_two_submitted_windows_are_or_of_complete_pairs_only(
    single_source, second_rms, remove_rms, expected,
):
    wire = two_windows(second_rms=second_rms)
    wire["request"]["setup_complete"] = False
    if remove_rms:
        wire["request"]["sensitivities"][1].pop("rms")
    item = evaluate_single(single_source, wire).context_evaluations[0]
    assert item.line_pairs[0].truth is Truth.FALSE
    result = v2(item)
    assert len(result.submitted_requirement_ids) == len(result.pairs) == 2
    assert result.branch.truth is expected
    assert result.branch.scope == SCOPE
    assert all(p.method_version == "archive_line_pair_and_1" for p in result.pairs)
    assert result.pairs == item.line_pairs
    if expected is Truth.FALSE:
        first, second = ({c.criterion_id: c.outcome for c in p.criteria}
                         for p in result.pairs)
        # A successful RMS from one pair and coverage from another never splice.
        assert first["LINE-RMS"] == "SATISFIED"
        assert second["LINE-COVERAGE"] == "SATISFIED"
        assert first["LINE-COVERAGE"] == second["LINE-RMS"] == "NOT_SATISFIED"
        assert item.branches[0].truth is Truth.UNKNOWN


def test_missing_eligible_pair_never_becomes_a_negative(single_source):
    wire = two_windows(second_rms=0.01)
    item = evaluate_single(single_source, wire).context_evaluations[0]
    assert all(pair.truth is Truth.FALSE for pair in item.line_pairs)
    result = v2(item, pair_evaluations=item.line_pairs[:1])
    assert result.branch.truth is Truth.UNKNOWN
    assert result.missing_requirement_ids == (
        item.line_pairs[1].attempt.proposed_window_id,
    )
    assert "SUBMITTED_LINE_PAIRS_INCOMPLETE" in result.branch.reasons
    # Missing attempt (not only missing evaluated pair) must also remain UNKNOWN.
    shortened = replace(item.line_pairing, attempts=item.line_pairing.attempts[:1])
    result = v2(item, pairing=shortened, pair_evaluations=item.line_pairs[:1])
    assert result.branch.truth is Truth.UNKNOWN


def test_true_with_an_unevaluated_requirement_still_or_true(single_source):
    wire = two_windows(second_rms=0.3)
    item = evaluate_single(single_source, wire).context_evaluations[0]
    assert [p.truth for p in item.line_pairs] == [Truth.FALSE, Truth.TRUE]
    result = v2(item, pair_evaluations=item.line_pairs[1:])
    assert result.branch.truth is Truth.TRUE
    assert result.missing_requirement_ids == (
        item.line_pairs[0].attempt.proposed_window_id,
    )


def test_unsupported_context_cannot_be_a_positive_or_negative(single_source):
    item = single_item(single_source, frequency=240)
    result = v2(item, context_supported=False)
    assert result.branch.truth is Truth.UNKNOWN
    assert "BRANCH_SCOPE_UNSUPPORTED" in result.branch.reasons
    positive = single_item(single_source, frequency=225.134765625)
    assert v2(positive, context_supported=False).branch.truth is Truth.UNKNOWN


def test_empty_submitted_requirements_are_unknown_even_if_pairing_says_complete(
    single_source,
):
    item = single_item(single_source)
    empty = LinePairBuildResult(item.line_pairing.candidate_context_id, (), True)
    result = v2(item, submitted=(), pairing=empty, pair_evaluations=())
    assert result.branch.truth is Truth.UNKNOWN
    assert result.submitted_requirement_ids == ()
    assert result.missing_requirement_ids == ()
    assert result.branch.reasons == ("NO_SUBMITTED_LINE_REQUIREMENTS",)


@pytest.mark.parametrize("inventory_complete", [False, True])
def test_new_separated_operands_select_only_line_not_physical(
    single_source, inventory_complete,
):
    item = single_item(single_source, complete=False)
    line_id = item.line_pairs[0].attempt.proposed_window_id
    wire = new_wire()
    wire["request"]["line_requirements"][0]["requirement_id"] = line_id
    wire["request"]["physical_spw_evidence"][0]["linked_line_requirement_id"] = line_id
    wire["request"]["physical_spw_inventory_complete"] = inventory_complete
    validator = _Validator()
    snapshot = validator.snapshot(wire["request"], "request")
    operands = parse_separated_setup(validator, snapshot)
    assert not [i for i in validator.issues if i.category == "ERROR"]
    line_windows, sensitivities = operands.line_comparison_operands
    assert len(line_windows) == len(sensitivities) == 1
    assert len(operands.continuum_window_evidence) == 2
    assert operands.physical_inventory_complete is inventory_complete
    assert all(w.window_id != line_id for w in operands.continuum_window_evidence)
    assert operands.physical_links[0].line_requirement_id == line_id
    result = v2(item, submitted=tuple(w.window_id for w in line_windows))
    assert result.branch.truth is Truth.FALSE
    # This step does not enable the separated request's *official* execution.
    validation = validate_proposed_observation(wire["request"], wire["search_options"])
    assert not validation.is_valid and not validation.can_search
    assert {i.code for i in validation.errors} == {"SEPARATED_INPUT_NOT_EXECUTABLE"}


def test_cross_context_or_unsubmitted_pairing_is_rejected():
    # evaluate_single() deliberately retains only the first Archive row.
    # The recorded Guide B report retains two independent candidate contexts.
    from tests.integration.test_line_preparation import report as recorded_line_report

    contexts = recorded_line_report().context_evaluations
    assert len(contexts) >= 2, "Cross-context acceptance needs two candidates"
    first, second = contexts[:2]
    assert first.candidate.context.context_id != second.candidate.context.context_id
    assert first.line_pairs and second.line_pairs
    with pytest.raises(ValueError, match="Pair evaluation"):
        v2(first, pair_evaluations=second.line_pairs)
    with pytest.raises(ValueError, match="unsubmitted"):
        v2(first, submitted=("some-other-requirement",))
    with pytest.raises(ValueError, match="Duplicate submitted"):
        v2(first, submitted=(first.line_pairs[0].attempt.proposed_window_id,) * 2)
    with pytest.raises(ValueError, match="wrong spatial geometry"):
        v2(first, geometry="MOSAIC")


def test_double_evaluation_or_pairing_mismatch_is_rejected(single_source):
    item = single_item(single_source)
    pair = item.line_pairs[0]
    with pytest.raises(ValueError, match="Duplicate LINE pair evaluation"):
        v2(item, pair_evaluations=(pair, pair))
    other = single_item(single_source, frequency=225.134765625)
    with pytest.raises(ValueError, match="does not match its pairing attempt"):
        v2(item, pair_evaluations=other.line_pairs)


def test_no_user_claim_or_legacy_enumeration_switch_can_control_v2(single_source):
    item = single_item(single_source, complete=False)
    with pytest.raises(TypeError, match="evaluated Boolean"):
        v2(item, context_supported="true")
    with pytest.raises(TypeError, match="must be tuples"):
        v2(item, submitted=[item.line_pairs[0].attempt.proposed_window_id])
    complete = replace(item.line_pairing, proposed_enumeration_complete=True)
    result = v2(item, pairing=complete)
    assert result.branch.truth is Truth.FALSE
    assert "PROPOSED_ENUMERATION_INCOMPLETE" not in result.branch.reasons
