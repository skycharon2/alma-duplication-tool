"""Stage accounting is optional and does not alter scientific output."""
import json
from pathlib import Path

import pytest

from alma_duplicate.performance import PerformanceRecorder, measure_stage
from alma_duplicate.cli.profile_assessment import profile
from alma_duplicate.ui.runs import BrowserAssessment

ROOT = Path(__file__).parents[2]


def test_clock_accounting_failure_and_isolation():
    clock = iter([10., 12., 20., 23.])
    cpu = iter([1., 1.5, 2., 3.])
    recorder = PerformanceRecorder(wall_clock=lambda: next(clock), cpu_clock=lambda: next(cpu))
    with recorder.record():
        with measure_stage('successful'):
            pass
        with pytest.raises(ValueError), measure_stage('failed'):
            raise ValueError('expected')
    with measure_stage('not_recorded'):
        pass
    assert [(s.wall_seconds, s.thread_cpu_seconds, s.failed) for s in recorder.stages] == [(2., .5, False), (3., 1., True)]


def test_profile_and_failed_storage_preserve_evaluation():
    document = json.loads((ROOT / 'examples/confirmed_line/request.json').read_text())
    configured = BrowserAssessment(archive_replay=ROOT / 'examples/confirmed_line/archive/manifest.json')
    ordinary = configured.assess(document)
    with PerformanceRecorder().record() as recorder:
        timed = configured.assess(document)
    for key in ['context_evaluations', 'request_criteria', 'evaluation_configuration']:
        assert ordinary.document[key] == timed.document[key]
    names = [s.name for s in recorder.stages]
    assert names.index('tap_acquisition') < names.index('scientific_evaluation') < names.index('report_assembly')
    success = profile(document, configured)
    failed = profile(document, configured, max_bytes=1)
    assert success['execution'] == 'COMPLETED' and failed['execution'] == 'FAILED'
    assert success['retained_contexts'] == failed['retained_contexts'] > 0
    assert success['branch_outcomes'] == failed['branch_outcomes']
    assert success['files']['report.json'] > 0 and failed['files'] == {}
    assert any(s['name'] == 'write_report' and s['failed'] for s in failed['stages'])
    assert all(s['wall_seconds'] >= 0 for s in success['stages'])
    assert sum(s['wall_seconds'] for s in success['stages']) <= success['wall_seconds']


def test_saved_failure_report_is_not_a_successful_source_run(monkeypatch):
    from alma_duplicate.clients import archive_client, archive_aq_client

    class FailedTap:
        def __init__(self, endpoint):
            pass

        def search(self, query):
            raise TimeoutError('simulated timeout')

    def forbidden_aq():
        pytest.fail('AQ must not start after TAP failure')

    monkeypatch.setattr(archive_client, 'ArchiveClient', FailedTap)
    monkeypatch.setattr(archive_aq_client, 'ArchiveAqClient', forbidden_aq)
    document = json.loads((ROOT / 'examples/confirmed_line/request.json').read_text())
    result = profile(document, BrowserAssessment(live_archive=True, live_aq=True))
    assert result['execution'] == 'COMPLETED'
    assert result['assessment_status'] == 'SOURCES_UNAVAILABLE'
    assert result['sources']['ARCHIVE'] == 'FAILED'
    assert result['retained_contexts'] == 0
    assert result['branch_outcomes'] == {}
    diagnostic = result['source_diagnostics']['ARCHIVE']
    assert diagnostic['reasons'] == ['ACQUIRE_FAILED', 'TimeoutError', 'simulated timeout']
    assert diagnostic['aq_status'] == 'SKIPPED'
    assert diagnostic['aq_reason'] == 'TAP_NOT_COMPLETED'
    assert any(s['name'] == 'tap_acquisition' and s['failed'] for s in result['stages'])
