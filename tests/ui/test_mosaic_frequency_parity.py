"""P0.5: no inferred spectral windows, cross-candidate mixing or rule changes."""
from copy import deepcopy

from alma_duplicate.ui.mosaic_visualization import (
    _archive_spectral_setup, _queue_spectral_setup, spectral_overview,
)
from tests.ui.test_queue_geometry_visualization import sample


def archive_context():
    reference = {'source': 'ARCHIVE', 'raw_row_id': 'raw-9', 'component_index': 1,
                 'source_record_id': 'source-1'}
    return {
        'source_reference': reference,
        'display_identity': {'Member OUS': 'member-1', 'ASDM': 'asdm-1', 'Target': 'target-1'},
        'spectral_setup_display': {'reference': deepcopy(reference), 'evidence': {
            'raw_row_id': 'raw-9', 'parse_result': {'parser_version': 'fixture', 'components': [
                {'component_index': 0, 'parse_status': 'PARSED', 'validation_issues': [],
                 'frequency_interval': {'low': 229., 'high': 230., 'unit': 'GHz'}},
                {'component_index': 1, 'parse_status': 'PARSED', 'validation_issues': [],
                 'frequency_interval': {'low': 231., 'high': 232., 'unit': 'GHz'}},
                {'component_index': 2, 'parse_status': 'UNPARSED', 'validation_issues': ['fixture'],
                 'frequency_interval': None},
            ]}},
        },
    }


def test_archive_setup_uses_exact_row_binding_and_preserves_gaps():
    context = archive_context()
    original = deepcopy(context)
    setup = _archive_spectral_setup(context)
    assert context == original
    assert setup['source'] == 'Archive'
    assert len(setup['components']) == 3
    overview = spectral_overview([dict(available=True, kind='interval',
        proposed=231.5, low=231.2, high=231.8, spw='25')], setup)
    assert len(overview['setup_rows']) == 3
    assert overview['setup_rows'][0]['high'] < overview['setup_rows'][1]['low']
    assert overview['setup_rows'][2]['low'] is None
    assert overview['rows'][0]['spw'] == '25'
    # Do not invent components when the raw row or context reference differs.
    context['spectral_setup_display']['evidence']['raw_row_id'] = 'unrelated'
    assert _archive_spectral_setup(context) is None


def test_queue_setup_requires_candidate_and_snapshot_and_source_row_binding():
    page = sample()
    candidate = page['document']['geometry_reports']['RECTANGLE']['candidates'][0]
    science = candidate['science']
    science['spectral_setup_display'] = {
        'schema_version': 'mosaic_queue_regular_spws_display_1',
        'candidate_id': candidate['candidate_id'],
        'snapshot_sha256': 'abc',
        'source_row_ids': ['abc:1'],
        'representative_source_row_id': 'abc:1',
        'spws': [{'number': 1, 'nominal_low_ghz': 240, 'nominal_high_ghz': 242,
                  'usable_low_ghz': None, 'usable_high_ghz': None},
                 {'number': 2, 'nominal_low_ghz': 244, 'nominal_high_ghz': 246,
                  'usable_low_ghz': None, 'usable_high_ghz': None}],
    }
    candidate['source_rows'] = [{'source_row_id': 'abc:1'}]
    snapshot = deepcopy(candidate)
    setup = _queue_spectral_setup(candidate)
    assert candidate == snapshot
    assert len(setup['components']) == 2
    overview = spectral_overview([dict(available=True, kind='representative',
        proposed=241, candidate=241)], setup)
    assert overview['setup_rows'][0]['high'] < overview['setup_rows'][1]['low']
    science['spectral_setup_display']['snapshot_sha256'] = 'foreign-snapshot'
    assert _queue_spectral_setup(candidate) is None
    science['spectral_setup_display']['snapshot_sha256'] = 'abc'
    science['spectral_setup_display']['candidate_id'] = 'foreign-candidate'
    assert _queue_spectral_setup(candidate) is None


def test_legacy_missing_setup_falls_back_to_saved_matching_comparisons():
    spectra = [dict(available=True, kind='interval', proposed=690, low=689, high=691, spw=25),
               dict(available=False, result='No saved spectral comparison')]
    before = deepcopy(spectra)
    chart = spectral_overview(spectra)
    assert len(chart['rows']) == 1 and chart['rows'][0]['spw'] == 25
    assert not chart['setup_rows']
    assert 'not retained' in chart['setup_note']
    assert spectra == before
    assert spectral_overview([dict(available=False)], None) is None


def test_unbounded_setup_is_not_partially_plotted():
    many = {'label': 'test', 'components': [dict(label=str(i), low=230., high=231.)
                                           for i in range(129)]}
    view = spectral_overview([dict(available=True, kind='representative',
        proposed=230, candidate=230)], many)
    assert not view['setup_rows']
    assert '128' in view['setup_note']


def test_archive_candidate_sidecar_is_read_without_changing_scientific_context():
    from alma_duplicate.ui.mosaic_visualization import archive_rows
    context = dict(context_id='c1', branches=[dict(branch='LINE', status='CRITERIA_MET')],
                   criteria=[], line_pairs=[], coverage={})
    saved_context = deepcopy(context)
    sidecar = archive_context()
    page = {'candidate_entries': [dict(candidate_index=0,
        candidate=dict(member_ous_uid='member-1', source_name='target-1',
                       metadata_rows=[], spectral_setup_displays={'c1': sidecar}),
        contexts=[dict(index=0, record=context)])]}
    result = list(archive_rows(page))
    assert len(result) == 1
    assert result[0]['spectral_setup']['source'] == 'Archive'
    assert len(result[0]['spectral_setup']['components']) == 3
    assert context == saved_context
    # A foreign context key must not leak another candidate's spectral setup.
    page['candidate_entries'][0]['candidate']['spectral_setup_displays'] = {'foreign': sidecar}
    assert list(archive_rows(page))[0]['spectral_setup'] is None


def test_setup_disclosure_coordinates_use_compact_summary_and_separate_rows():
    setup = _archive_spectral_setup(archive_context())
    overview = spectral_overview([dict(available=True, kind='interval',
        proposed=231.5, low=231.2, high=231.8, spw=25)], setup)
    assert overview['collapsed_height'] == 154
    assert overview['height'] > overview['collapsed_height']
    assert overview['setup_rows'][0]['y'] > 100  # clear of the compact Setup row
    assert overview['matching_label_y'] > overview['setup_rows'][-1]['y']
    assert overview['rows'][0]['y'] > overview['matching_label_y']
    assert overview['valid_setup_count'] == 2
