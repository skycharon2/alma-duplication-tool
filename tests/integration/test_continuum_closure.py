"""Input/CLI regressions for the post-4122f81 continuum closure."""
from dataclasses import replace
import json

import pytest

from alma_duplicate.cli.evaluate import main
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.continuum import evaluate_continuum_rms
from tests.integration.test_confirmed_continuum import EXAMPLE, case, payload


def run_cli(tmp_path, data, *args):
    request = tmp_path / 'request.json'
    output = tmp_path / 'report.json'
    request.write_text(json.dumps(data))
    code = main(['--request', str(request), '--output', str(output), *map(str, args)])
    return code, json.loads(output.read_text()) if output.exists() else None


@pytest.mark.parametrize('ids', [[], ['w0'], ['w0', 'w1', 'w2', 'w3']])
def test_aggregate_contributors_preserve_cli_branch(tmp_path, ids):
    p = payload()
    p['request']['sensitivities'][0]['window_ids'] = ids
    code, doc = run_cli(tmp_path, p, '--archive-replay', EXAMPLE / 'archive/manifest.json')
    assert code == 0
    assert [c['branches'][0]['status'] for c in doc['context_evaluations']] == [
        'CRITERIA_MET', 'CRITERIA_NOT_MET', 'INDETERMINATE', 'CRITERIA_NOT_MET']
    rms = next(c for c in doc['context_evaluations'][0]['criteria'] if c['criterion_id'] == 'CONT-RMS')
    assert rms['method_version'] == 'archive_cont_rms_2'
    assert [value for name, value in rms['details'] if name == 'contributing_window_id'] == ids
    assert doc['evaluation_scope']['evaluated_contexts'] == 4
    assert doc['evaluation_scope']['shown_candidates'] == 1


@pytest.mark.parametrize('ids', [['absent'], ['w0', 'w0']])
def test_invalid_contributors_rejected_at_both_boundaries(tmp_path, ids):
    p = payload()
    p['request']['sensitivities'][0]['window_ids'] = ids
    code, doc = run_cli(tmp_path, p)
    assert code == 2 and doc is None
    request, context, _ = case()
    sensitivity = replace(request.sensitivities[0], window_ids=tuple(ids))
    result = evaluate_continuum_rms(replace(request, sensitivities=(sensitivity,)), context)
    assert result.outcome is None
    assert 'INVALID_CONTRIBUTING_WINDOW_REFERENCE' in result.reasons


def solar():
    return {'request': {'target_kind': 'SUN', 'geometry': 'SINGLE_POINTING',
                        'setup_id': 'solar', 'intents': ['CONTINUUM']}, 'search_options': {}}


@pytest.mark.parametrize('source_flags', [[], ['--live-archive'],
    ['--archive-replay', 'missing/manifest.json', '--queue-csv', 'missing/queue.csv']])
def test_solar_cli_exempts_before_any_source_access(tmp_path, monkeypatch, source_flags):
    import alma_duplicate.cli.evaluate as cli
    import alma_duplicate.clients.archive_replay as replay
    import requests
    def forbidden(*args, **kwargs):
        pytest.fail('Solar must not query or load sources')
    monkeypatch.setattr(cli, 'search_candidates', forbidden)
    monkeypatch.setattr(cli.QueueCsvClient, 'load', forbidden)
    monkeypatch.setattr(replay, 'RecordedArchiveClient', forbidden)
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    data = solar()
    data['search_options']['sources'] = ['ARCHIVE', 'QUEUE']
    request = tmp_path / 'solar.json'
    output = tmp_path / 'report.json'
    request.write_text(json.dumps(data))
    assert main(['--request', str(request), '--output', str(output), *source_flags],
                archive_client_factory=forbidden) == 0
    doc = json.loads(output.read_text())
    assert doc['report_kind'] == 'SOLAR_EXEMPTION'
    assert doc['assessment'] == 'NOT_APPLICABLE'
    assert doc['exemption']['reason'] == 'SOLAR_EXEMPT'
    assert doc['search_execution'] == 'NOT_EXECUTED' and doc['plan'] is None
    assert not doc['context_evaluations'] and not doc['request']['issues']
    assert all(s['status'] == 'NOT_QUERIED' for s in doc['sources'].values())
    assert doc['evaluation_scope']['evaluated_contexts'] == 0


def test_solar_without_search_controls(tmp_path):
    code, doc = run_cli(tmp_path, solar())
    assert code == 0 and doc['assessment'] == 'NOT_APPLICABLE'


@pytest.mark.parametrize('change', ['invalid_rms', 'dangling', 'moving', 'invalid_radius'])
def test_exemption_never_bypasses_validation(tmp_path, change):
    p = payload()
    p['request']['target_kind'] = 'SUN'
    if change == 'invalid_rms':
        p['request']['sensitivities'][0]['rms']['value'] = -1
    elif change == 'dangling':
        p['request']['sensitivities'][0]['window_ids'] = ['absent']
    elif change == 'moving':
        p['request']['target_kind'] = 'MOVING'
    else:
        p['search_options']['radius']['value'] = -1
    assert run_cli(tmp_path, p) == (2, None)


def test_solar_replay_overwrite_cannot_replace_uninspected_response(tmp_path):
    p = solar()
    response = tmp_path / 'report.json'
    response.write_text('original response')
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(p))
    assert main(['--request', str(request), '--output', str(response), '--overwrite',
                 '--archive-replay', str(tmp_path / 'missing.json')]) == 2
    assert response.read_text() == 'original response'


def test_confirmed_example_has_only_raw_evidence_notes(tmp_path):
    code, doc = run_cli(tmp_path, payload(), '--archive-replay', EXAMPLE / 'archive/manifest.json')
    assert code == 0 and doc['request']['validation_version'] == '4'
    issues = doc['request']['issues']
    assert issues and all(i['category'] == 'EVIDENCE' and i['rule_id'] is None for i in issues)
    assert not any('Policy width interpretation' in i['message'] for i in issues)
    assert doc['context_evaluations'][0]['branches'][0]['status'] == 'CRITERIA_MET'


@pytest.mark.parametrize('intents', [['CONTINUUM'], ['LINE'], ['CONTINUUM', 'LINE'], []])
def test_diagnostics_follow_intents_without_hiding_invalid_data(intents):
    p = payload()
    p['request']['intents'] = intents
    p['request']['sensitivities'][0].pop('rms')
    validation = validate_proposed_observation(p['request'], p['search_options'])
    active = [i for i in validation.issues if i.category != 'EVIDENCE']
    assert any(i.rule_id == 'CONT-RMS' for i in active) == ('CONTINUUM' in intents)
    assert any(i.rule_id == 'LINE' and i.category == 'CAPABILITY' for i in active) == ('LINE' in intents)
    assert all(not (i.rule_id or '').startswith('LINE') for i in active) if 'LINE' not in intents else True
    p['request']['sensitivities'][0]['window_ids'] = ['invalid']
    assert not validate_proposed_observation(p['request'], p['search_options']).is_valid


def test_bounds_width_is_available_but_non_sky_representative_is_missing():
    p = payload()
    for window in p['request']['spectral_windows']:
        center = window.pop('center')
        window.pop('bandwidth')
        window.update(representation='BOUNDS', lower=dict(center, value=100, frame='LSRK'),
                      upper=dict(center, value=102, frame='LSRK'))
    v = validate_proposed_observation(p['request'], p['search_options'])
    assert not any(i.rule_id == 'CONT-SETUP' for i in v.issues)
    p['request']['representative_frequency']['kind'] = 'REST'
    v = validate_proposed_observation(p['request'], p['search_options'])
    assert any(i.rule_id == 'CONT-FREQ' and i.category == 'MISSING' for i in v.issues)
