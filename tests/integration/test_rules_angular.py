"""ANGULAR criterion (Appendix A factor <= 2); criterion results only."""
from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.domain.proposed_observation import RequestQuantity
from alma_duplicate.rules import (
    CriterionOutcome as O, EvidenceSide, MethodApproval, evaluate_angular_resolution,
)
from alma_duplicate.search_plan import build_search_plan
from tests.integration.test_case1_live_rows import (
    EXPECTED_MEMBER, case1_request, live_rows_client, rows_by_member,
)
from tests.integration.test_search_plan_spatial import archive, queue, validation


def with_resolution(request, arcsec):
    quantity = None if arcsec is None else RequestQuantity(arcsec, "arcsec", arcsec, "arcsec")
    return replace(request, angular_resolution=quantity)


def archive_context(spatial_resolution):
    plan = build_search_plan(validation())
    _, context = archive(plan, spatial_resolution=spatial_resolution)
    return context


def test_case1_real_rows_within_and_beyond_factor_two():
    validation_result = case1_request()
    result = search_candidates(validation_result, archive_client=live_rows_client())
    request = with_resolution(validation_result.request, 0.25)
    groups = rows_by_member(result)
    matched = evaluate_angular_resolution(request, groups[EXPECTED_MEMBER][0].context)
    assert matched.outcome is O.SATISFIED
    assert dict(matched.derived)["factor"] == pytest.approx(0.25 / 0.2293524825457554)
    assert matched.candidate.source_field == "spatial_resolution"
    assert matched.candidate.semantics == "ARCHIVE_ESTIMATED_ROBUST_0.5"
    assert matched.approval is MethodApproval.PROVISIONAL
    assert matched.method_version == "angular_factor_1"
    assert "Appendix A" in matched.policy_ref
    (aca,) = groups["uid://A001/X1234/X1d8"]  # 6.59 arcsec 7-m row
    far = evaluate_angular_resolution(request, aca.context)
    assert far.outcome is O.NOT_SATISFIED
    assert "FACTOR_EXCEEDS_LIMIT" in far.reasons


@pytest.mark.parametrize("proposed,candidate,outcome", [
    (1.0, 0.5, O.SATISFIED),       # exactly 2, inclusive boundary
    (0.25, 0.5, O.SATISFIED),      # symmetric factor
    (1.0, 0.4999, O.NOT_SATISFIED),
    (0.5, 1.0000001, O.NOT_SATISFIED),
    (0.5, 0.5, O.SATISFIED),
])
def test_factor_boundary_is_inclusive_and_symmetric(proposed, candidate, outcome):
    request = with_resolution(validation().request, proposed)
    assert evaluate_angular_resolution(request, archive_context(candidate)).outcome is outcome


def test_boundary_reason_is_explicit():
    request = with_resolution(validation().request, 1.0)
    result = evaluate_angular_resolution(request, archive_context(0.5))
    assert result.reasons == ("FACTOR_AT_INCLUSIVE_BOUNDARY",)


def test_missing_proposed_value_is_insufficient_not_negative():
    request = with_resolution(validation().request, None)
    result = evaluate_angular_resolution(request, archive_context(0.5))
    assert result.outcome is O.INSUFFICIENT_INFORMATION
    assert result.missing_side is EvidenceSide.PROPOSED
    assert not result.is_definite


@pytest.mark.parametrize("candidate", [None, 0.0, -1.0])
def test_missing_or_invalid_candidate_value_is_insufficient(candidate):
    request = with_resolution(validation().request, 0.5)
    result = evaluate_angular_resolution(request, archive_context(candidate))
    assert result.outcome is O.INSUFFICIENT_INFORMATION
    assert result.missing_side is EvidenceSide.CANDIDATE


def test_queue_requested_resolution_is_used_with_its_semantics():
    _, context = queue()
    requested = context.evidence.row.request.requested_angular_resolution_arcsec
    request = with_resolution(validation().request, requested.value * 1.5)
    result = evaluate_angular_resolution(request, context)
    assert result.candidate.source_field == "Req. Ang. Res."
    assert result.candidate.semantics == "QUEUE_REQUESTED"
    assert result.outcome is O.SATISFIED
    assert dict(result.derived)["factor"] == pytest.approx(1.5)
