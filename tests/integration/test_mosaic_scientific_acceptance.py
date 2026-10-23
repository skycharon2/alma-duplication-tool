"""Mosaic end-to-end scientific acceptance: deterministic, no live Archive calls.

The fixtures are synthetic or captured metadata; they are not supervisor-labelled
real proposal decisions. These checks protect Appendix A's shared rule structure.
"""

from dataclasses import replace
from copy import deepcopy

import pytest

from alma_duplicate.mosaic_candidate_discovery import plan_discovery
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.continuum import (
    evaluate_continuum_frequency,
    evaluate_continuum_rms,
)
from alma_duplicate.rules.line import evaluate_line
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from tests.integration.test_mosaic_context import data, other_execution


def _points(*positions):
    return [
        dict(id=str(i), frame="ICRS", ra_deg=float(ra), dec_deg=0.0)
        for i, ra in enumerate(positions)
    ]


def _line_case():
    # Reuse the approved numerical LINE Guide B fixture, not an invented
    # sensitivity/resolution formula or a vacuously empty set of line pairs.
    from types import SimpleNamespace
    from alma_duplicate.proposed_mosaic import import_proposed
    from tests.integration.test_line_preparation import report as line_report

    source_report = line_report()
    context = source_report.context_evaluations[0].candidate.context
    request = replace(
        source_report.search_result.plan.validation.request,
        geometry="MOSAIC", target_name="proposed",
    )
    proposed = import_proposed(
        b"RA,Dec,Coordinate Type,Coordinate Units\n--\n0,0,Absolute,Degrees\n",
        source_name="proposed", array="12m",
        confirm_fixed_icrs=True, confirm_complete=True,
    )
    raw = context.evidence.prepared.raw_row
    execution = dict(
        project_code=raw["proposal_id"],
        member_ous_uid=raw["member_ous_uid"],
        source_name=raw["target_name"],
        asdm_uid=raw["asdm_uid"],
        evidence=dict(fields=[dict(
            field_id=1, frame="ICRS", ra_deg=0.0, dec_deg=0.0,
            target_name=raw["target_name"],
        )]),
    )
    array = SimpleNamespace(
        context_id=context.context_id,
        source_record_id=context.reference.source_record_id,
        diameters_m=(12.0,),
    )
    return request, context, proposed, execution, array


@pytest.mark.parametrize("case,expected", [
    ("positive", Truth.TRUE),
    ("line_outside", Truth.FALSE),
    ("missing_rms", Truth.UNKNOWN),
    ("position_half", Truth.UNKNOWN),
])
def test_line_positive_negative_and_missing_evidence(case, expected):
    request, context, proposed, execution, array = _line_case()
    if case == "line_outside":
        window = request.spectral_windows[0]
        quantity = replace(window.center.quantity, value=500.0, raw_value=500.0)
        changed = replace(window, center=replace(window.center, quantity=quantity))
        request = replace(request, spectral_windows=(changed,))
    elif case == "missing_rms":
        request = replace(request, sensitivities=tuple(
            replace(s, rms=None) if s.purpose == "LINE" else s
            for s in request.sensitivities
        ))
    elif case == "position_half":
        proposed = dict(proposed, points=_points(0, 1))
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert result["branches"][0].truth is expected
    assert result["line_pairs"], "Acceptance must evaluate real line pairs"
    rules = {r.criterion_id: r for r in result["line_pairs"][0].criteria}
    if case == "line_outside":
        assert rules["LINE-COVERAGE"].outcome == "NOT_SATISFIED"
    if case == "missing_rms":
        assert rules["LINE-RMS"].outcome is None
    if case == "positive":
        assert all(r.outcome == "SATISFIED" for r in rules.values())


@pytest.mark.parametrize(
    "positions,complete,expected_outcome,expected_inside",
    [
        ((0, 0.001, 1), True, "SATISFIED", 2),
        ((0, 1), True, None, 1),   # exactly half is NOT a majority
        ((0, 1, 2), True, None, 1),
        ((0, 0.001, 1), False, None, 2),
    ],
)
def test_majority_boundary_and_proposal_completeness(
    positions, complete, expected_outcome, expected_inside
):
    request, context, proposed, execution, array = data()
    proposed = dict(
        proposed,
        points=_points(*positions),
        completeness="USER_CONFIRMED_COMPLETE" if complete else "NOT_CONFIRMED",
    )
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    position = result["criteria"][1]
    assert position.outcome == expected_outcome
    assert result["coverage"]["inside_count"] == expected_inside
    assert result["coverage"]["pointing_count"] == len(positions)
    if expected_outcome is None:
        assert result["branches"][0].truth is not Truth.TRUE


def test_exact_beam_boundary_remains_unresolved_not_positive():
    request, context, proposed, execution, array = data()
    first = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array,
    )
    radius = first["coverage"]["circles"][0]["radius_arcsec"]
    proposed = dict(proposed, points=_points(radius / 3600.0))
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array,
    )
    position = result["criteria"][1]
    assert position.outcome is None
    assert position.issues[0].code == "MOSAIC_BOUNDARY_COUNT_UNRESOLVED"
    assert result["coverage"]["boundary_count"] == 1
    assert result["branches"][0].truth is not Truth.TRUE


def test_continuum_nonposition_results_are_exact_shared_evaluators():
    request, context, proposed, execution, array = data()
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    criteria = {c.criterion_id: c for c in result["criteria"]}
    assert criteria["CONT-FREQ"] == evaluate_continuum_frequency(request, context)
    assert criteria["CONT-RMS"] == evaluate_continuum_rms(request, context)
    assert result["branches"][0].required_criteria == (
        "POS-MOSAIC", "ANGULAR", "CONT-SETUP", "CONT-FREQ", "CONT-RMS"
    )


def test_definite_frequency_failure_cannot_be_rescued_by_valid_position():
    request, context, proposed, execution, array = data()
    evidence = context.evidence.prepared.comparison_evidence
    q = replace(evidence.frequency.centre, canonical_value=999.0)
    updated = replace(evidence, frequency=replace(evidence.frequency, centre=q))
    prepared = replace(context.evidence.prepared, comparison_evidence=updated)
    context = replace(context, evidence=replace(context.evidence, prepared=prepared))
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    assert result["criteria"][1].outcome == "SATISFIED"
    assert next(c for c in result["criteria"] if c.criterion_id == "CONT-FREQ").outcome == "NOT_SATISFIED"
    assert result["branches"][0].truth is Truth.FALSE


def test_missing_continuum_rms_is_not_promoted_to_positive():
    request, context, proposed, execution, array = data()
    evidence = context.evidence.prepared.comparison_evidence
    missing = replace(evidence.continuum_sensitivity.quantity, canonical_value=None)
    prepared_evidence = replace(
        evidence,
        continuum_sensitivity=replace(evidence.continuum_sensitivity, quantity=missing),
    )
    context = replace(
        context, evidence=replace(context.evidence, prepared=replace(
            context.evidence.prepared, comparison_evidence=prepared_evidence,
        )),
    )
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array,
    )
    assert result["criteria"][1].outcome == "SATISFIED"
    assert next(c for c in result["criteria"] if c.criterion_id == "CONT-RMS").outcome is None
    assert result["branches"][0].truth is not Truth.TRUE


def test_incompatible_execution_cannot_supply_a_second_pointing():
    request, context, proposed, execution, array = data()
    other, second = other_execution(context, execution, ra=1.0, frequency=999.0)
    proposed = dict(proposed, points=_points(0, 1, 2))
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution, second],
        metadata_contexts=[other], array_evidence=array
    )
    assert result["coverage"]["inside_count"] == 1
    assert result["coverage"]["included_asdm_uids"] == [execution["asdm_uid"]]
    assert result["criteria"][1].outcome is None


def test_absent_execution_readiness_cannot_qualify_position():
    request, context, proposed, execution, array = _line_case()
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution],
        array_evidence=array, ready_asdm_uids=set(),
    )
    position = next(c for c in result["criteria"] if c.criterion_id == "POS-MOSAIC")
    assert position.outcome is None
    assert position.issues[0].code == "EXECUTION_POSITION_READINESS_REQUIRED"
    assert result["branches"][0].truth is not Truth.TRUE


def test_distinct_selected_spectral_component_does_not_expand_union():
    request, context, proposed, execution, array = _line_case()
    other, second = other_execution(context, execution, ra=1)
    component = other.evidence.selected_component
    assert component is not None
    altered_component = replace(component, component_index=component.component_index + 1)
    other = replace(other, evidence=replace(other.evidence, selected_component=altered_component))
    proposed = dict(proposed, points=_points(0, 1, 2))
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution, second],
        metadata_contexts=[other], array_evidence=array,
    )
    assert result["coverage"]["included_asdm_uids"] == [execution["asdm_uid"]]
    assert result["coverage"]["inside_count"] == 1
    assert result["criteria"][1].outcome is None


def test_line_numerics_are_identical_between_mosaic_and_single():
    request, context, proposed, execution, array = _line_case()
    result = evaluate_mosaic_context(
        request, context, proposed, executions=[execution], array_evidence=array
    )
    single_request = replace(request, geometry="SINGLE_POINTING")
    pos_single = replace(result["criteria"][1], criterion_id="POS-SINGLE")
    _, single_pairs, _ = evaluate_line(
        single_request, context, (pos_single, result["criteria"][0]), mosaic=False
    )
    mosaic_pairs = result["line_pairs"]
    assert len(mosaic_pairs) == len(single_pairs) > 0
    for mosaic_pair, single_pair in zip(mosaic_pairs, single_pairs):
        assert mosaic_pair.criteria[2:] == single_pair.criteria[2:]


@pytest.mark.parametrize("mutation,needle", [
    ("project", "project"),
    ("field_target", "another target"),
    ("acquisition", "acquisition"),
])
def test_execution_and_context_provenance_is_not_interchangeable(mutation, needle):
    request, context, proposed, execution, array = data()
    execution = deepcopy(execution)
    if mutation == "project":
        execution["project_code"] = "WRONG-PROJECT"
    elif mutation == "field_target":
        execution["evidence"]["fields"][0]["target_name"] = "WRONG-TARGET"
    else:
        other, _ = other_execution(context, execution)
        other = replace(
            other,
            reference=replace(other.reference, source_record_id="foreign-acquisition"),
        )
        with pytest.raises(ValueError, match=needle):
            evaluate_mosaic_context(
                request, context, proposed, executions=[execution],
                metadata_contexts=[other], array_evidence=array
            )
        return
    with pytest.raises(ValueError, match=needle):
        evaluate_mosaic_context(
            request, context, proposed, executions=[execution], array_evidence=array
        )


def test_cross_geometry_discovery_is_not_yet_implemented():
    # This is a regression reminder of a known coverage gap, NOT a passing
    # scientific acceptance test for Mosaic vs Archive Single Pointing.
    _, _, proposed, _, _ = data()
    proposed["input_sha256"] = proposed.get("input_sha256", "fixture")
    plan = plan_discovery(proposed, margin_arcsec=1)
    assert all("is_mosaic='T'" in req["query"] for req in plan["requests"])
    assert "MOSAICS" in plan["scope"]
    assert plan["recall_status"].startswith("NOT_ESTABLISHED")
