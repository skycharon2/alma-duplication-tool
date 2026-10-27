"""Read-only Mosaic projection and indexed browser report storage."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.mosaic_report_view import mosaic_report_projection
from alma_duplicate.ui.run_store import RunStore


def criterion(name='POS-MOSAIC', outcome='SATISFIED'):
    return {'criterion_id': name, 'outcome': outcome,
            'eligible_for_formal_aggregation': True,
            'derived': [('secret_operands', 17)], 'reasons': ['ORIGINAL_REASON']}


def context(name, statuses, *, with_pairs=False):
    return {
        'context_id': name,
        'branches': [{'branch': 'LINE', 'status': status,
                      'truth': 'TRUE' if status == 'CRITERIA_MET' else 'UNKNOWN'}
                     for status in statuses],
        'criteria': [criterion()], 'request_criteria': [criterion('CONT-SETUP')],
        'line_pairs': ([{'status': 'INDETERMINATE', 'raw_operand': 'unavailable'},
                        {'status': 'CRITERIA_MET'}] if with_pairs else []),
        'coverage': {'points': [{'ra_deg': 10, 'dec_deg': -30}]},
    }


def candidate(index, status, contexts=None):
    value = {'member_ous_uid': f'uid://member/{index}', 'source_name': 'NGC 253',
             'status': status}
    if contexts is not None:
        value['evaluation'] = {'contexts': contexts}
    if status != 'EVALUATED':
        value['error'] = 'Source metadata unavailable'
    return value


def document():
    return {
        'schema_version': 'archive_mosaic_backend_2',
        'proposed': {'source_name': 'NGC253_CASE2_SYNTHETIC_LINE', 'row_count': 3,
                     'raw_text': 'SENSITIVE_OT_POINTINGS'},
        'assessment_status': 'INCOMPLETE',
        'absence_interpretation': 'NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION',
        'discovery': {'status': 'COMPLETED', 'query': 'SENSITIVE_TAP_QUERY'},
        'candidates': [
            candidate(0, 'EVALUATED', [context('positive', ['CRITERIA_MET', 'INDETERMINATE'], with_pairs=True)]),
            candidate(1, 'EVALUATED', [context('negative', ['CRITERIA_NOT_MET'])]),
            candidate(2, 'EVALUATED', [context('uncertain', ['INDETERMINATE'])]),
            candidate(3, 'INCOMPLETE'),
            candidate(4, 'NO_METADATA_CONTEXTS'),
            candidate(5, 'EVALUATED', []),
        ],
    }


def test_projection_separates_scientific_and_source_states_without_recomputation():
    source = document()
    before = deepcopy(source)
    view = mosaic_report_projection(source)
    assert source == before
    assert view['projection_schema_version'] == 'mosaic_browser_view_1'
    assert view['mosaic_overview']['candidate_count'] == 6
    assert view['mosaic_overview']['context_count'] == 3
    assert view['mosaic_overview']['candidate_buckets'] == {
        'MATCH': 1, 'NOT_MET': 1, 'NEEDS_REVIEW': 2, 'UNAVAILABLE': 2,
    }
    assert view['mosaic_overview']['branch_status_counts'] == {
        'CRITERIA_MET': 1, 'CRITERIA_NOT_MET': 1,
        'INDETERMINATE': 2, 'OTHER_OR_UNRECORDED': 0,
    }
    assert view['mosaic_overview']['candidate_source_status_counts'] == {
        'EVALUATED': 4, 'INCOMPLETE': 1, 'NO_METADATA_CONTEXTS': 1,
    }
    first = view['candidate_summaries'][0]
    assert first['bucket'] == 'MATCH'
    assert first['contexts'][0]['branches'] == [
        {'branch': 'LINE', 'status': 'CRITERIA_MET'},
        {'branch': 'LINE', 'status': 'INDETERMINATE'},
    ]
    assert first['contexts'][0]['criteria'][0]['criterion_id'] == 'POS-MOSAIC'
    assert first['contexts'][0]['line_pair_status_counts'] == {
        'CRITERIA_MET': 1, 'INDETERMINATE': 1,
    }
    serialized = json.dumps(view)
    for forbidden in ('SENSITIVE_OT_POINTINGS', 'SENSITIVE_TAP_QUERY',
                      'secret_operands', 'Source metadata unavailable', 'raw_operand'):
        assert forbidden not in serialized


def test_evaluated_empty_or_unknown_never_counts_as_negative():
    source = document()
    source['candidates'] = [
        candidate(0, 'EVALUATED', []),
        candidate(1, 'EVALUATED', [context('unrecognized', ['FUTURE_STATUS'])]),
        candidate(2, 'EVALUATED', [context('missing', [])]),
        candidate(3, 'INCOMPLETE', [context('supplied', ['CRITERIA_MET'])]),
    ]
    view = mosaic_report_projection(source)
    assert [item['bucket'] for item in view['candidate_summaries']] == [
        'NEEDS_REVIEW', 'NEEDS_REVIEW', 'NEEDS_REVIEW', 'UNAVAILABLE',
    ]
    assert view['mosaic_overview']['branch_status_counts']['OTHER_OR_UNRECORDED'] == 1
    assert view['mosaic_overview']['branch_status_counts']['CRITERIA_MET'] == 0


def test_projection_preserves_identity_order_and_refuses_wrong_schema():
    source = document()
    source['candidates'][1]['member_ous_uid'] = source['candidates'][0]['member_ous_uid']
    view = mosaic_report_projection(source)
    assert [entry['candidate_index'] for entry in view['candidate_summaries']] == list(range(6))
    assert view['candidate_summaries'][0]['member_ous_uid'] == view['candidate_summaries'][1]['member_ous_uid']
    with pytest.raises(ValueError, match='Mosaic backend'):
        mosaic_report_projection({'schema_version': 'report_v6'})


def test_run_store_keeps_original_exports_and_reads_only_selected_candidates(tmp_path, monkeypatch):
    source = document()
    source['candidates'] = [candidate(i, 'EVALUATED', [context(f'context-{i}', ['CRITERIA_NOT_MET'])])
                            for i in range(21)]
    store = RunStore(directory=tmp_path)
    try:
        request = {'request': {'geometry': 'MOSAIC'}}
        original = deepcopy(source)
        run_id = store.add(request, SimpleNamespace(document=source, status='COMPLETED'))
        assert source == original
        projection = json.loads((store._runs[run_id].directory / 'view.json').read_text())
        assert projection['mosaic_overview']['candidate_buckets']['NOT_MET'] == 21
        assert len(projection['candidate_summaries']) == 21
        raw = b''.join(store.open_download(run_id, 'report'))
        assert raw == report_json_text(source).encode('utf-8')
        assert b''.join(store.open_download(run_id, 'request')) == report_json_text(request).encode('utf-8')
        page = store.page(run_id, page=2, view='all')
        assert page['candidate_count'] == 21
        assert len(page['candidates']) == len(page['candidate_summaries']) == 1
        assert page['candidate_summaries'][0]['candidate_index'] == 20
        assert page['candidates'][0] == json.loads(report_json_text(source['candidates'][20]))
        assert page['mosaic_overview']['candidate_buckets']['NOT_MET'] == 21
        assert 'candidates' not in page['document']
        with pytest.raises(IndexError):
            store.page(run_id, page=3, view='all')
        # The index is read once; candidate payloads remain in indexed report bytes.
        assert (store._runs[run_id].directory / 'view.json').stat().st_size < len(raw)
    finally:
        store.close()


def test_missing_criteria_and_pair_evidence_remain_unknown_not_matched():
    source = document()
    source['candidates'] = [candidate(0, 'EVALUATED', [{
        'context_id': 'only-identity', 'branches': [{'branch': 'LINE', 'status': None}],
    }])]
    view = mosaic_report_projection(source)
    assert view['candidate_summaries'][0]['bucket'] == 'NEEDS_REVIEW'
    assert view['candidate_summaries'][0]['contexts'][0]['line_pair_count'] == 0
    assert view['mosaic_overview']['branch_status_counts']['OTHER_OR_UNRECORDED'] == 1
