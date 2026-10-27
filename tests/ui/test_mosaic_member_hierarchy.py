"""PR D: positive-Member navigation retains recorded sibling targets and contexts."""

from copy import deepcopy
from pathlib import Path

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
import pytest

from alma_duplicate.ui.mosaic_report_pages import mosaic_report_page
from alma_duplicate.ui.mosaic_report_view import mosaic_report_projection


def _context(label, status, *, member='uid://member/A', target='target-A', spw=None):
    pairs = []
    if spw is not None:
        pairs.append({
            'status': status, 'criteria': [],
            'attempt': {'reference': {'candidate_association': {
                'context': {'member_ous_uid': member, 'source_name': target,
                            'asdm_uid': 'uid://execution/1'},
                'spw_token': str(spw),
            }}},
        })
    return {'context_id': label, 'branches': [{'branch': 'LINE', 'status': status}],
            'criteria': [], 'request_criteria': [], 'line_pairs': pairs}


def _candidate(target, statuses, *, member='uid://member/A', metadata=True):
    result = {'member_ous_uid': member, 'source_name': target,
              'status': 'EVALUATED', 'evaluation': {'contexts': [
                  _context(f'{target}-{i}', status, member=member,
                           target=target, spw=25 + 2*i)
                  for i, status in enumerate(statuses)
              ]}}
    if metadata:
        result['metadata_rows'] = [{
            'proposal_id': '2018.1.00294.S', 'group_ous_uid': 'uid://group/1',
            'member_ous_uid': member, 'target_name': target,
            'asdm_uid': 'uid://execution/1',
        }]
    return result


def _document(candidates):
    return {'schema_version': 'archive_mosaic_backend_2',
            'proposed': {'source_name': 'CASE2', 'row_count': 3},
            'assessment_status': 'COMPLETED',
            'discovery': {'status': 'COMPLETED'}, 'candidates': candidates}


def _page(report, view='matching', page=1):
    projection = mosaic_report_projection(report)
    loads = []
    def load(index):
        loads.append(index)
        return report['candidates'][index]
    result = mosaic_report_page(projection, page, view, load)
    return result, loads


def test_matching_member_retains_all_targets_and_all_four_contexts():
    report = _document([
        _candidate('target-A', ['CRITERIA_MET', 'INDETERMINATE',
                                'CRITERIA_NOT_MET', 'INDETERMINATE']),
        _candidate('other-target', ['INDETERMINATE']),
        _candidate('unrelated', ['INDETERMINATE'], member='uid://other'),
    ])
    before = deepcopy(report)
    result, loads = _page(report)
    assert loads == [0, 1]
    assert result['matching_member_count'] == 1
    assert result['visible_count'] == 2
    assert len(result['member_groups']) == 1
    group = result['member_groups'][0]
    assert group['member_ous_uid'] == 'uid://member/A'
    assert group['projects'] == ['2018.1.00294.S']
    assert group['group_ous_uids'] == ['uid://group/1']
    assert [entry['candidate']['source_name'] for entry in group['entries']] == [
        'target-A', 'other-target',
    ]
    first = group['entries'][0]
    assert len(first['contexts']) == 4
    assert [x['spws'] for x in first['contexts']] == [
        ['25'], ['27'], ['29'], ['31'],
    ]
    assert first['contexts'][0]['matching'] is True
    assert [x['matching'] for x in first['contexts'][1:]] == [False]*3
    assert report == before


def test_matching_contexts_are_presented_first_without_renumbering():
    report = _document([_candidate('target-A', ['INDETERMINATE', 'CRITERIA_MET'])])
    view, _ = _page(report)
    assert [x['index'] for x in view['candidate_entries'][0]['contexts']] == [1, 0]
    assert report['candidates'][0]['evaluation']['contexts'][0]['branches'][0]['status'] == 'INDETERMINATE'


def test_matching_member_is_never_split_across_20_group_page_boundary():
    records = [_candidate('target-0', ['CRITERIA_MET'])]
    # 25 related targets are within one matching Member (not 25 pages).
    records.extend(_candidate(f'target-{i}', ['INDETERMINATE']) for i in range(1, 26))
    records.extend(_candidate(f'foreign-{i}', ['CRITERIA_MET'], member=f'uid://foreign/{i}')
                   for i in range(20))
    report = _document(records)
    first, loads1 = _page(report, page=1)
    second, loads2 = _page(report, page=2)
    assert first['matching_member_count'] == 21
    assert first['pages'] == second['pages'] == 2
    assert list(range(26)) == loads1[:26]
    assert len(first['member_groups'][0]['entries']) == 26
    assert 0 not in loads2 and 25 not in loads2
    assert second['matching_member_count'] == 21


def test_unknown_members_never_merge_and_raw_metadata_must_match_candidate():
    blank = _candidate('no-member', ['CRITERIA_MET'], member=None, metadata=False)
    another = _candidate('another', ['INDETERMINATE'], member=None, metadata=False)
    other = _candidate('target', ['CRITERIA_MET'])
    other['metadata_rows'].append({
        'proposal_id': 'FORGED', 'member_ous_uid': 'uid://foreign',
        'target_name': 'target', 'asdm_uid': 'uid://foreign',
    })
    result, loads = _page(_document([blank, another, other]))
    assert loads == [0, 2]
    assert len(result['member_groups']) == 2
    assert result['member_groups'][0]['member_ous_uid'] is None
    assert result['member_groups'][1]['projects'] == ['2018.1.00294.S']
    assert result['candidate_entries'][1]['identity']['projects'] == ['2018.1.00294.S']
    assert result['candidate_entries'][1]['identity']['asdm_uids'] == ['uid://execution/1']


def test_untrusted_line_pair_association_does_not_assign_spw_to_wrong_member():
    candidate = _candidate('target-A', ['CRITERIA_MET'])
    assoc = candidate['evaluation']['contexts'][0]['line_pairs'][0]['attempt']['reference']['candidate_association']
    assoc['context']['member_ous_uid'] = 'uid://wrong'
    result, _ = _page(_document([candidate]))
    assert result['candidate_entries'][0]['contexts'][0]['spws'] == []
    assert result['candidate_entries'][0]['contexts'][0]['asdm_uids'] == []


def test_render_contains_hierarchy_siblings_contexts_and_exact_spws():
    report = _document([_candidate('target-A', ['CRITERIA_MET', 'INDETERMINATE',
                                               'INDETERMINATE', 'INDETERMINATE']),
                        _candidate('other-target', ['INDETERMINATE'])])
    result, _ = _page(report)
    result.update(
        report_id='demo', retention_hours=24,
        url_for=lambda endpoint, **p: '/' + endpoint,
        status_labels={'CRITERIA_MET': 'Meets these conditions',
                       'CRITERIA_NOT_MET': 'Does not meet these conditions',
                       'INDETERMINATE': 'Needs review'},
        display_number=str,
        criterion_view=lambda item: {'label': item['criterion_id'], 'proposed': None, 'candidate': None},
        criterion_status=lambda record: record['outcome'],
        criterion_explanation=lambda record: 'Recorded comparison',
        pair_title=lambda pair: 'Recorded pair',
    )
    folder = Path(__file__).resolve().parents[2] / 'src/alma_duplicate/ui/templates'
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block extra_head %}{% endblock %}'
                                 '{% block content %}{% endblock %}'}),
        FileSystemLoader(folder)
    ]), autoescape=True)
    text = env.get_template('mosaic_report.html').render(**result)
    assert '2018.1.00294.S' in text
    assert 'uid://group/1' in text
    assert 'uid://execution/1' in text
    for spw in (25, 27, 29, 31):
        assert f'Archive SPW {spw}' in text
    assert 'Target: other-target' in text
    assert 'Context 4' in text
    assert text.count('class="candidate-comparison mosaic-context"') == 5
    assert 'id="mosaic-context-0-0" open' in text
    for context_index in (1, 2, 3):
        assert f'id="mosaic-context-0-{context_index}"' in text
        assert f'id="mosaic-context-0-{context_index}" open' not in text


def test_other_diagnostic_views_keep_original_candidate_filters():
    report = _document([
        _candidate('match', ['CRITERIA_MET']),
        _candidate('review', ['INDETERMINATE']),
        _candidate('no', ['CRITERIA_NOT_MET']),
    ])
    for view, expected in [('all', [0, 1, 2]), ('review', [1]), ('not_met', [2])]:
        result, loaded = _page(report, view=view)
        assert loaded == expected
        assert [entry['candidate_index'] for entry in result['candidate_entries']] == expected
