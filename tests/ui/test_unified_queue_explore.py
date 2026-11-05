"""Existing Explore rows and Queue Mosaic branches share one selection model."""
from copy import deepcopy

from alma_duplicate.ui.queue_geometry_visualization import queue_geometry_visualization_data
from alma_duplicate.ui.unified_queue_visualization import merge_queue_matches
from tests.ui.test_queue_geometry_visualization import sample


def base():
    return dict(rows=[dict(id='archive', label='Archive match', source='ARCHIVE',
                spatial={'available': True}, spectral={'available': False})],
        total=1, start=1, stop=1, plot_pages=1, plot_page=1,
        spatial_available=1, spectral_available=0)


def test_queue_rectangle_shares_archive_explore_rows_without_mutating_report():
    report=sample()
    before=deepcopy(report)
    queue=queue_geometry_visualization_data(report, [0.,0.])
    visual=merge_queue_matches(base(), queue, details_url='/runs/example/queue?page=1')
    assert report == before
    assert len(visual['rows']) == 2
    a,q=visual['rows']
    assert a['id']=='archive'
    assert q['identity']['Project']=='2025.1.TEST'
    assert q['geometry_kind']=='RECTANGLE'
    assert q['source']=='QUEUE' and q['intent']=='CONTINUUM'
    assert q['array_diameter_m']==12.
    assert q['details_url']=='/runs/example/queue?page=1'
    assert q['spatial']['available'] and len(q['spatial']['beams'])==2
    assert q['spatial']['covered_beam_count']==1
    assert q['spatial']['center'] is None  # not a fictitious single pointing
    assert visual['spatial_available']==2


def test_not_matching_array_is_not_promoted_to_explore_match():
    report=sample()
    candidate=report['document']['geometry_reports']['RECTANGLE']['candidates'][0]
    candidate['science']['variants'][0]['branches'][0]['truth']='FALSE'
    queue=queue_geometry_visualization_data(report, [0.,0.])
    visual=merge_queue_matches(base(), queue)
    assert [r['source'] for r in visual['rows']]==['ARCHIVE']


def test_unresolved_geometry_keeps_candidate_without_imaginary_beam():
    report=sample()
    candidate=report['document']['geometry_reports']['RECTANGLE']['candidates'][0]
    candidate['position']['beam_variants'][0]['coverage']['complete']=False
    queue=queue_geometry_visualization_data(report, [0.,0.])
    visual=merge_queue_matches(base(), queue)
    row=visual['rows'][1]
    assert row['spatial']['available'] is False
    assert not row['spatial']['beams']
    assert 'incomplete' in row['spatial']['reason']


def test_same_queue_candidate_separate_array_matches():
    report=sample()
    candidate=report['document']['geometry_reports']['RECTANGLE']['candidates'][0]
    position=deepcopy(candidate['position']['beam_variants'][0])
    position['diameter_m']=7.
    position['coverage']['diameter_m']=7.
    candidate['position']['beam_variants'].append(position)
    variant=deepcopy(candidate['science']['variants'][0])
    variant['diameter_m']=7.
    candidate['science']['variants'].append(variant)
    queue=queue_geometry_visualization_data(report, [0.,0.])
    visual=merge_queue_matches(base(), queue)
    assert [r['array_diameter_m'] for r in visual['rows'][1:]] == [12.,7.]
    assert len({r['id'] for r in visual['rows']})==3
