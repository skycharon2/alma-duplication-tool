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
    success = profile(document, configured, analyze_size=True)
    failed = profile(document, configured, max_bytes=1)
    assert success['execution'] == 'COMPLETED' and failed['execution'] == 'FAILED'
    assert success['retained_contexts'] == failed['retained_contexts'] > 0
    assert success['branch_outcomes'] == failed['branch_outcomes']
    assert success['files']['report.json'] > 0 and failed['files'] == {}
    assert any(s['name'] == 'write_report' and s['failed'] for s in failed['stages'])
    assert all(s['wall_seconds'] >= 0 for s in success['stages'])
    assert sum(s['self_wall_seconds'] for s in success['stages']) <= success['wall_seconds']
    roots = sum(s['wall_seconds'] for s in success['stages'] if s['parent_id'] is None)
    assert roots + success['unattributed_wall_seconds'] == pytest.approx(success['wall_seconds'])
    assert success['report_size']['formatted_bytes'] == success['files']['report.json']
    assert 'report_size' not in failed


def test_saved_failure_report_is_not_a_successful_source_run(monkeypatch):
    from alma_duplicate.clients import archive_client, archive_aq_client

    class FailedTap:
        def __init__(self, endpoint, *, completeness_policy):
            assert completeness_policy == "STATUS_THEN_COUNT"

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


def test_nested_timing_counts_children_once_and_resets_after_failure():
    clock = iter([0., 2., 5., 10., 11., 12.])
    recorder = PerformanceRecorder(wall_clock=lambda: next(clock), cpu_clock=lambda: 0)
    with recorder.record():
        with measure_stage('parent'):
            with pytest.raises(RuntimeError), measure_stage('child'):
                raise RuntimeError('expected')
        with measure_stage('next'):
            pass
    child, parent, following = recorder.stages
    assert child.parent_id == parent.stage_id
    assert child.wall_seconds == child.self_wall_seconds == 3
    assert child.failed and not parent.failed
    assert parent.wall_seconds == 10 and parent.self_wall_seconds == 7
    assert following.parent_id is None and following.self_wall_seconds == 1
    assert sum(s.self_wall_seconds for s in recorder.stages) == 11


def test_inner_recorder_does_not_corrupt_outer_scope():
    outer, inner = PerformanceRecorder(), PerformanceRecorder()
    with outer.record(), measure_stage('outer'):
        with inner.record(), measure_stage('inner'):
            pass
        with measure_stage('child'):
            pass
    assert inner.stages[0].parent_id is None
    assert outer.stages[0].parent_id == outer.stages[1].stage_id
