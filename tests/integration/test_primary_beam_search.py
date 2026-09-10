"""Formula-mode search acceptance, with synthetic source evidence only."""
from dataclasses import replace
import math

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.primary_beam import primary_beam_fwhm_deg, evaluate_primary_beam
from alma_duplicate.search_plan import build_search_plan, bind_archive_query
from alma_duplicate.spatial import adapt_spatial
from alma_duplicate.domain.spatial import PositionInterpretation
from alma_duplicate.clients.archive_queries import build_count_adql, normalize_query_parameters, ArchiveQuerySpec
from tests.integration.test_search_plan_spatial import validation, archive
from tests.integration.test_candidate_search import queue_rows, interpretations

REF = 'test-only-user-frequency-convention'


def run_archive(**changes):
    v = validation()
    p = build_search_plan(v, beam_decision_ref=REF)
    a, c = archive(p, **changes)
    i = PositionInterpretation(c.context_id, 'ICRS', 'FIXED', 'synthetic-position')
    return search_candidates(v, archive_result=a, interpretations=(i,), beam_decision_ref=REF)


@pytest.mark.parametrize('frequency,diameter', [(100.,12.), (100.,7.), (690.,12.)])
def test_formula_full_width_and_inverse_scaling(frequency, diameter):
    w = primary_beam_fwhm_deg(frequency, diameter)
    assert w == pytest.approx(1.13*299792458/(frequency*1e9*diameter)*180/math.pi)
    assert primary_beam_fwhm_deg(frequency*2, diameter) == pytest.approx(w/2)


@pytest.mark.parametrize('value', [0, -1, True, float('nan'), float('inf'), '100'])
def test_invalid_numerical_inputs(value):
    with pytest.raises(ValueError):
        primary_beam_fwhm_deg(value, 12.)
    with pytest.raises(ValueError):
        primary_beam_fwhm_deg(100., value)


def test_center_query_expands_small_scope_to_supported_beam_bound():
    v = validation(radius=1e-5)
    p = build_search_plan(v, beam_decision_ref=REF)
    q = p.for_source('ARCHIVE').archive_query
    assert q.radius_deg > primary_beam_fwhm_deg(100.5, 7.)/2
    assert v.search_options.radius.value == 1e-5
    assert 'CONTAINS(POINT' in build_count_adql(q)
    assert 's_region' not in build_count_adql(q)
    a,c = archive(p, s_ra=0.001, region=None)
    result = search_candidates(v, archive_result=a, beam_decision_ref=REF,
        interpretations=(PositionInterpretation(c.context_id,'ICRS','FIXED','synthetic'),))
    assert result.archive.rows[0].disposition == 'MATCHED_FILTERS'


def test_coordinate_and_region_plans_cannot_share_binding():
    v = validation()
    legacy = build_search_plan(v)
    new = build_search_plan(v, beam_decision_ref=REF)
    a,_ = archive(legacy)
    assert bind_archive_query(new,a).status == 'MISMATCH'
    assert normalize_query_parameters(legacy.for_source('ARCHIVE').archive_query) != normalize_query_parameters(new.for_source('ARCHIVE').archive_query)
    assert 'INTERSECTS' in build_count_adql(legacy.for_source('ARCHIVE').archive_query)


@pytest.mark.parametrize('region', [None, 'INVALID', 'CIRCLE ICRS 180 70 0.001'])
def test_region_neither_supplies_nor_vetoes_formula(region):
    result = run_archive(region=region)
    row = result.archive.rows[0]
    assert row.disposition == 'MATCHED_FILTERS'
    b = row.filters[1].spatial
    assert b.threshold_deg == b.beam_fwhm_deg/2
    assert b.beam_frequency_ghz == 100.5
    assert b.antenna_diameter_m == 12.
    assert b.decision_ref == REF
    assert b.assessment == result.assessment == 'NOT_EVALUATED'
    assert result.archive.server_predicate_indices == (0,)


@pytest.mark.parametrize('changes', [{'mosaic':'T'}, {'array':'TP'}, {'array':'12-m 7-m'}])
def test_unsupported_archive_geometry_retained(changes):
    result = run_archive(**changes)
    assert result.archive.rows[0].disposition == 'RETAINED_UNEVALUATED'


def test_local_beam_outside_is_not_region_server_disagreement():
    result = run_archive(s_ra=.1)
    row = result.archive.rows[0]
    assert row.disposition == 'EXCLUDED'
    assert 'SERVER_LOCAL_SPATIAL_DISAGREEMENT' not in row.filters[1].reasons


def test_server_coordinate_inconsistency_retained():
    result = run_archive(s_ra=5.)
    assert result.archive.rows[0].disposition == 'RETAINED_UNEVALUATED'
    assert 'OUTSIDE_DOCUMENTED_CENTER_SCOPE' in result.archive.rows[0].filters[1].reasons


@pytest.mark.parametrize('frequency', [None, 'REST'])
def test_missing_or_rest_frequency_retains_without_center_fallback(frequency):
    v = validation()
    f = None if frequency is None else replace(v.request.representative_frequency, kind='REST')
    v = replace(v, request=replace(v.request, representative_frequency=f))
    p = build_search_plan(v, beam_decision_ref=REF)
    a,c = archive(p)
    out = search_candidates(v, archive_result=a, beam_decision_ref=REF,
        interpretations=(PositionInterpretation(c.context_id,'ICRS','FIXED','synthetic'),))
    assert out.archive.rows[0].disposition == 'RETAINED_UNEVALUATED'
    assert out.plan.retrieval_radius_deg == v.search_options.radius.value


def test_missing_position_interpretation_retained():
    v=validation(); a,_=archive(build_search_plan(v,beam_decision_ref=REF))
    assert search_candidates(v,archive_result=a,beam_decision_ref=REF).archive.rows[0].disposition == 'RETAINED_UNEVALUATED'


def test_queue_explicit_diameter_and_formula_exclusion():
    q = queue_rows({}, {'RA':'.1'})
    v = validation(sources=('QUEUE',), radius=.00001)
    i = tuple(replace(x,antenna_diameter_m=12.) for x in interpretations(q))
    out=search_candidates(v,queue_result=q,interpretations=i,beam_decision_ref=REF)
    assert sorted(r.disposition.value for r in out.queue.rows) == ['EXCLUDED','MATCHED_FILTERS']
    unknown=search_candidates(v,queue_result=q,interpretations=interpretations(q),beam_decision_ref=REF)
    assert all(r.disposition == 'RETAINED_UNEVALUATED' for r in unknown.queue.rows)


@pytest.mark.parametrize('change',[{'Long Offset':'5'}, {'Use TP?':'True'}])
def test_queue_unsupported_stays_retained(change):
    q=queue_rows(change)
    assert q.can_reconstruct
    i=tuple(replace(x,antenna_diameter_m=12.) for x in interpretations(q))
    out=search_candidates(validation(sources=('QUEUE',)),queue_result=q,interpretations=i,beam_decision_ref=REF)
    assert out.queue.rows[0].disposition == 'RETAINED_UNEVALUATED'


def test_ra_wrap_and_numerical_boundary():
    result=run_archive(s_ra=359.999)
    assert result.archive.rows[0].disposition == 'MATCHED_FILTERS'
    r=primary_beam_fwhm_deg(100.5,12.)/2
    result=run_archive(s_ra=r)
    assert 'SPATIAL_BOUNDARY_TOLERANCE' in result.archive.rows[0].filters[1].reasons


def test_polar_position():
    v=validation(dec=90.)
    p=build_search_plan(v,beam_decision_ref=REF)
    a,c=archive(p,s_ra=180.,s_dec=90.)
    e=adapt_spatial(c,a,interpretation=PositionInterpretation(c.context_id,'ICRS','FIXED','synthetic'))
    assert evaluate_primary_beam(p,e).status == 'INSIDE'


def test_reject_unidentified_strategy():
    with pytest.raises(ValueError):
        build_search_plan(validation(),beam_decision_ref=' ')
    with pytest.raises(ValueError):
        ArchiveQuerySpec(0,0,1,spatial_strategy='invalid')


def test_real_client_count_retrieval_preserve_center_strategy():
    from alma_duplicate.clients.archive_client import ArchiveClient
    from alma_duplicate.clients.archive_contract import TapResponse
    from tests.fakes import FakeTapExecutor
    from tests.integration.test_archive_pipeline_fixture import _field_metadata
    v=validation(sources=('ARCHIVE',))
    p=build_search_plan(v,beam_decision_ref=REF)
    a,c=archive(p,region=None)
    executor=FakeTapExecutor([
        TapResponse(rows=({'total_matches':1},),declared_columns=('total_matches',),
                    field_metadata=_field_metadata(('total_matches',)),query_status_raw='OK'),
        TapResponse(rows=a.rows,declared_columns=tuple(a.rows[0]),field_metadata=a.field_metadata,query_status_raw='OK')])
    client=ArchiveClient('https://example.invalid/tap',executor=executor)
    class Core:
        def search(self,spec):
            return client.search(spec,optional_columns=())
    out=search_candidates(v,archive_client=Core(),beam_decision_ref=REF)
    assert out.archive.status == 'COMPLETED'
    assert out.archive.query_binding.status == 'MATCHED'
    assert 'CONTAINS(POINT' in out.archive.source_record.provenance.count_adql
    assert 'CONTAINS(POINT' in out.archive.source_record.provenance.retrieval_adql
    # No manufactured per-run context interpretation for this newly acquired run.
    assert out.archive.rows[0].disposition == 'RETAINED_UNEVALUATED'


def test_formula_branch_rejects_supplied_legacy_query():
    v=validation();a,_=archive(build_search_plan(v))
    out=search_candidates(v,archive_result=a,beam_decision_ref=REF)
    assert out.archive.status == 'FAILED'
    assert out.archive.rows == ()


def test_public_selector_dispatches_formula_even_without_region():
    from alma_duplicate.spatial import evaluate_spatial
    v=validation();p=build_search_plan(v,beam_decision_ref=REF)
    a,c=archive(p,region=None)
    e=adapt_spatial(c,a,interpretation=PositionInterpretation(c.context_id,'ICRS','FIXED','synthetic'))
    assert evaluate_spatial(p,e).status == 'INSIDE'
    assert evaluate_spatial(p,e).operation == 'FORMULA_PRIMARY_BEAM'
