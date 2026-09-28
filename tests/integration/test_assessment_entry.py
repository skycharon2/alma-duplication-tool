"""Application/CLI agreement and lazy-source contracts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, AssessmentStatus, assess_observation,
)
from alma_duplicate.cli.evaluate import main
from alma_duplicate.clients.queue_csv_client import QueueCsvClient

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / 'tests/fixtures/queue/queue_pipeline_v1.csv'


def forbidden():
    pytest.fail('Source accessed before validation/exemption')


def normalized(document):
    document = deepcopy(document)
    for field in ('generated_at', 'search_started_at', 'search_finished_at'):
        document.pop(field, None)
    metadata = document.get('sources', {}).get('QUEUE', {}).get('source_metadata') or {}
    snapshot = metadata.get('snapshot')
    if snapshot is not None:
        snapshot.pop('parsed_at', None)
    return document


@pytest.mark.parametrize('example, options, flags', [
    ('queue_continuum/request.json', AssessmentOptions(queue_continuum=True), ['--queue-continuum']),
    ('proposed_observation.json', AssessmentOptions(), []),
])
def test_cli_and_application_return_same_document(tmp_path, example, options, flags):
    raw = (ROOT / 'examples' / example).read_bytes()
    payload = json.loads(raw)
    payload['search_options']['sources'] = ['ARCHIVE', 'QUEUE']
    raw = json.dumps(payload).encode()
    path = tmp_path / 'request.json'
    path.write_bytes(raw)
    output = tmp_path / 'report.json'
    result = assess_observation(
        **payload, options=options,
        sources=AssessmentSources(queue_loader=lambda: QueueCsvClient().load(QUEUE)),
        input_sha256=hashlib.sha256(raw).hexdigest(),
    )
    assert result.status == AssessmentStatus.SOURCES_UNAVAILABLE
    assert main(['--request', str(path), '--queue-csv', str(QUEUE),
                 '--output', str(output), *flags]) == 3
    assert normalized(result.document) == normalized(json.loads(output.read_text()))


def test_solar_skips_sources_and_method_selection():
    result = assess_observation(
        {'target_kind': 'SUN', 'geometry': 'SINGLE_POINTING', 'setup_id': 'sun',
         'intents': ['CONTINUUM']}, {},
        sources=AssessmentSources('LIVE', forbidden, forbidden),
        options=AssessmentOptions(queue_line=True),
    )
    assert result.status == AssessmentStatus.SOLAR_EXEMPTION
    assert result.document['report_kind'] == 'SOLAR_EXEMPTION'


def test_invalid_request_has_no_report_or_source_access():
    result = assess_observation({'target_kind': 'INVALID'}, {},
                               sources=AssessmentSources('LIVE', forbidden, forbidden))
    assert result.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY
    assert result.document is None
    assert not result.validation.is_valid


@pytest.mark.parametrize('options,sources', [
    (AssessmentOptions(queue_line=True), AssessmentSources('LIVE', forbidden)),
    (AssessmentOptions(beam_decision_ref=' '), AssessmentSources('LIVE', forbidden)),
    (AssessmentOptions(), AssessmentSources('INVALID', forbidden)),
    (AssessmentOptions(), AssessmentSources('LIVE', None)),
])
def test_invalid_configuration_is_rejected_before_source_access(options, sources):
    payload = json.loads((ROOT / 'examples/proposed_observation.json').read_text())
    payload['search_options']['sources'] = ['ARCHIVE']
    with pytest.raises(ValueError):
        assess_observation(**payload, options=options, sources=sources)


def test_conflicting_beam_strategies_are_rejected_before_source_access():
    payload = json.loads((ROOT / 'examples/proposed_observation.json').read_text())
    payload['search_options']['sources'] = ['ARCHIVE', 'QUEUE']
    with pytest.raises(
        ValueError,
        match='Candidate-beam profile cannot be mixed with the legacy request-beam strategy',
    ):
        assess_observation(
            **payload,
            options=AssessmentOptions(
                beam_decision_ref='decision-ref',
                queue_candidate_beam=True,
            ),
            sources=AssessmentSources('LIVE', forbidden, forbidden),
        )


def test_failed_queue_source_preserves_structured_report():
    payload = json.loads((ROOT / 'examples/queue_continuum/request.json').read_text())
    payload['search_options']['sources'] = ['QUEUE']
    def failed():
        raise OSError('source unavailable')
    result = assess_observation(**payload, options=AssessmentOptions(queue_continuum=True),
                               sources=AssessmentSources(queue_loader=failed))
    assert result.status == AssessmentStatus.SOURCES_UNAVAILABLE
    assert result.document['sources']['QUEUE']['status'] == 'FAILED'
    assert result.document['assessment'] == 'NOT_AGGREGATED'


@pytest.mark.parametrize('case_id', ['dual-source-line', 'mixed-intents'])
def test_replay_metadata_and_line_results_agree_with_cli(tmp_path, case_id):
    from alma_duplicate.clients.archive_replay import RecordedArchiveClient
    base = ROOT / 'examples/acceptance'
    case = next(c for c in json.loads((base / 'catalog.json').read_text())['cases']
                if c['case_id'] == case_id)
    request = (base / case['inputs']['request']['path']).resolve()
    manifest = (base / case['inputs']['archive_replay']['path']).resolve()
    queue = ((base / case['inputs']['queue_csv']['path']).resolve()
             if 'queue_csv' in case['inputs'] else None)
    calls = []
    def provider():
        calls.append('archive')
        client = RecordedArchiveClient(manifest)
        return ArchiveInput(client, client.metadata)
    raw = request.read_bytes()
    result = assess_observation(
        **json.loads(raw), options=AssessmentOptions(**case['evaluation_options']),
        sources=AssessmentSources('REPLAY', provider,
                                  (lambda: QueueCsvClient().load(queue)) if queue else None),
        input_sha256=hashlib.sha256(raw).hexdigest(),
    )
    assert calls == ['archive']
    output = tmp_path / 'report.json'
    args = ['--request', str(request), '--archive-replay', str(manifest), '--output', str(output)]
    if queue:
        args += ['--queue-csv', str(queue)]
    args += ['--' + key.replace('_', '-') for key, value in case['evaluation_options'].items() if value]
    assert main(args) == case['expected_exit_code']
    assert normalized(result.document) == normalized(json.loads(output.read_text()))
