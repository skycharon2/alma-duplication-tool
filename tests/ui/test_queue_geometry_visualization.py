"""Saved evidence controls Queue geometry drawing; never calculate new matches."""
from copy import deepcopy

from alma_duplicate.ui.queue_geometry_visualization import (
    MAX_ARRAY_BEAMS, queue_geometry_visualization_data,
)


def sample():
    points = [dict(id='a', ra_deg=.001, dec_deg=0., frame='ICRS'),
              dict(id='b', ra_deg=359.999, dec_deg=0., frame='ICRS')]
    candidate = dict(candidate_id='candidate-1', group=dict(project_code='2025.1.TEST', target_name='Test'),
        science=dict(model_status='PROVISIONAL', scientific_candidate_completeness='NOT_ESTABLISHED',
            branches=[dict(branch='CONTINUUM', truth='TRUE', status='CRITERIA_MET')],
            variants=[dict(diameter_m=12., branches=[dict(branch='CONTINUUM', truth='TRUE', status='CRITERIA_MET')])]),
        position=dict(snapshot_sha256='abc', source_row_ids=['abc:1'],
            beam_variants=[dict(diameter_m=12., radius_arcsec=12., outcome='SATISFIED', reasons=[],
                points=[dict(matched_point_ids=['a'])],
                coverage=dict(candidate_id='candidate-1', snapshot_sha256='abc',
                    source_row_ids=['abc:1'], association_confirmed=True, complete=True, diameter_m=12.,
                    frequency_ghz=230., points=points))]))
    return dict(page=1, pages=1, result_view='matching', visible_count=1,
                document=dict(sources={'QUEUE':dict(status='COMPLETE')},
                    geometry_reports=dict(RECTANGLE=dict(candidates=[candidate]))))


def test_reads_only_saved_per_array_coordinates_and_radius():
    raw = sample()
    before = deepcopy(raw)
    view = queue_geometry_visualization_data(raw, [0.,0.])
    assert raw == before
    assert len(view['rows']) == 1
    item = view['rows'][0]
    assert item['kind'] == 'RECTANGLE' and item['model_status'] == 'PROVISIONAL'
    v = item['variants'][0]
    assert v['science'][0]['truth'] == 'TRUE'
    assert v['geometry']['point_count'] == 2
    assert v['geometry']['radius_arcsec'] == 12
    assert v['geometry']['points'][0]['covers_proposed']
    assert not v['geometry']['points'][1]['covers_proposed']
    assert v['geometry']['points'][1]['offset'][0] > 0
    assert v['geometry']['points'][0]['offset'][0] < 0
    assert len(v['geometry']['points'][0]['outline']) == 73


def test_missing_or_unconfirmed_coverage_never_drawn():
    for change in ({'complete':False}, {'association_confirmed':False}, {'frequency_ghz':None}):
        raw = sample()
        raw['document']['geometry_reports']['RECTANGLE']['candidates'][0]['position']['beam_variants'][0]['coverage'].update(change)
        result = queue_geometry_visualization_data(raw, [0.,0.])['rows'][0]['variants'][0]['geometry']
        assert result['available'] is False and result['points'] == []


def test_invalid_and_oversize_arrays_not_partially_drawn():
    raw = sample()
    points = raw['document']['geometry_reports']['RECTANGLE']['candidates'][0]['position']['beam_variants'][0]['coverage']['points']
    points[1]['frame'] = 'Galactic'
    result = queue_geometry_visualization_data(raw, [0.,0.])['rows'][0]['variants'][0]['geometry']
    assert not result['available'] and not result['points']
    points[1]['frame'] = 'ICRS'
    points[:] = [dict(id=str(i), ra_deg=.001, dec_deg=0., frame='ICRS') for i in range(MAX_ARRAY_BEAMS+1)]
    result = queue_geometry_visualization_data(raw, [0.,0.])['rows'][0]['variants'][0]['geometry']
    assert not result['available'] and not result['points']
    assert 'budget' in result['reason']


def test_no_candidate_or_invalid_origin():
    raw = sample()
    v = queue_geometry_visualization_data(raw, None)['rows'][0]['variants'][0]['geometry']
    assert not v['available']
    raw['document']['geometry_reports'] = {}
    assert queue_geometry_visualization_data(raw, [0.,0.])['rows'] == []


def test_foreign_candidate_binding_cannot_be_drawn():
    raw = sample()
    coverage = raw['document']['geometry_reports']['RECTANGLE']['candidates'][0]['position']['beam_variants'][0]['coverage']
    coverage['candidate_id'] = 'another-candidate'
    result = queue_geometry_visualization_data(raw, [0., 0.])['rows'][0]['variants'][0]['geometry']
    assert not result['available'] and not result['points']
    assert 'bound' in result['reason']


def test_outside_display_hemisphere_never_gets_fake_footprint():
    # The fixture's 0/360-degree beams are more than 90 degrees from this
    # unrelated request. Geometry must not be silently forced into the map.
    view = queue_geometry_visualization_data(sample(), [201.365, -43.019])
    footprint = view['rows'][0]['variants'][0]['geometry']
    assert footprint['available'] is False
    assert footprint['points'] == []
    assert 'hemisphere' in footprint['reason']
