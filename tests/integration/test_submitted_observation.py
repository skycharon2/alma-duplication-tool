"""Separated LINE and continuum branches share candidates, never operands."""
from copy import deepcopy
import pytest
from alma_duplicate.separated_setup_input import SEPARATED_OBSERVATION_CONTRACT
from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
from alma_duplicate.submitted_line_assessment import assess_submitted_line_mosaic_v2
from tests.integration.test_submitted_line_assessment_step04c import _wire, _single
from tests.integration.test_mosaic_scientific_acceptance import _line_case
from alma_duplicate.domain.proposed_observation import CONTINUUM_SETUP_DECLARATION


def observation(intents=('LINE', 'CONTINUUM')):
    doc = _wire()
    raw = doc['request']
    raw.update(line_input_contract=SEPARATED_OBSERVATION_CONTRACT, intents=list(intents),
        representative_frequency={'value': '225.1', 'unit': 'GHz', 'kind': 'SKY'},
        continuum_setup_declaration=CONTINUUM_SETUP_DECLARATION)
    if 'CONTINUUM' in intents:
        raw['continuum_requirement'] = {'rms': {'value': '0.3', 'unit': 'mJy/beam'}, 'physical_spw_ids': []}
    if 'LINE' not in intents:
        raw['line_requirements'] = []
        raw['physical_spw_evidence'] = []
    return doc


@pytest.mark.parametrize('intents', [('LINE',), ('CONTINUUM',), ('LINE','CONTINUUM')])
def test_single_selected_branches_and_inspection(intents):
    from alma_duplicate.report_inspection import inspect_report
    doc = observation(intents)
    report = _single(doc)
    assert report['report_version'] == '8'
    assert report['request']['raw'] == doc['request']
    for c in report['context_evaluations']:
        assert {b['branch'] for b in c['branches']} == set(intents)
    inspect_report(report, inspection_version='3')


def test_mosaic_combined_keeps_both_branches():
    doc = observation()
    original, context, points, execution, evidence = _line_case()
    doc['request'].update(geometry='MOSAIC', target_name=original.target_name, position=None)
    report = assess_submitted_line_mosaic_v2(doc['request'], [context], points,
                         use_s_region=False, executions=[execution], array_evidence=evidence)
    assert {b['branch'] for b in report['contexts'][0]['branches']} == {'LINE','CONTINUUM'}


def test_physical_records_are_not_line_operands():
    doc = observation()
    prepared = prepare_submitted_line_request(doc['request'])
    assert [w.window_id for w in prepared.line_request.spectral_windows] == ['line-a']
    assert [w.window_id for w in prepared.continuum_request.spectral_windows] == ['physical-a', 'physical-b']
    changed = deepcopy(doc)
    changed['request']['line_requirements'][0]['rms']['value'] = '0.00001'
    first, second = _single(doc), _single(changed)
    assert [b for c in first['context_evaluations'] for b in c['branches'] if b['branch']=='CONTINUUM'] == [b for c in second['context_evaluations'] for b in c['branches'] if b['branch']=='CONTINUUM']


def test_aq_failure_retains_candidates_and_source_failure():
    from alma_duplicate.clients.archive_aq_client import ArchiveAqError
    from alma_duplicate.clients.archive_replay import RecordedArchiveClient
    from alma_duplicate.submitted_line_assessment import assess_submitted_line_single_v2
    from tests.integration.test_line_preparation import EXAMPLE
    doc = observation()
    calls = []
    def fail(members):
        calls.append(members)
        raise ArchiveAqError('INCOMPLETE', 'fixture unavailable')
    report = assess_submitted_line_single_v2(doc['request'], doc['search_options'],
        archive_client=RecordedArchiveClient(EXAMPLE/'archive/manifest.json'), archive_array_fetcher=fail)
    assert len(calls) == 1
    assert report['assessment_status'] == 'SOURCES_UNAVAILABLE'
    assert report['sources']['ARCHIVE']['array_evidence']['acquisition']['status'] == 'INCOMPLETE'
    assert report['context_evaluations']
    assert report['assessment'] == 'NOT_AGGREGATED'


@pytest.mark.parametrize('change', [
    {'rms': None}, {'rms': {'value': '-1', 'unit': 'mJy/beam'}},
    {'physical_spw_ids': ['not-a-physical-window']}, {'unknown': True},
])
def test_invalid_continuum_requirement_rejected(change):
    doc = observation()
    doc['request']['continuum_requirement'].update(change)
    with pytest.raises(ValueError):
        prepare_submitted_line_request(doc['request'])
