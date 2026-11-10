"""Keep text, charts and sky aligned with saved source-specific evidence."""
from copy import deepcopy

from alma_duplicate.ui import create_app
from alma_duplicate.ui.mosaic_visualization import archive_rows, _evidence, position_chart
from alma_duplicate.ui.mosaic_sky_preview import sky_preview


def archive_page():
    circle = dict(field_id='ctx', ra_deg=0., dec_deg=0., radius_arcsec=10., metadata_context_ids=['ctx'])
    coverage = dict(candidate_geometry='SINGLE_POINTING', circles=[circle], inside_count=1,
                    pointing_count=1, probes=dict(points=[dict(id='p', ra_deg=0., dec_deg=0., status='INSIDE')]))
    ctx = dict(context_id='ctx', coverage=coverage, branches=[dict(branch='CONTINUUM', status='CRITERIA_MET')],
               criteria=[dict(criterion_id='POS-MOSAIC', method_version='archive_pos_mosaic_single_candidate_1')])
    return dict(candidate_entries=[dict(candidate=dict(member_ous_uid='member', source_name='target'),
                                        candidate_index=0, contexts=[dict(index=0, record=ctx)])])


def test_legacy_archive_bound_single_field_renders_without_mutating_saved_evidence():
    page = archive_page()
    original = deepcopy(page)
    row = next(archive_rows(page))
    proposed = dict(points=[dict(id='p', frame='ICRS', ra_deg=0., dec_deg=0.)])
    chart = position_chart(row, proposed)
    assert chart['available'] and len(chart['outlines']) == 1
    assert sky_preview(row, proposed, chart)['candidate']['kind'] == 'beams'
    assert page == original
    circle = page['candidate_entries'][0]['contexts'][0]['record']['coverage']['circles'][0]
    circle['metadata_context_ids'] = ['foreign']
    assert not position_chart(next(archive_rows(page)), proposed)['available']
    circle.update(metadata_context_ids=['ctx'], frame='Galactic')
    assert not position_chart(next(archive_rows(page)), proposed)['available']


def test_queue_line_identity_and_pair_index_survive_projection():
    pairs = [dict(truth='FALSE'), dict(truth='TRUE', reference=dict(proposed_window_id='line-3', spw_number=25), criteria=[])]
    view = _evidence(dict(branch='LINE', status='CRITERIA_MET'), [], pairs)
    assert view['spectra'][0]['window'] == 'line-3'
    assert view['spectra'][0]['spw'] == 25
    assert view['spectra'][0]['pair_index'] == 1


def test_single_field_text_uses_beam_label_and_nested_point_evidence():
    app = create_app(dict(TESTING=True, AUTO_QUEUE=False))
    coverage = archive_page()['candidate_entries'][0]['contexts'][0]['record']['coverage']
    with app.app_context():
        template = app.jinja_env.from_string("{% from '_mosaic_matching.html' import coverage_view with context %}{{ coverage_view(coverage) }}")
        html = template.render(coverage=coverage, display_number=str)
    assert 'half-power beam union' in html
    assert 'Archive s_region' not in html
    assert 'Point-by-point evidence' in html and 'INSIDE' in html
    assert 'Outside: Unknown' in html and 'Unknown: Unknown' in html
