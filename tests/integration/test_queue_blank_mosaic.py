"""Portal blank-Mosaic interpretation is confined to current formal methods."""

import math
from dataclasses import replace

import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.domain.queue import QueueMosaicKind
from alma_duplicate.queue_line_pairing import build_queue_line_pairs
from alma_duplicate.queue_position import adapt_queue_position
from tests.integration.test_queue_common import case
from tests.integration.test_queue_continuum import case as continuum_case, rule
from tests.integration.test_queue_line_pairing import contexts, request


@pytest.mark.parametrize('frame', ['', 'ICRS', 'J2000', 'galactic'])
def test_blank_offset_uses_spherical_transport_and_preserves_raw_parser(frame):
    s, (angular, position) = case({'Mosaic': '', 'Long Offset': '3',
                                  'Lat Offset': '4', 'Mos. Coord.': frame})
    row = s.queue.rows[0]
    assert row.context.evidence.row.spatial.mosaic_kind is QueueMosaicKind.UNSPECIFIED_WITH_OFFSET
    assert row.context.evidence.row.raw_row.value('Mosaic') == ''
    assert angular.method_version == 'queue_angular_factor_8'
    assert position.method_version == 'queue_pos_single_7'
    assert position.outcome == 'SATISFIED'
    assert 'PORTAL_BLANK_MOSAIC_SINGLE_POINTING' in position.reasons
    assert 'QUEUE_GEOMETRY_UNSUPPORTED' not in position.reasons
    center = SkyCoord(10*u.deg, 20*u.deg, frame='icrs')
    native = center.galactic if frame == 'galactic' else center
    expected = native.directional_offset_by(math.atan2(3, 4)*u.rad, 5*u.arcsec).icrs
    derived = dict(position.derived)
    assert derived['candidate_ra_deg'] == pytest.approx(expected.ra.deg)
    assert derived['candidate_dec_deg'] == pytest.approx(expected.dec.deg)
    assert dict(position.details)['geometry_interpretation'] == 'PORTAL_BLANK_MOSAIC_SINGLE_POINTING'
    assert 'docs/queue_blank_mosaic.md' in position.decision_refs
    legacy = adapt_queue_position(row.context, s.queue.source_record)
    assert legacy.selection_status != 'AVAILABLE'


@pytest.mark.parametrize('changes', [
    {'Mosaic': 'Custom'}, {'Mosaic': 'Rectangle', 'Mos. Length': '60', 'Mos. Width': '60', 'Mos. PA': '0', 'Mos. Spacing': '0.5', 'Mos. Coord.': 'ICRS'},
    {'Mos. Coord.': 'B1950'}, {'RA': '0', 'Dec': '0'},
    {'Long Offset': '324000'},
])
def test_new_interpretation_does_not_bypass_geometry_frame_or_coordinate_guards(changes):
    _, (_, position) = case({'Mosaic': '', 'Long Offset': '3', 'Lat Offset': '4'} | changes)
    assert position.outcome is None


def test_blank_offset_continuum_and_line_use_same_scope():
    s, _, c = continuum_case({'Mosaic': '', 'Long Offset': '1', 'Lat Offset': '0'})
    assert c.branches[0].status == 'CRITERIA_MET'
    assert rule(c, 'POS-SINGLE').method_version == 'queue_pos_single_7'
    c = contexts({'Mosaic': '', 'Long Offset': '1'})[0]
    pairs = build_queue_line_pairs(request(), c)
    assert pairs.builder_version == 'queue_line_pair_builder_2'
    assert 'QUEUE_SINGLE_FIELD_REQUIRED' not in pairs.reasons
    assert all('QUEUE_SINGLE_FIELD_REQUIRED' not in p.reasons for p in pairs.attempts)
    # No source geometry is relabelled by pair preparation.
    assert c.evidence.row.spatial.mosaic_kind is QueueMosaicKind.UNSPECIFIED_WITH_OFFSET
    custom = contexts({'Mosaic': 'Custom', 'Long Offset': '1'})[0]
    assert 'QUEUE_SINGLE_FIELD_REQUIRED' in build_queue_line_pairs(request(), custom).reasons


def test_interpretation_requires_both_raw_blank_and_expected_parser_category():
    from alma_duplicate.queue_pointing_scope import is_queue_single_point
    row = contexts({'Mosaic': 'Custom', 'Long Offset': '1'})[0].evidence.row
    inconsistent = replace(row, spatial=replace(row.spatial, mosaic_kind=QueueMosaicKind.UNSPECIFIED_WITH_OFFSET))
    assert not is_queue_single_point(inconsistent)
