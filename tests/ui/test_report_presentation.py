"""Report presentation preserves scientific decisions and original evidence."""
from copy import deepcopy

from alma_duplicate.ui.report_view import (
    context_identity, criterion_view, display_number, report_summary,
)


def test_comparable_rms_is_backend_derived_and_missing_is_not_raw_rms():
    record = {'criterion_id': 'LINE-RMS', 'proposed': {'value': 20, 'unit': 'mJy/beam'},
              'candidate': {'value': 6.3, 'unit': 'mJy/beam'},
              'derived': [['sigma_comp_mjy_beam', 19.10611373013061]]}
    original = deepcopy(record)
    assert criterion_view(record)['candidate']['value'] == 19.10611373013061
    assert record == original
    record['derived'] = [['sigma_comp_mjy_beam', None]]
    assert criterion_view(record)['candidate']['value'] is None
    assert display_number(19.10611373013061) == '19.1061'
    assert display_number(0.00000000012345) != '0'


def test_stored_identity_zero_spw_and_legacy_fallback():
    context = {'display_identity': {'Target': '<script>', 'Project': 'P1', 'SPW': 0}}
    assert ('SPW', '0') in context_identity(context)
    assert ('Target', '<script>') in context_identity(context)  # Jinja escapes at rendering.
    assert context_identity({'reference': {'component_index': 3}}) == []


def test_summary_counts_context_branches_not_beam_variants_or_pair_rows():
    context = {'branches': [{'branch': 'LINE', 'status': 'CRITERIA_MET'}],
               'beam_variants': [{'branches': [{'branch': 'LINE', 'status': 'CRITERIA_NOT_MET'}]}],
               'line_pairs': [{'status': 'CRITERIA_MET'}, {'status': 'CRITERIA_NOT_MET'}]}
    doc = {'request': {'normalized': {'target_name': 'test', 'intents': ['LINE']}},
           'context_evaluations': [context, {'branches': []}]}
    original = deepcopy(doc)
    summary = report_summary(doc)
    assert summary['counts'] == [{'intent': 'LINE', 'met': 1, 'not_met': 0,
                                  'review': 0, 'unreported': 1}]
    assert doc == original
