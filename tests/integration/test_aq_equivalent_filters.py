"""Opt-in ALMA Archive Query-equivalent Archive filters; candidate filters only."""
from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.domain.candidate_search import CandidateDisposition as D
from alma_duplicate.search_plan import (
    AQ_EQUIVALENT_FILTERS, AQ_FILTER_REASON, build_search_plan, evaluate_archive_scalar_filter,
)
from tests.integration.test_case1_live_rows import (
    EXPECTED_MEMBER, case1_request, live_rows_client, outcome, rows_by_member,
)
from tests.integration.test_search_plan_spatial import archive, validation

CASE1_FILTERS = [
    {"field": "frequency", "operator": "=", "quantity": {"value": 290.420, "unit": "GHz"}},
    {"field": "angular_resolution", "operator": "<", "quantity": {"value": 0.5, "unit": "arcsec"}},
    {"field": "spectral_resolution", "operator": "<", "quantity": {"value": 1500, "unit": "kHz"}},
    {"field": "sensitivity", "operator": "<", "quantity": {"value": 0.02, "unit": "mJy/beam"},
     "basis": "AGGREGATE"},
]


def test_default_plan_keeps_filters_skipped():
    plan = build_search_plan(case1_request(CASE1_FILTERS))
    actions = {p.name: p.action for p in plan.for_source("ARCHIVE").predicates}
    assert actions["frequency"] == actions["spectral_resolution"] == actions["sensitivity"] == "SKIPPED"
    assert plan.archive_filter_semantics is None


def test_opt_in_plans_archive_filters_locally_and_leaves_queue_skipped():
    plan = build_search_plan(validation(predicates=CASE1_FILTERS), aq_equivalent_filters=True)
    assert plan.archive_filter_semantics == AQ_EQUIVALENT_FILTERS
    archive_plan = {p.name: p for p in plan.for_source("ARCHIVE").predicates}
    for name in ("frequency", "spectral_resolution", "sensitivity"):
        assert archive_plan[name].action == "PLANNED_LOCAL"
        assert archive_plan[name].reason == AQ_FILTER_REASON
    queue_plan = {p.name: p for p in plan.for_source("QUEUE").predicates}
    assert queue_plan["frequency"].action == "SKIPPED"
    # Query text is unchanged: the filters are local, not ADQL prefilters.
    default = build_search_plan(validation(predicates=CASE1_FILTERS))
    assert plan.for_source("ARCHIVE").archive_query == default.for_source("ARCHIVE").archive_query


@pytest.mark.parametrize("predicate,reason", [
    ({"field": "frequency", "operator": "<", "quantity": {"value": 290, "unit": "GHz"}},
     "FREQUENCY_OPERATOR_UNSUPPORTED"),
    ({"field": "sensitivity", "operator": "<", "quantity": {"value": 1, "unit": "mJy/beam"},
      "basis": "NATIVE_CHANNEL"}, "RMS_BASIS_NOT_AGGREGATE"),
])
def test_unsupported_operator_or_basis_stays_skipped(predicate, reason):
    plan = build_search_plan(validation(predicates=[predicate]), aq_equivalent_filters=True)
    planned = plan.for_source("ARCHIVE").predicates[-1]
    assert planned.action == "SKIPPED" and planned.reason == reason


def test_case1_live_rows_reduce_to_the_reported_spectral_window():
    result = search_candidates(case1_request(CASE1_FILTERS), archive_client=live_rows_client(),
                               aq_equivalent_filters=True)
    retained = result.archive.retained_rows
    assert len(retained) == 1
    (row,) = retained
    assert row.disposition is D.MATCHED_FILTERS
    assert row.context.evidence.prepared.raw_row["obs_id"].endswith(".PKS1830-211.spw.29")
    assert result.archive.requested_filters_fully_evaluated is False  # excluded rows keep unresolved checks
    for name in ("frequency", "spectral_resolution", "sensitivity"):
        check = outcome(row, name)
        assert check.outcome == "MATCH"
        assert check.scalar.method_version == "aq_equivalent_1"
        assert AQ_FILTER_REASON in check.reasons
    others = [r for r in rows_by_member(result)[EXPECTED_MEMBER] if r is not row]
    assert len(others) == 3
    assert all(outcome(r, "frequency").outcome == "NO_MATCH" for r in others)
    assert result.assessment == "NOT_EVALUATED"


def _single(plan_predicates, **row_changes):
    v = validation(predicates=plan_predicates)
    plan = build_search_plan(v, aq_equivalent_filters=True)
    _, context = archive(plan, **row_changes)
    return plan, context


@pytest.mark.parametrize("frequency_ghz,status", [
    (100.0, "MATCH"),          # fixture row: 100 GHz centre, 0.2 GHz bandwidth
    (100.2, "NO_MATCH"),
    (100.1, "NOT_EVALUATED"),  # interval edge
    (99.9, "NOT_EVALUATED"),
])
def test_frequency_point_containment_and_edges(frequency_ghz, status):
    plan, context = _single([{"field": "frequency", "operator": "=",
                              "quantity": {"value": frequency_ghz, "unit": "GHz"}}])
    check = evaluate_archive_scalar_filter(plan, context, 1)
    assert check.status == status


def test_rest_frequency_context_is_not_compared_with_sky_intervals():
    plan, context = _single([{"field": "frequency", "operator": "=",
                              "quantity": {"value": 100, "unit": "GHz"},
                              "context": {"frequency_reference": {"kind": "REST"}}}])
    check = evaluate_archive_scalar_filter(plan, context, 1)
    assert check.status == "NOT_EVALUATED"
    assert "REST_FREQUENCY_NOT_COMPARED_WITH_SKY" in check.reasons


@pytest.mark.parametrize("changes,status", [
    ({"cont_sensitivity_bandwidth": None}, "NOT_EVALUATED"),
    ({"cont_sensitivity_bandwidth": 0.05}, "NO_MATCH"),
    ({"cont_sensitivity_bandwidth": 0.01}, "MATCH"),
])
def test_missing_sensitivity_never_excludes(changes, status):
    plan, context = _single([{"field": "sensitivity", "operator": "<",
                              "quantity": {"value": 0.02, "unit": "mJy/beam"}, "basis": "AGGREGATE"}],
                            **changes)
    assert evaluate_archive_scalar_filter(plan, context, 1).status == status


def test_spectral_resolution_units_are_converted():
    plan, context = _single([{"field": "spectral_resolution", "operator": "<",
                              "quantity": {"value": 1.5, "unit": "MHz"}}])
    check = evaluate_archive_scalar_filter(plan, context, 1)
    raw_khz = float(context.evidence.prepared.raw_row["spectral_resolution"])
    assert check.value == pytest.approx(raw_khz / 1000) and check.unit == "MHz"
    assert check.status == ("MATCH" if raw_khz < 1500 else "NO_MATCH")


def test_filters_are_not_evaluated_without_opt_in_semantics():
    plan, context = _single([{"field": "frequency", "operator": "=",
                              "quantity": {"value": 100, "unit": "GHz"}}])
    plain = replace(plan, archive_filter_semantics=None)
    assert evaluate_archive_scalar_filter(plain, context, 1).status == "NOT_EVALUATED"
