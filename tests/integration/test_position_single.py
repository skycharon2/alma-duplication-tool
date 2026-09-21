"""Numeric criterion cases and independent direction checks, not duplication labels."""
from dataclasses import replace
import hashlib
import json
import math

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.cli.evaluate import main
from alma_duplicate.reporting import report_document
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.position_single import evaluate_position_single
from tests.integration.test_queue_candidate_beam import search, QUEUE, REQUEST
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_search_plan_spatial import validation, archive
from alma_duplicate.search_plan import build_search_plan


def criterion(result):
    row = result.queue.rows[0]  # includes excluded rows for direct rule tests
    return evaluate_position_single(result.plan.validation.request, row.context, row.spatial_evidence)


@pytest.mark.parametrize('offset,outcome', [(0, 'SATISFIED'), (20, 'NOT_SATISFIED'),
                                          (8.601107285572768, None)])
def test_direct_rule_inside_outside_boundary(offset, outcome):
    result = search(dec=20 + offset/3600)
    rule = criterion(result)
    assert rule.outcome == outcome
    assert rule.approval == 'PROVISIONAL'
    assert not rule.eligible_for_formal_aggregation
    assert dict(rule.derived)['candidate_radius_deg'] * 3600 == pytest.approx(8.601107285572768)
    if outcome is None:
        assert rule.evaluation == 'INSUFFICIENT_INFORMATION'
        assert 'SPATIAL_BOUNDARY_TOLERANCE' in rule.reasons
    if outcome == 'NOT_SATISFIED':
        assert result.total_retained == 0
        assert not evaluate_candidate_search(result).context_evaluations
        summary = report_document(evaluate_candidate_search(result))['sources']['QUEUE']['filter_summary']
        assert summary['excluded_rows'] == 1


@pytest.mark.parametrize('changes,reason', [
    ({'Use 7-m?':'True'}, 'QUEUE_ARRAY_COMBINATION_UNRESOLVED'),
    ({'Use TP?':'True'}, 'TP_GEOMETRY_UNSUPPORTED'),
    ({'RA':'0','Dec':'0'}, 'POSSIBLE_EPHEMERIS_PLACEHOLDER_NAME_CHECK_REQUIRED'),
    ({'Mosaic':'Custom'}, 'QUEUE_GEOMETRY_UNSUPPORTED'),
    ({'Mos. Coord.':'B1950'}, 'QUEUE_OFFSET_FRAME_UNSUPPORTED'),
])
def test_missing_or_unsupported(changes, reason):
    rule = criterion(search(changes))
    assert rule.outcome is None
    assert reason in rule.reasons


def test_rule_does_not_consume_search_labels():
    result = search()
    row = result.queue.rows[0]
    rule = criterion(result)
    forged = replace(row, filters=(), disposition='RETAINED_UNEVALUATED')
    altered = replace(result, queue=replace(result.queue, rows=(forged,)))
    assert evaluate_candidate_search(altered).context_evaluations[0].criteria[1] == rule
    assert 'PORTAL_EQUATORIAL_FRAME_CONVENTION_NOT_MEASURED_FRAME' in rule.reasons
    fallback = criterion(search({'Ref.Frequency':'0'}))
    assert dict(fallback.details)['frequency_source'] == 'sky_spw_weighted_mean'
    assert 'ZERO_REFERENCE_FREQUENCY_SKY_SPW_FALLBACK' in fallback.reasons


@pytest.mark.parametrize('dx,dy,ra,dec,expected_ra,expected_dec', [
    (5,0,10,0,10+5/3600,0), (-5,0,10,0,10-5/3600,0),
    (0,5,10,20,10,20+5/3600), (0,-5,10,20,10,20-5/3600),
])
def test_offset_cardinal_directions(dx,dy,ra,dec,expected_ra,expected_dec):
    result = search({'RA':str(ra),'Dec':str(dec),'Mosaic':'N/A',
                     'Long Offset':str(dx),'Lat Offset':str(dy)},ra=ra,dec=dec)
    center = result.queue.rows[0].spatial_evidence.center
    assert center.ra_deg == pytest.approx(expected_ra,abs=1e-10)
    assert center.dec_deg == pytest.approx(expected_dec,abs=1e-10)


def test_galactic_offset_against_cartesian_reference():
    # Standard rounded ICRS->Galactic rotation, used as an independent reference.
    # Independent Rodrigues/tangent construction: no directional_offset_by call.
    import numpy as np
    rotation = np.array([
        [-0.0548755604,-0.8734370902,-0.4838350155],
        [0.4941094279,-0.4448296300,0.7469822445],
        [-0.8676661490,-0.1980763734,0.4559837762]])
    ra,dec = math.radians(10),math.radians(20)
    original = np.array([math.cos(dec)*math.cos(ra),math.cos(dec)*math.sin(ra),math.sin(dec)])
    native = rotation @ original
    lon = math.atan2(native[1],native[0]); lat = math.asin(native[2])
    east = np.array([-math.sin(lon),math.cos(lon),0])
    north = np.array([-math.sin(lat)*math.cos(lon),-math.sin(lat)*math.sin(lon),math.cos(lat)])
    angle = math.radians(5/3600)
    shifted = rotation.T @ (native*math.cos(angle)+(3*east+4*north)/5*math.sin(angle))
    expected_ra = math.degrees(math.atan2(shifted[1],shifted[0])) % 360
    expected_dec = math.degrees(math.atan2(shifted[2],math.hypot(shifted[0],shifted[1])))
    center = search({'Mosaic':'N/A','Long Offset':'3','Lat Offset':'4',
                     'Mos. Coord.':'galactic'}).queue.rows[0].spatial_evidence.center
    # Rounded rotation matrix and frame realization limit absolute precision.
    assert center.ra_deg == pytest.approx(expected_ra, abs=1e-7)
    assert center.dec_deg == pytest.approx(expected_dec, abs=1e-7)


def test_archive_confirmed_position_and_queue_unselected_profile():
    v = validation(ra=10,dec=20)
    a,_ = archive(build_search_plan(v),s_ra=10.,s_dec=20.)
    result = search_candidates(v,archive_result=a,queue_result=queue_rows({'RA':'10','Dec':'20'}))
    rules = [c.criteria[1] for c in evaluate_candidate_search(result).context_evaluations]
    assert len(rules) == 2
    assert rules[0].outcome == 'SATISFIED'
    assert rules[1].outcome is None
    assert rules[1].reasons == ('QUEUE_CANDIDATE_POSITION_PROFILE_REQUIRED',)


def test_summary_overlapping_predicates_counts_rows_once():
    result = search(dec=20+20/3600)
    row = result.queue.rows[0]
    second = replace(row.filters[0],predicate_index=1,name='synthetic_second_filter')
    result = replace(result,queue=replace(result.queue,rows=(replace(row,filters=row.filters+(second,)),)))
    summary = report_document(evaluate_candidate_search(result))['sources']['QUEUE']['filter_summary']
    assert summary['processed_rows'] == summary['excluded_rows'] == 1
    assert len(summary['predicates']) == 2
    assert all(p['outcomes']['NO_MATCH'] == 1 for p in summary['predicates'])


def test_cli_ngc6240_full_retained_scope(tmp_path):
    output=tmp_path/'report.json'
    assert main(['--request',str(REQUEST),'--queue-csv',str(QUEUE),'--queue-candidate-beam',
                 '--output',str(output)]) == 0
    report=json.loads(output.read_text())
    assert report['evaluation_version'] == '4'
    scope=report['evaluation_scope']
    assert scope['evaluated_contexts'] == scope['total_retained'] == 13
    assert scope['shown_candidates'] == 1
    assert len(report['request_criteria']) == 1
    assert all([r['criterion_id'] for r in c['criteria']] == ['ANGULAR','POS-SINGLE','CONT-FREQ','CONT-RMS']
               for c in report['context_evaluations'])
    rule=report['context_evaluations'][0]['criteria'][1]
    assert rule['outcome'] == 'SATISFIED'
    assert dict(rule['derived'])['separation_deg'] == pytest.approx(0,abs=1e-10)
    assert dict(rule['derived'])['candidate_radius_deg']*3600 == pytest.approx(8.601107285572768)
    assert report['sources']['QUEUE']['source_metadata']['snapshot']['snapshot_sha256'] == hashlib.sha256(QUEUE.read_bytes()).hexdigest()
    assert report['assessment'] == 'NOT_AGGREGATED'


@pytest.mark.parametrize('change', [dict(target_kind='MOVING'), dict(geometry='MOSAIC'), dict(position=None)])
def test_proposed_scope_is_a_domain_gate(change):
    result = search()
    row = result.queue.rows[0]
    rule = evaluate_position_single(replace(result.plan.validation.request, **change),
                                    row.context, row.spatial_evidence)
    assert rule.outcome is None
    assert rule.reasons == ('PROPOSED_FIXED_SINGLE_POINT_POSITION_REQUIRED',)
