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


def test_queue_only_batch_counts_each_matching_array_without_a_legacy_range():
    visual = base()
    visual.update(rows=[], start=0, stop=0, total=0)
    report = sample()
    variant = report['document']['geometry_reports']['RECTANGLE']['candidates'][0]['science']['variants'][0]
    variant['branches'].append(dict(branch='LINE', truth='TRUE', status='CRITERIA_MET'))
    queue = queue_geometry_visualization_data(report, [0., 0.])
    merged = merge_queue_matches(visual, queue)
    assert (merged['start'], merged['stop'], merged['total']) == (0, 0, 0)
    assert merged['queue_comparison_count'] == 2
    assert len({row['display_number'] for row in merged['rows']}) == 2


def test_saved_queue_continuum_intervals_preserve_gaps_and_ignore_invalid_values():
    import json
    from alma_duplicate.ui.unified_queue_visualization import _spectral
    records = [dict(criterion_id='CONT-FREQ', proposed={'value':230., 'unit':'GHz'},
                    candidate={'value':231., 'unit':'GHz'}),
               dict(criterion_id='CONT-RMS', details=[['spw_evidence_json', json.dumps([
                   {'spw_number':1, 'usable_interval_ghz_exact':['229/1','230/1']},
                   {'spw_number':2, 'usable_interval_ghz_exact':['232/1','233/1']},
                   {'spw_number':3, 'usable_interval_ghz_exact':['bad','234']},
               ])]])]
    before = deepcopy(records)
    result = _spectral(records, 'CONTINUUM')
    assert [(c['low'],c['high']) for c in result['coverage']] == [(229.,230.),(232.,233.)]
    assert records == before
    assert _spectral(records[:1], 'CONTINUUM')['coverage'] == []


def test_all_matching_line_pairs_are_selectable_other_windows_are_reference_only():
    report = sample()
    variant = report['document']['geometry_reports']['RECTANGLE']['candidates'][0]['science']['variants'][0]
    variant['branches'] = [dict(branch='LINE', truth='TRUE', status='CRITERIA_MET')]
    variant['line_pairs'] = [dict(truth=truth, status=status,
        reference={'spw_number':i, 'proposed_window_id':'line-1'},
        criteria=[dict(criterion_id='LINE-COVERAGE', derived=[
            ['sky_frequency_ghz',230.], ['interval_low_ghz',low], ['interval_high_ghz',low+1]])])
        for i,truth,status,low in [(1,'TRUE','CRITERIA_MET',229.),
                                  (2,'TRUE','CRITERIA_MET',229.5),
                                  (3,'FALSE','CRITERIA_NOT_MET',240.)]]
    before = deepcopy(report)
    queue = queue_geometry_visualization_data(report,[0.,0.])
    rows = merge_queue_matches(base(),queue)['rows'][1:]
    assert [r['spw'] for r in rows] == [1,2]
    assert len({r['id'] for r in rows}) == 2
    assert rows[0]['queue_setup_key'] == rows[1]['queue_setup_key']
    assert [w['spw'] for w in rows[0]['spectral']['coverage']] == [1,2,3]
    assert report == before


def test_queue_text_report_separates_matching_and_other_pairs():
    from alma_duplicate.ui import create_app
    from flask import render_template, render_template_string
    report = sample()['document']
    variant = report['geometry_reports']['RECTANGLE']['candidates'][0]['science']['variants'][0]
    variant['line_pairs'] = [dict(truth=t,status=s,criteria=[],reference={
        'spw_number':i,'proposed_window_id':'line-1'}) for i,t,s in
        [(1,'TRUE','CRITERIA_MET'),(2,'FALSE','CRITERIA_NOT_MET'),(3,'UNKNOWN','UNRESOLVED')]]
    app = create_app({'TESTING':True, 'AUTO_QUEUE':False})
    with app.test_request_context():
        html = render_template('_queue_geometry_results.html',geometry_report=report,report_id='test')
    assert 'Matching LINE comparisons (1)' in html
    assert 'Other evaluated window pairs (2)' in html
    assert html.index('SPW 1') < html.index('Other evaluated window pairs') < html.index('SPW 2')
    assert 'UNRESOLVED' in html
    from alma_duplicate.ui.queue_browser import presentation
    with app.test_request_context():
        for template in ('_queue_matching.html', '_mosaic_queue_matching.html'):
            rendered = render_template_string(
                "{% from template import details with context %}{{ details(entries) }}",
                template=template, entries=presentation(report), status_labels={})
            assert 'Technical details and provenance' not in rendered
            assert 'Geometry method version' not in rendered
            assert 'Candidate ID:' not in rendered
            assert 'Matching LINE comparisons (1)' in rendered
            assert 'Other evaluated window pairs (2)' in rendered
            assert rendered.index('SPW 1') < rendered.index('Other evaluated window pairs') < rendered.index('SPW 2')
