"""REST/SKY parity, exact boundaries and missing evidence for both sources."""

from dataclasses import replace
from fractions import Fraction

import pytest

from alma_duplicate.proposed_frequency import prepare_frequency
from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.continuum import evaluate_continuum_frequency
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from tests.integration.test_confirmed_continuum import case, payload
from tests.integration.test_queue_continuum import case as queue_case, rule


def request(value=460, kind='REST', z=1, unit='GHz'):
    p = payload()
    p['request']['representative_frequency'].update(value=value, kind=kind, unit=unit)
    p['request']['source_redshift'] = z
    return validate_proposed_observation(p['request'], p['search_options'])


def evaluate(validation, source, candidate=230):
    if source == 'ARCHIVE':
        _, context, _ = case(frequency=candidate)
        return evaluate_continuum_frequency(validation.request, context)
    search, _, _ = queue_case({'Ref.Frequency': str(candidate)})
    search = replace(search, plan=replace(search.plan, validation=validation))
    return rule(evaluate_candidate_search(search, queue_continuum=True).context_evaluations[0], 'CONT-FREQ')


@pytest.mark.parametrize('source', ['ARCHIVE', 'QUEUE'])
@pytest.mark.parametrize('unit,value', [('GHz', '460'), ('MHz', '460000'), ('kHz', '460000000'), ('Hz', '460000000000')])
def test_rest_units_match_sky_and_preserve_input(source, unit, value):
    v = request(value=value, unit=unit)
    result = evaluate(v, source)
    direct = evaluate(request(230, 'SKY', 99), source)
    assert v.is_valid and not [i for i in v.issues if i.rule_id == 'CONT-FREQ']
    assert result.outcome == direct.outcome == 'SATISFIED'
    assert result.proposed.value == direct.proposed.value == 230
    assert v.request.representative_frequency.kind == 'REST'
    details = dict(result.details)
    assert details['input_frequency_value'] == value
    assert details['input_frequency_unit'] == unit
    assert details['sky_frequency_ghz_exact'] == '230'
    assert dict(result.derived)['source_redshift'] == 1
    assert result.method_version == ('archive_cont_freq_2' if source == 'ARCHIVE' else 'queue_cont_freq_3')


@pytest.mark.parametrize('source', ['ARCHIVE', 'QUEUE'])
@pytest.mark.parametrize('value,outcome', [('260', 'SATISFIED'), ('260.00000000000000001', 'NOT_SATISFIED')])
def test_no_float_rounding_across_frequency_boundary(source, value, outcome):
    assert evaluate(request(value), source, candidate=100).outcome == outcome


@pytest.mark.parametrize('source', ['ARCHIVE', 'QUEUE'])
@pytest.mark.parametrize('kind,z,code', [('REST', None, 'SOURCE_REDSHIFT_REQUIRED'),
                                      ('UNKNOWN', 1, 'FREQUENCY_REFERENCE_REQUIRED')])
def test_missing_evidence_has_no_verdict_but_can_search(source, kind, z, code):
    v = request(kind=kind, z=z)
    assert v.is_valid and v.can_search
    assert any(i.code == code and i.rule_id == 'CONT-FREQ' for i in v.issues)
    result = evaluate(v, source)
    assert result.outcome is None and code in result.reasons


@pytest.mark.parametrize('z', [-1, -2, 'NaN', 'inf', True])
def test_invalid_redshift_is_rejected(z):
    assert not request(z=z).is_valid


@pytest.mark.parametrize('z,sky', [(0, 460), (-0.5, 920)])
def test_zero_and_negative_valid_redshifts(z, sky):
    v = request(z=z)
    assert v.is_valid
    assert prepare_frequency(v.request.representative_frequency, v.request.source_redshift).sky_ghz == sky


def test_unrepresentable_conversion_is_unresolved():
    v = request(value=1e308, z=-0.9999999999999999)
    assert v.is_valid
    assert prepare_frequency(v.request.representative_frequency, v.request.source_redshift).reasons == ('SKY_FREQUENCY_UNREPRESENTABLE',)


def test_line_and_continuum_share_exact_frequency_without_mutating_rms():
    v = request(value='230.538', z=0.024)
    frequency = v.request.representative_frequency
    window = replace(v.request.spectral_windows[0], center=frequency)
    line = prepare_line_window(window, (), v.request.source_redshift)
    cont = prepare_frequency(frequency, v.request.source_redshift)
    assert Fraction(line.sky_frequency_ghz_exact) == cont.sky_ghz_exact == Fraction('230.538') / Fraction('1.024')


def test_explicit_request_beam_selector_uses_same_preparation():
    from alma_duplicate.primary_beam import requested_beam_frequency
    assert requested_beam_frequency(request().request) == 230
    assert requested_beam_frequency(request(230, 'SKY', 9).request) == 230
    assert requested_beam_frequency(request(z=None).request) is None
