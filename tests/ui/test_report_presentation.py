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


def test_explanations_use_recorded_outcome_and_do_not_recalculate():
    from alma_duplicate.ui.report_view import criterion_explanation, criterion_status
    # Deliberately inconsistent operands: the viewer must not become another evaluator.
    record = {'criterion_id': 'ANGULAR', 'outcome': 'SATISFIED',
              'eligible_for_formal_aggregation': True,
              'proposed': {'value': 1}, 'candidate': {'value': 999}, 'reasons': []}
    assert criterion_status(record) == 'Condition met'
    assert 'meet the allowed' in criterion_explanation(record)
    record['eligible_for_formal_aggregation'] = False
    assert criterion_status(record) == 'Needs review'
    assert 'not eligible' in criterion_explanation(record)
    record.update(evaluation='NOT_APPLICABLE', outcome=None)
    assert criterion_status(record) == 'Not applicable'
    assert 'does not apply' in criterion_explanation(record)


def test_unknown_reason_is_not_translated_into_scientific_or_input_claim():
    from alma_duplicate.ui.report_view import criterion_explanation, attention_groups
    r = {'criterion_id': 'FUTURE', 'outcome': None, 'reasons': ['FUTURE_REASON']}
    assert criterion_view(r)['label'] == 'Additional criterion'
    assert 'does not establish a result' in criterion_explanation(r)
    doc = {'context_evaluations': [{'context_id': 'c'}]}
    inspection = {'gap_occurrences': [{'code': 'FUTURE_REASON', 'category': 'UNCLASSIFIED', 'context_id': 'c'}]}
    original = deepcopy(inspection)
    groups = attention_groups(doc, inspection)
    assert groups[0]['candidates'] == [0]
    assert 'without a recognized explanation' in groups[0]['messages'][0]
    assert inspection == original


def test_attention_links_include_candidates_beyond_current_page():
    from alma_duplicate.ui.report_view import attention_groups, pair_title
    doc = {'context_evaluations': [{'context_id': str(i)} for i in range(21)]}
    gap = {'code': 'PLANNED_LINE_RMS_REQUIRED', 'category': 'USER_INPUT_MISSING', 'context_id': '20'}
    groups = attention_groups(doc, {'gap_occurrences': [gap, gap]})
    assert groups[0]['count'] == 2  # Evidence occurrences, not two candidate verdicts.
    assert groups[0]['candidates'] == [20]
    assert groups[0]['messages'] == ['Enter the planned RMS for this proposed line.']
    assert pair_title({'attempt': {'reference': {'proposed_window_id': 'CO', 'candidate_association': {'spw_token': 0}}}}) == 'Requested line / candidate window 0'


def test_source_summary_does_not_turn_zero_hits_or_failure_into_negative_result():
    from alma_duplicate.ui.report_view import source_overview
    doc = {'sources': {'ARCHIVE': {'status': 'COMPLETED', 'array_evidence': {
        'record_count': 0, 'acquisition': {'status': 'COMPLETED'}}}, 'QUEUE': {'status': 'NOT_SELECTED'}}}
    summary = source_overview(doc)
    assert len(summary) == 1
    assert 'does not mean there is no duplication' in summary[0]['notes'][-1]
    doc['sources']['ARCHIVE']['array_evidence']['acquisition']['status'] = 'FAILED'
    assert source_overview(doc)[0]['attention']
    assert 'unresolved' in source_overview(doc)[0]['notes'][-1]


def test_only_identical_common_records_are_suppressed_for_line_only_display():
    from alma_duplicate.ui.report_view import standalone_criteria
    common = {'criterion_id': 'POS-SINGLE', 'outcome': 'SATISFIED'}
    scope = {'criteria': [common], 'branches': [{'branch': 'LINE'}],
             'line_pairs': [{'criteria': [deepcopy(common)]}]}
    original = deepcopy(scope)
    assert standalone_criteria(scope) == []
    assert scope == original
    scope['line_pairs'].append({'criteria': []})
    assert standalone_criteria(scope) == [common]
    scope['line_pairs'].pop()
    scope['branches'].append({'branch': 'CONTINUUM'})
    assert standalone_criteria(scope) == [common]


def test_findings_describe_stored_results_without_claiming_search_completeness():
    doc = {'request': {'normalized': {'intents': ['LINE', 'CONTINUUM']}},
           'context_evaluations': [{'branches': [
               {'branch': 'LINE', 'status': 'CRITERIA_MET'},
               {'branch': 'CONTINUUM', 'status': 'CRITERIA_NOT_MET'}]}]}
    assert 'were found' in report_summary(doc)['findings'][0]['text']
    assert 'None of the evaluated candidates' in report_summary(doc)['findings'][1]['text']
    doc['context_evaluations'][0]['branches'][0]['status'] = 'FUTURE_STATUS'
    summary = report_summary(doc)
    assert summary['counts'][0]['review'] == 1
    assert 'unresolved' in summary['findings'][0]['text']
    doc['context_evaluations'][0]['branches'] = []
    assert 'unresolved' in report_summary(doc)['findings'][0]['text']
    doc['context_evaluations'] = []
    assert all('No evaluated candidates' in f['text'] for f in report_summary(doc)['findings'])


def test_match_selection_uses_requested_parent_branches_and_never_pairs_or_variants():
    from alma_duplicate.ui.report_view import matching_contexts
    positive = {'branch': 'LINE', 'status': 'CRITERIA_MET'}
    doc = {'request': {'normalized': {'intents': ['LINE', 'CONTINUUM']}}, 'context_evaluations': [
        {'branches': [positive, {'branch': 'CONTINUUM', 'status': 'INDETERMINATE'}]},
        {'branches': [{'branch': 'LINE', 'status': 'CRITERIA_NOT_MET'}],
         'line_pairs': [{'status': 'CRITERIA_MET'}], 'beam_variants': [{'branches': [positive]}]},
        {'branches': [{'branch': 'LINE', 'status': 'FUTURE_STATUS'}]},
        {'branches': []},
        {'branches': [{'branch': 'CONTINUUM', 'status': 'CRITERIA_MET'}]},
    ]}
    original = deepcopy(doc)
    assert [i for i, _ in matching_contexts(doc)] == [0, 4]
    assert doc == original
    doc['request']['normalized']['intents'] = ['LINE']
    assert [i for i, _ in matching_contexts(doc)] == [0]


def test_member_groups_keep_target_execution_associations_and_every_spw_context():
    from alma_duplicate.ui.report_view import member_groups
    def context(member, target, execution, spw=0):
        return {'reference': {'source': 'ARCHIVE'}, 'display_identity': {
            'Member OUS': member, 'Target': target, 'ASDM': execution, 'SPW': spw,
            'Project': 'P'}, 'branches': [{'branch': 'LINE', 'status': 'CRITERIA_MET'}]}
    entries = list(enumerate([
        context('M1', 'A', 'E1'), context('M2', 'A', 'E1'),
        context('M1', 'B', 'E1'), context('M1', 'A', 'E2'),
        context('M1', 'A', 'E1', 1), context('M1', 'A', 'E1', 0),
    ]))
    original = deepcopy(entries)
    groups = member_groups(entries)
    assert [g['member'] for g in groups] == ['M1', 'M2']
    assert [[i for i, _ in child['entries']] for child in groups[0]['children']] == [[0, 4, 5], [2], [3]]
    assert [i for i, _ in groups[0]['entries']] == [0, 2, 3, 4, 5]
    assert groups[0]['children'][0]['entries'][0][1] is entries[0][1]
    assert entries == original


def test_grouping_never_guesses_missing_conflicting_or_cross_source_identities():
    from alma_duplicate.ui.report_view import member_groups
    base = {'reference': {'source': 'ARCHIVE'}, 'display_identity': {
        'Member OUS': 'M1', 'Target': 'A', 'ASDM': 'E1'}}
    conflicting = deepcopy(base)
    conflicting['array_evidence'] = {'records': [{'member_ous_uid': 'M2'}]}
    queue = deepcopy(base)
    queue['reference']['source'] = 'QUEUE'
    missing = {'reference': {'source': 'ARCHIVE'}, 'context_id': 'M1/source/A/spw/0'}
    entries = list(enumerate([base, conflicting, deepcopy(conflicting), missing, deepcopy(missing), queue, deepcopy(queue)]))
    assert len(member_groups(entries)) == 7
    missing_execution = deepcopy(base)
    del missing_execution['display_identity']['ASDM']
    ambiguous_target = deepcopy(base)
    ambiguous_target['array_evidence'] = {'records': [{'source_name': 'B', 'member_ous_uid': 'M1'}]}
    groups = member_groups(list(enumerate([base, missing_execution, deepcopy(missing_execution), ambiguous_target])))
    assert len(groups) == 1
    assert len(groups[0]['children']) == 4


def test_legacy_explicit_association_can_supply_member_and_execution():
    from alma_duplicate.ui.report_view import member_groups
    context = {'reference': {'source': 'ARCHIVE'}, 'line_pairs': [{'attempt': {'reference': {
        'candidate_association': {'context': {'member_ous_uid': 'M', 'source_name': 'S', 'asdm_uid': 'E'}, 'spw_token': 0}}}}]}
    group = member_groups([(9, context), (15, deepcopy(context))])[0]
    assert group['member'] == 'M'
    assert group['children'][0]['target'] == 'S'
    assert group['children'][0]['execution'] == 'E'
    assert [i for i, _ in group['children'][0]['entries']] == [9, 15]
