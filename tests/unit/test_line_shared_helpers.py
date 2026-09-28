"""Boundary contracts for shared LINE rendering, explicit units and truth gates."""
from decimal import localcontext
from fractions import Fraction

import pytest

from alma_duplicate.rules.aggregation import Truth, criterion_truth
from alma_duplicate.rules.model import (
    CriterionResult, CriterionOutcome as O, EvaluationStatus as E,
    MethodApplicability as A, MethodApproval as P,
)
from alma_duplicate.rules.numeric import explicit_unit_quantity, rational_to_display


@pytest.mark.parametrize('value,sqrt,expected', [
    (None, False, None), (Fraction(0), False, 0.0),
    (Fraction(1, 8), False, .125), (Fraction(1, 16), True, .25),
    (Fraction(10)**400, False, None), (Fraction(1, 10**400), False, None),
    (Fraction(10)**400, True, 1e200), (Fraction(1, 10**400), True, 1e-200),
])
def test_display_preserves_zero_and_unrepresentable_value_behavior(value, sqrt, expected):
    assert rational_to_display(value, sqrt=sqrt) == expected


def test_display_does_not_inherit_ambient_decimal_precision():
    with localcontext() as ctx:
        ctx.prec = 2
        assert rational_to_display(Fraction(2), sqrt=True) == 1.4142135623730951
        assert ctx.prec == 2


@pytest.mark.parametrize('value,unit,target,expected', [
    (.9765625, 'MHz', 'GHz', Fraction('.0009765625')),
    (.5, 'Jy/beam', 'mJy/beam', Fraction(500)),
    (1000, 'm/s', 'km/s', Fraction(1)),
    (None, 'MHz', 'GHz', None), (1, None, 'GHz', None),
    (True, 'MHz', 'GHz', None), (0, 'MHz', 'GHz', None),
    (-1, 'MHz', 'GHz', None), (float('nan'), 'MHz', 'GHz', None),
    (float('inf'), 'MHz', 'GHz', None), ('1', 'MHz', 'GHz', None),
    (1, 'invalid-unit', 'GHz', None), (1, 'MHz', 'arcsec', None),
])
def test_explicit_units_keep_decimal_scale_and_unavailable_evidence(value, unit, target, expected):
    assert explicit_unit_quantity(value, unit, target) == expected


@pytest.mark.parametrize('approval,evaluation,applicability,outcome,expected', [
    (P.APPROVED, E.EVALUATED, A.APPLICABLE, O.SATISFIED, Truth.TRUE),
    (P.APPROVED, E.EVALUATED, A.APPLICABLE, O.NOT_SATISFIED, Truth.FALSE),
    (P.PROVISIONAL, E.EVALUATED, A.APPLICABLE, O.SATISFIED, Truth.UNKNOWN),
    (P.PROVISIONAL, E.EVALUATED, A.APPLICABLE, O.NOT_SATISFIED, Truth.UNKNOWN),
    (P.APPROVED, E.INSUFFICIENT_INFORMATION, A.UNRESOLVED, None, Truth.UNKNOWN),
    (P.APPROVED, E.NOT_APPLICABLE, A.NOT_APPLICABLE, None, Truth.UNKNOWN),
    (P.APPROVED, E.NOT_EVALUATED, A.UNRESOLVED, None, Truth.UNKNOWN),
])
def test_truth_retains_formal_eligibility_gate(approval, evaluation, applicability, outcome, expected):
    result = CriterionResult(
        criterion_id='LINE-RMS', policy_ref='test', method_version='test',
        approval=approval, evaluation=evaluation, applicability=applicability,
        outcome=outcome, context_id='context', proposed=None, candidate=None,
        decision_refs=('tests:shared-line-helpers',),
    )
    assert criterion_truth(result) is expected
