"""Verified-source profile and explicitly synthetic boundary/exception cases."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from astropy.coordinates import SkyCoord
from astropy import units as u

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.cli.evaluate import main
from alma_duplicate.queue_normalization import map_nominal_to_usable_mhz
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_search_plan_spatial import validation, archive

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / 'tests/fixtures/queue/queue_pipeline_v1.csv'
REQUEST = ROOT / 'examples/single_point/request.json'


def search(changes=None, *, ra=10, dec=20):
    q = queue_rows({'RA':'10', 'Dec':'20', 'Ref.Frequency':'338.5'} | (changes or {}))
    assert q.can_reconstruct
    result = search_candidates(validation(ra=ra, dec=dec), queue_result=q, queue_candidate_beam=True)
    assert result.queue.status == 'COMPLETED'
    return result


def spatial(result):
    return result.queue.rows[0].filters[0].spatial


@pytest.mark.parametrize('offset,status', [(0, 'INSIDE'), (20, 'OUTSIDE'),
                                          (8.601107285572768, 'NOT_EVALUATED')])
def test_candidate_radius_boundary(offset, status):
    r = search(dec=20 + offset/3600)
    s = spatial(r)
    assert s.status == status
    assert s.beam_frequency_ghz == 338.5
    assert s.beam_frequency_source == 'Ref.Frequency'
    assert s.threshold_deg * 3600 == pytest.approx(8.601107285572768)
    if status == 'OUTSIDE': assert not r.queue.retained_rows
    if status == 'NOT_EVALUATED': assert 'SPATIAL_BOUNDARY_TOLERANCE' in s.reasons


def test_proposed_frequency_cannot_change_candidate_beam():
    q = queue_rows({'RA':'10', 'Dec':'20'})
    v = validation(ra=10, dec=20)
    before = spatial(search_candidates(v, queue_result=q, queue_candidate_beam=True))
    for value in (90, 700):
        changed = replace(v, request=replace(v.request, representative_frequency=replace(
            v.request.representative_frequency,
            quantity=replace(v.request.representative_frequency.quantity, value=value))))
        after = spatial(search_candidates(changed, queue_result=q, queue_candidate_beam=True))
        assert after.threshold_deg == before.threshold_deg
        assert after.beam_frequency_ghz == before.beam_frequency_ghz
    missing = replace(v, request=replace(v.request, representative_frequency=None))
    assert spatial(search_candidates(missing, queue_result=q, queue_candidate_beam=True)).status == 'INSIDE'


def test_zero_reference_frequency_uses_candidate_sky_windows():
    r = search({'Ref.Frequency':'0'})
    s = spatial(r)
    assert s.status == 'INSIDE'
    assert s.beam_frequency_source == 'sky_spw_weighted_mean'
    assert s.beam_frequency_ghz == pytest.approx(343.5)


@pytest.mark.parametrize('changes,reason', [
    ({'Use 7-m?':'True'}, 'QUEUE_ARRAY_COMBINATION_UNRESOLVED'),
    ({'Use TP?':'True'}, 'TP_GEOMETRY_UNSUPPORTED'),
    ({'RA':'0', 'Dec':'0'}, 'POSSIBLE_EPHEMERIS_PLACEHOLDER_NAME_CHECK_REQUIRED'),
    ({'Mos. Coord.':'B1950'}, 'QUEUE_OFFSET_FRAME_UNSUPPORTED'),
    ({'Mosaic':'Custom'}, 'QUEUE_GEOMETRY_UNSUPPORTED'),
    ({'Long Offset':'1'}, 'QUEUE_GEOMETRY_UNSUPPORTED'),
])
def test_uncertain_inputs_retained(changes, reason):
    result = search(changes)
    assert spatial(result).status == 'NOT_EVALUATED'
    assert reason in spatial(result).reasons
    assert len(result.queue.retained_rows) == 1


@pytest.mark.parametrize('mosaic', ['', 'N/A'])
def test_dictionary_single_field_categories(mosaic):
    assert spatial(search({'Mosaic':mosaic})).status == 'INSIDE'


@pytest.mark.parametrize('frame', ['', 'ICRS', 'J2000', 'galactic'])
def test_offsets_preserve_source_and_follow_spherical_transport(frame):
    r = search({'Mosaic':'N/A', 'Long Offset':'3', 'Lat Offset':'4', 'Mos. Coord.':frame})
    e = r.queue.rows[0].spatial_evidence
    original = SkyCoord(10*u.deg,20*u.deg,frame='icrs')
    actual = SkyCoord(e.center.ra_deg*u.deg,e.center.dec_deg*u.deg,frame='icrs')
    assert original.separation(actual).arcsec == pytest.approx(5, abs=1e-8)
    assert e.context.evidence.row.spatial.ra_deg.value == 10
    assert e.context.evidence.row.spatial.dec_deg.value == 20
    assert e.context.evidence.row.spatial.long_offset_arcsec.value == 3
    assert 'TANGENT_OFFSETS_SPHERICAL_1' in e.reasons
    assert spatial(r).status == 'INSIDE'


def offset_center(changes):
    evidence = search({'Mosaic':'N/A'} | changes).queue.rows[0].spatial_evidence
    return SkyCoord(evidence.center.ra_deg*u.deg, evidence.center.dec_deg*u.deg, frame='icrs')


def bearing_error(origin, moved, expected_deg):
    """Signed position-angle error, wrapped so that 0 and 360 are one bearing."""
    return (origin.position_angle(moved).deg - expected_deg + 180) % 360 - 180


# Position angle is measured from north through east, so a length-only check
# passes even when the two offset components are transported the wrong way.
@pytest.mark.parametrize('long_offset,lat_offset,arcsec,position_angle', [
    ('10', '0', 10, 90),
    ('-10', '0', 10, 270),
    ('0', '10', 10, 0),
    ('0', '-10', 10, 180),
    ('3', '4', 5, 36.86989764584402),
])
def test_offset_direction_follows_the_east_north_convention(
        long_offset, lat_offset, arcsec, position_angle):
    origin = SkyCoord(10*u.deg, 20*u.deg, frame='icrs')
    moved = offset_center({'Long Offset': long_offset, 'Lat Offset': lat_offset})
    assert origin.separation(moved).arcsec == pytest.approx(arcsec, abs=1e-8)
    assert bearing_error(origin, moved, position_angle) == pytest.approx(0, abs=1e-6)


def test_offset_direction_uses_the_declared_galactic_frame():
    origin = SkyCoord(10*u.deg, 20*u.deg, frame='icrs')
    moved = offset_center({'Long Offset': '10', 'Lat Offset': '0',
                           'Mos. Coord.': 'galactic'})
    assert origin.separation(moved).arcsec == pytest.approx(10, abs=1e-8)
    # East in the declared offset frame, which is not east in ICRS.
    assert bearing_error(origin.galactic, moved.galactic, 90) == pytest.approx(0, abs=1e-6)


def test_profile_is_opt_in_and_archive_plan_does_not_change():
    v = validation()
    from alma_duplicate.search_plan import build_search_plan
    base, new = build_search_plan(v), build_search_plan(v, queue_candidate_beam=True)
    assert base.for_source('ARCHIVE') == new.for_source('ARCHIVE')
    q = queue_rows({'RA':'10','Dec':'20'})
    old = search_candidates(v, queue_result=q)
    assert spatial(old).status == 'NOT_EVALUATED'


def test_both_sources_preserve_full_evaluation_scope_and_archive_binding():
    v = validation(ra=10,dec=20)
    from alma_duplicate.search_plan import build_search_plan
    a, _ = archive(build_search_plan(v,queue_candidate_beam=True),s_ra=10.,s_dec=20.,region='CIRCLE ICRS 10 20 0.01')
    q = queue_rows({'RA':'10','Dec':'20'}, {'RA':'10','Dec':'20','Use 7-m?':'True'})
    v = replace(v, search_options=replace(v.search_options,result_limit=1))
    result = search_candidates(v,archive_result=a,queue_result=q,queue_candidate_beam=True)
    report = evaluate_candidate_search(result)
    assert result.archive.query_binding.status == 'MATCHED'
    assert result.total_retained == len(report.context_evaluations) == 3
    assert len(result.candidates) == 1


@pytest.mark.parametrize('width', [1900.,1920.,1950.,1999.])
def test_current_portal_interval_mapping_is_retained(width):
    # Checked against the downloaded current script, not the older Cycle 5 code.
    assert map_nominal_to_usable_mhz(width)[0] == 1875.


def test_production_cli_real_fixture(tmp_path):
    out = tmp_path/'report.json'
    assert main(['--request',str(REQUEST),'--queue-csv',str(QUEUE),
                 '--queue-candidate-beam','--output',str(out)]) == 0
    p = json.loads(out.read_text())
    q = p['sources']['QUEUE']
    assert q['source_metadata']['snapshot']['snapshot_sha256'] == hashlib.sha256(QUEUE.read_bytes()).hexdigest()
    assert q['rows'][0]['filters'][0]['spatial']['status'] == 'INSIDE'
    assert p['request_criteria'][0]['outcome'] == 'SATISFIED'
    assert p['context_evaluations'][0]['criteria'][0]['outcome'] == 'SATISFIED'
    assert p['evaluation_scope']['total_retained'] == p['evaluation_scope']['evaluated_contexts']
    assert p['evaluation_scope']['display_truncated'] is True
    assert p['assessment'] == 'NOT_AGGREGATED'
    assert p['plan']['queue_candidate_beam'] is True


def test_mutually_exclusive_profiles(tmp_path):
    assert main(['--request',str(REQUEST),'--queue-csv',str(QUEUE),'--queue-candidate-beam',
                 '--beam-decision-ref','legacy','--output',str(tmp_path/'out.json')]) == 2


def test_zero_reference_is_preserved_and_negative_rejected():
    q = queue_rows({'RA':'10','Dec':'20','Ref.Frequency':'0'})
    assert q.can_reconstruct
    assert q.row_inputs[0].spectral.sensitivity.reference_frequency_ghz.value == 0
    assert not queue_rows({'Ref.Frequency':'-1'}).can_reconstruct


def test_frequency_fallback_uses_doppler_corrected_candidate_values():
    r = search({'Ref.Frequency':'0', 'Is Sky Freq?':'False',
                'Velocity':'3000', 'Vel. Convention':'RADIO', 'Vel. Frame':'lsrk'})
    assert spatial(r).beam_frequency_ghz == pytest.approx(343.5 * (1-3000/299792.458))


def test_offset_near_pole_remains_finite():
    q = queue_rows({'RA':'359.999','Dec':'89.999','Mosaic':'N/A','Long Offset':'5'})
    result = search_candidates(validation(ra=359.999,dec=89.999),queue_result=q,queue_candidate_beam=True)
    e = result.queue.rows[0].spatial_evidence
    assert 0 <= e.center.ra_deg < 360
    assert -90 <= e.center.dec_deg <= 90
    assert spatial(result).separation_deg * 3600 == pytest.approx(5,abs=1e-6)


def test_profile_requires_selected_queue():
    with pytest.raises(ValueError,match='requires QUEUE'):
        search_candidates(validation(sources=('ARCHIVE',)),queue_candidate_beam=True)
