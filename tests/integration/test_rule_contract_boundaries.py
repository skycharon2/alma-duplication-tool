"""Independent threshold and result-contract regressions; no live services."""
from dataclasses import replace
from decimal import localcontext
import math

import pytest

from alma_duplicate.rules import (
    CriterionOutcome as O, EvaluationStatus as E, MethodApplicability as A,
    MethodApproval, EvidenceSide, evaluate_angular_resolution, evaluate_continuum_setup,
)
from alma_duplicate.rules.numeric import symmetric_factor
from tests.integration.test_rules_angular import archive_context, with_resolution
from tests.integration.test_search_plan_spatial import validation
from tests.unit.test_rules_continuum_setup import request, window


def angular(proposed=1., candidate=.5):
    return evaluate_angular_resolution(with_resolution(validation().request, proposed),
                                       archive_context(candidate))


@pytest.mark.parametrize('factor,expected', [
    (math.nextafter(2., 0.), O.SATISFIED), (2., O.SATISFIED),
    (math.nextafter(2., math.inf), O.NOT_SATISFIED), (2.000000001, O.NOT_SATISFIED),
])
def test_angular_no_equality_band_in_either_direction(factor, expected):
    assert angular(factor, 1.).outcome is expected
    assert angular(1., factor).outcome is expected


@pytest.mark.parametrize('width,expected', [
    (math.nextafter(1.8, 0.), O.NOT_SATISFIED), (1.8, O.NOT_SATISFIED),
    (math.nextafter(1.8, math.inf), O.SATISFIED), (1.8000000005, O.SATISFIED),
])
def test_usable_width_strict_boundary(width, expected):
    result = evaluate_continuum_setup(request([window('a', width), window('b', width)]))
    assert result.outcome is expected
    if width == 1.8000000005:
        assert "1.8000000005" in dict(result.details)["a"]


def test_both_missing_sides_survive():
    result = angular(None, None)
    assert result.outcome is None
    assert result.evaluation is E.INSUFFICIENT_INFORMATION
    assert result.issue_sides == (EvidenceSide.PROPOSED, EvidenceSide.CANDIDATE)
    assert {i.path for i in result.issues} == {'request.angular_resolution', 'context.angular_resolution'}


def test_invalid_candidate_is_not_labelled_missing():
    assert angular(1., -1.).issues[0].code == 'INVALID_EVIDENCE'


def test_computed_provisional_result_cannot_enter_formal_aggregation():
    result = angular()
    assert result.has_computed_outcome
    assert not result.eligible_for_formal_aggregation
    approved = replace(result, approval=MethodApproval.APPROVED, decision_refs=('test-only-decision',))
    assert approved.eligible_for_formal_aggregation


@pytest.mark.parametrize('changes', [
    {'outcome': None}, {'evaluation': E.NOT_EVALUATED},
    {'applicability': A.UNRESOLVED},
    {'evaluation': E.NOT_APPLICABLE, 'outcome': None},
    {'approval': MethodApproval.APPROVED, 'decision_refs': ()},
])
def test_contradictory_result_is_rejected(changes):
    with pytest.raises(ValueError):
        replace(angular(), **changes)


def test_scope_exclusion_has_no_negative_condition_result():
    result = replace(angular(), evaluation=E.NOT_APPLICABLE, applicability=A.NOT_APPLICABLE,
                     outcome=None)
    assert not result.has_computed_outcome
    assert not result.eligible_for_formal_aggregation


def test_existential_positive_retains_nonblocking_missing_evidence():
    result = evaluate_continuum_setup(request(
        [window('a', 1.9), window('b', 1.9), window('c', None)], complete=False))
    assert result.outcome is O.SATISFIED
    assert {i.code for i in result.issues} == {'MISSING_USABLE_WIDTH', 'INCOMPLETE_ENUMERATION'}
    assert not result.eligible_for_formal_aggregation


def test_duplicate_window_identity_cannot_satisfy_count():
    proposed = request([window('a', 1.9)])
    with pytest.raises(ValueError, match='Duplicate window'):
        evaluate_continuum_setup(replace(proposed, spectral_windows=proposed.spectral_windows * 2))


def test_exact_arithmetic_independent_of_decimal_context_and_float_ratio_overflow():
    with localcontext() as ctx:
        ctx.prec = 2
        assert symmetric_factor(2.000000001, 1.) > 2
        assert symmetric_factor(1e300, 1e-300) > 2


@pytest.mark.parametrize('unit,width', [('GHz', 1.8000000005), ('MHz', 1800.0000005)])
def test_equivalent_canonical_units_above_boundary(unit, width):
    assert evaluate_continuum_setup(request([
        window('a', width, unit), window('b', width, unit)])).outcome is O.SATISFIED


@pytest.mark.parametrize('bad_width', [0., -1., float('nan'), float('inf'), True])
def test_invalid_typed_width_remains_unresolved(bad_width):
    proposed = request([window('a', 1.9)])
    original = proposed.spectral_windows[0]
    corrupt = replace(original, bandwidth=replace(original.bandwidth, value=bad_width))
    result = evaluate_continuum_setup(replace(proposed, spectral_windows=(corrupt,)))
    assert result.outcome is None
    assert result.issues[0].code == 'INVALID_EVIDENCE'


def test_incompatible_typed_width_unit_is_not_compared_as_ghz():
    proposed = request([window('a', 1.9)])
    original = proposed.spectral_windows[0]
    corrupt = replace(original, bandwidth=replace(original.bandwidth, unit='MHz'))
    result = evaluate_continuum_setup(replace(proposed, spectral_windows=(corrupt,)))
    assert result.outcome is None
    assert result.issues[0].code == 'INCOMPATIBLE_UNIT'


def test_blank_reference_cannot_document_approval():
    with pytest.raises(ValueError, match='decision reference'):
        replace(angular(), approval=MethodApproval.APPROVED, decision_refs=(' ',))
