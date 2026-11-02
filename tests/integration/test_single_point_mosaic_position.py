"""Scientific position and branch acceptance for proposed single points."""
from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.comparison import build_archive_contexts
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request, evaluate_submitted_line_context_v2
from alma_duplicate.rules.confirmed import approve_angular
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.spatial_evidence import adapt_spatial
from tests.integration.test_confirmed_continuum import case
from tests.integration.test_auto_retrieval import auto_payload, validate
from tests.integration.test_search_plan_spatial import archive
from alma_duplicate.search_plan import build_search_plan
from tests.integration.test_submitted_line_context_evaluation_step04b import _wire
from tests.integration.test_line_preparation import report


@pytest.mark.parametrize('array', ['TP', 'A001:DA01 T701:PM01'])
def test_tp_scope_stays_unknown(array):
    r, c, e = case(mosaic='T', array=array)
    result = evaluate_position_single(r, c, e)
    assert result.outcome is None


def test_region_does_not_need_center_or_frequency_for_position():
    r, c, e = case(mosaic='T', s_ra=None, s_dec=None, frequency=None)
    assert evaluate_position_single(r, c, e).outcome == 'SATISFIED'


@pytest.mark.parametrize('region,status', [('Circle ICRS 201.365 -43.019 1', 'CRITERIA_MET'),
                                         ('Circle ICRS 0 0 1', 'CRITERIA_NOT_MET'),
                                         (None, 'INDETERMINATE')])
def test_continuum_branch_uses_region(region, status):
    v = validate(auto_payload())
    source, _ = archive(build_search_plan(v), mosaic='T', region=region,
                        frequency=240., spatial_resolution=.45, cont_sensitivity_bandwidth=.15)
    item = evaluate_candidate_search(search_candidates(v, archive_result=source)).context_evaluations[0]
    assert item.branches[0].status == status


@pytest.mark.parametrize('frequency,truth', [('225.1', 'TRUE'), ('240', 'FALSE')])
def test_v2_line_uses_mosaic_position_and_unchanged_spectral_criteria(frequency, truth):
    prepared = prepare_submitted_line_request(_wire(frequency)['request'])
    original = report().search_result.archive.source_record
    point = prepared.line_request.position
    rows = (dict(original.rows[0], is_mosaic='T',
                 s_region=f'Circle ICRS {point.ra_deg} {point.dec_deg} 1'),)
    source = replace(original, rows=rows, provenance=replace(original.provenance, expected_count=1, retrieved_count=1))
    context = build_archive_contexts(source).contexts[0]
    request = prepared.line_request
    position = evaluate_position_single(request, context, adapt_spatial(context, source))
    common = (approve_angular(evaluate_angular_resolution(request, context), request, context), position)
    result = evaluate_submitted_line_context_v2(prepared, context, common)
    assert position.outcome == 'SATISFIED'
    assert result.result.branch.truth == truth


def test_conflicting_context_is_rejected():
    r, c, e = case(mosaic='T')
    with pytest.raises(ValueError, match='different context'):
        evaluate_position_single(r, replace(c, context_id='other'), e)


def test_conflicting_interpretation_remains_unresolved():
    from alma_duplicate.domain.spatial import PositionInterpretation
    r, c, e = case(mosaic='T')
    e = replace(e, interpretation=PositionInterpretation(c.context_id, 'ICRS', 'MOVING', 'test'))
    result = evaluate_position_single(r, c, e)
    assert result.outcome is None
    assert 'CONFLICTING_POSITION_INTERPRETATION' in result.reasons


def test_candidate_regions_are_not_pooled():
    inside = case(mosaic='T')
    outside = case(mosaic='T', region='Circle ICRS 0 0 1')
    assert evaluate_position_single(*inside).outcome == 'SATISFIED'
    assert evaluate_position_single(*outside).outcome == 'NOT_SATISFIED'
