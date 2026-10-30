"""Separated Single Pointing requirements retain both source evaluations."""
from copy import deepcopy

import pytest

from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.submitted_line_assessment import assess_submitted_line_single_v2
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_submitted_line_assessment_step04c import _wire, EXAMPLE
from tests.integration.test_queue_line_evaluation import request, common
from tests.integration.test_queue_line_pairing import contexts
from alma_duplicate.rules.queue_line import evaluate_queue_line


def csv_result(document):
    p = document['request']['position']
    return queue_rows({'RA': str(p['ra']), 'Dec': str(p['dec']),
                       'Use TP?': 'False', 'Use 7-m?': 'False'})


@pytest.mark.parametrize('sources', [['QUEUE'], ['ARCHIVE', 'QUEUE']])
def test_two_rest_requirements_preserve_ids_and_redshifts_across_sources(sources):
    document = _wire()
    raw = document['request']
    first = raw['line_requirements'][0]
    first['window_center'].update(value='450.2', kind='REST')
    first['source_redshift'] = '1'
    second = deepcopy(first)
    second.update(requirement_id='line-b', source_redshift='0')
    raw['line_requirements'].append(second)
    document['search_options']['sources'] = sources
    result = assess_submitted_line_single_v2(raw, document['search_options'],
        archive_client=RecordedArchiveClient(EXAMPLE / 'archive/manifest.json'),
        queue_loader=lambda: csv_result(document))
    assert result['sources']['QUEUE']['status'] == 'COMPLETED'
    assert result['sources']['ARCHIVE']['status'] == ('COMPLETED' if 'ARCHIVE' in sources else 'NOT_SELECTED')
    for context in result['context_evaluations']:
        assert {p['attempt']['reference']['proposed_window_id'] for p in context['line_pairs']} == {'line-a', 'line-b'}
        assert not any('physical' in p['attempt']['reference']['proposed_window_id'] for p in context['line_pairs'])
    assert result['request']['raw'] == raw
    queue = [c for c in result['context_evaluations'] if c['reference']['source'] == 'QUEUE']
    assert queue
    assert queue[0]['branches'][0]['method_version'] == 'queue_line_context_submitted_or_2'
    frequencies = {p['attempt']['reference']['proposed_window_id']:
                   p['attempt']['proposed']['sky_frequency_ghz']
                   for p in queue[0]['line_pairs']}
    assert frequencies == {'line-a': 225.1, 'line-b': 450.2}



@pytest.mark.parametrize('failed', ['ARCHIVE', 'QUEUE'])
def test_one_source_failure_does_not_discard_other_source(failed):
    document = _wire()
    document['search_options']['sources'] = ['ARCHIVE', 'QUEUE']
    def broken():
        raise OSError('unavailable fixture')
    result = assess_submitted_line_single_v2(document['request'], document['search_options'],
        archive_client=None if failed == 'ARCHIVE' else RecordedArchiveClient(EXAMPLE / 'archive/manifest.json'),
        queue_loader=broken if failed == 'QUEUE' else lambda: csv_result(document))
    other = 'QUEUE' if failed == 'ARCHIVE' else 'ARCHIVE'
    assert result['sources'][other]['status'] == 'COMPLETED'
    assert result['sources'][failed]['status'] != 'COMPLETED'
    assert any(c['reference']['source'] == other for c in result['context_evaluations'])
    assert result['assessment'] == 'NOT_AGGREGATED'
    assert result['assessment_status'] == 'SOURCES_UNAVAILABLE'


def test_queue_v2_negative_does_not_depend_on_physical_inventory():
    context = contexts()[0]
    incomplete = request(center_ghz=240, setup_complete=False)
    _, _, legacy = evaluate_queue_line(incomplete, context, common(context))
    _, pairs, submitted = evaluate_queue_line(incomplete, context, common(context), submitted_scope=True)
    assert legacy.status == 'INDETERMINATE'
    assert submitted.status == 'CRITERIA_NOT_MET'
    assert all(p.status == 'CRITERIA_NOT_MET' for p in pairs)
    assert 'PROPOSED_ENUMERATION_INCOMPLETE' not in submitted.reasons


def test_queue_v2_preserves_unknown_candidate_evidence():
    context = contexts({'Spec.Res. SPW 1': '0.123'})[0]
    _, _, result = evaluate_queue_line(request(center_ghz=222, setup_complete=False),
                                      context, common(context), submitted_scope=True)
    assert result.status == 'INDETERMINATE'
