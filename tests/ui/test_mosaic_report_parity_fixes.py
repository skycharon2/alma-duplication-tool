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


def test_archive_continuum_uses_stored_context_spw_identity_only():
    page = archive_page()
    ctx = page['candidate_entries'][0]['contexts'][0]['record']
    ctx['display_identity'] = {'SPW': 25}
    original = deepcopy(page)
    row = next(archive_rows(page))
    assert row['spectra'][0]['spw'] == 25
    assert page == original
    ctx['display_identity']['SPW'] = 'Not recorded'
    assert 'spw' not in next(archive_rows(page))['spectra'][0]
    ctx['display_identity'] = {}
    assert 'spw' not in next(archive_rows(page))['spectra'][0]


def test_queue_continuum_does_not_invent_spw_identity():
    row = _evidence(dict(branch='CONTINUUM', status='CRITERIA_MET'), [], [])
    assert 'spw' not in row['spectra'][0]


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


def test_archive_continuum_bound_coverage_survives_mosaic_projection():
    from alma_duplicate.ui.mosaic_visualization import spectral_overview
    from tests.ui.test_mosaic_frequency_parity import archive_context
    page = archive_page()
    entry = page['candidate_entries'][0]
    ctx = entry['contexts'][0]['record']
    saved = archive_context()
    ctx['source_reference'] = deepcopy(saved['source_reference'])
    ctx['display_identity'] = {'SPW': 25}
    ctx['criteria'].append(dict(criterion_id='CONT-FREQ', outcome='SATISFIED',
        proposed=dict(value=233., unit='GHz'), candidate=dict(value=231.5, unit='GHz')))
    entry['candidate']['spectral_setup_displays'] = {'ctx': saved}
    original = deepcopy(page)
    spectrum = next(archive_rows(page))['spectra'][0]
    assert [(c['low'], c['high']) for c in spectrum['coverage']] == [(231., 232.)]
    chart = spectral_overview([spectrum])  # Works even without a full setup display.
    interval = chart['rows'][0]['coverage'][0]
    assert interval['raw_low'] == 231. and interval['raw_high'] == 232.
    assert interval['low'] < chart['rows'][0]['low'] < interval['high']
    assert chart['ticks'][0]['value'] < 231 < 232 < chart['ticks'][-1]['value']
    assert page == original
    # A foreign raw row, missing binding, invalid or duplicate component must
    # never turn the setup-wide coverage into this comparison's coverage.
    for change in ('foreign', 'missing', 'invalid', 'duplicate'):
        broken = deepcopy(original)
        item = broken['candidate_entries'][0]
        context = item['contexts'][0]['record']
        sidecar = item['candidate']['spectral_setup_displays']['ctx']
        components = sidecar['spectral_setup_display']['evidence']['parse_result']['components']
        if change == 'foreign':
            sidecar['spectral_setup_display']['evidence']['raw_row_id'] = 'foreign'
        elif change == 'missing':
            context['source_reference'].pop('component_index')
        elif change == 'invalid':
            components[1]['validation_issues'] = ['invalid']
        else:
            components.append(deepcopy(components[1]))
        assert next(archive_rows(broken))['spectra'][0]['coverage'] == []


def test_queue_saved_widths_supply_nominal_and_usable_intervals_without_mutation():
    import json
    from alma_duplicate.ui.queue_spectral_display import continuum_windows
    window = dict(spw_number=1, usable_interval_ghz_exact=['99', '101'],
                  sky_frequency_ghz='100', nominal_bandwidth_mhz='4000')
    records = [dict(criterion_id='CONT-RMS', details=[
        ['spw_evidence_json', json.dumps([window])]])]
    assert continuum_windows(records) == [dict(low=99., high=101., bandwidth_ghz=2.,
        spw=1, nominal_low=98., nominal_high=102.)]
    window.pop('sky_frequency_ghz')
    records[0]['details'][0][1] = json.dumps([window])
    assert 'nominal_low' not in continuum_windows(records)[0]


def test_mosaic_projection_keeps_saved_usable_bounds():
    from alma_duplicate.ui.mosaic_frequency_view import spectral_overview
    result = spectral_overview([], dict(components=[dict(label='SPW 1', low=98., high=102.,
        usable_low=99., usable_high=101.)]))
    assert result['setup_rows'][0]['usable_low'] == 99.
    assert result['setup_rows'][0]['usable_high'] == 101.
