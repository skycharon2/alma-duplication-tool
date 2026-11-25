"""Bounded overlap, shared Queue initialization and isolated progress."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

import pytest

from alma_duplicate.ui.progress import ProgressStore
from alma_duplicate.ui.queue_browser import memoized_loader
from alma_duplicate.ui.runs import BrowserAssessment
from alma_duplicate.ui.batch_assessment import execute_batch
from tests.ui.test_batch_assessment import store as store_fixture, run, values, runner, ROW, TOKEN

store = store_fixture


def test_two_targets_overlap_and_progress_never_regresses(store, monkeypatch):
    barrier = Barrier(2, timeout=10)
    original = BrowserAssessment.assess
    active = peak = 0
    lock = Lock()

    def assess(self, document):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            barrier.wait()
            return original(self, document)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    events = []
    batch_id = run(store, values(), max_workers=2, progress=events.append)
    manifest = store.batches.get(batch_id, 'browser-a')
    assert peak == 2 and manifest['execution_complete']
    assert [s['source']['name'] for s in manifest['sources']] == ['first', 'second']
    counts = [e['batch_completed'] for e in events]
    assert counts == sorted(counts) and counts[-1] == 4
    assert {e['batch_workers'] for e in events} == {2}


def test_five_targets_respect_limit_and_keep_failed_target_separate(store, monkeypatch):
    gate = Barrier(2, timeout=10)
    original = BrowserAssessment.assess
    lock = Lock()
    active = peak = 0

    def assess(self, document):
        nonlocal active, peak
        name = document['request']['target_name']
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            if name in ('target-0', 'target-1'):
                gate.wait()
            if name == 'target-2':
                raise OSError('Controlled target failure')
            return original(self, document)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    raw = ('name,ra,dec,redshift\n' + ''.join(
        f'target-{i},201.365,-43.019,0\n' for i in range(5))).encode()
    batch_id = execute_batch(values(intents=['LINE']), [ROW], raw, runner=runner(),
                             runs=store, owner='browser-a', submission_token=TOKEN, max_workers=2)
    manifest = store.batches.get(batch_id, 'browser-a')
    assert peak == 2 and manifest['execution_complete']
    assert [s['reports'][0]['state'] for s in manifest['sources']] == [
        'COMPLETED', 'COMPLETED', 'FAILED', 'COMPLETED', 'COMPLETED']


def test_live_archive_starts_next_target_before_previous_report_is_saved(store, monkeypatch):
    original = BrowserAssessment.assess
    third_started = Event()
    first_pair = Barrier(2, timeout=5)

    def assess(self, document):
        name = document['request']['target_name']
        with self.archive_search_slot():
            if name == 'third':
                third_started.set()
            else:
                first_pair.wait()
        assert third_started.wait(5)
        return original(runner(), document)

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    raw = b'name,ra,dec,redshift\nfirst,201,-43,0\nsecond,201,-43,0\nthird,201,-43,0\n'
    batch_id = execute_batch(values(intents=['LINE']), [ROW], raw,
                             runner=BrowserAssessment(live_archive=True), runs=store,
                             owner='browser-a', submission_token=TOKEN, max_workers=2)
    manifest = store.batches.get(batch_id, 'browser-a')
    assert all(s['reports'][0]['state'] == 'COMPLETED' for s in manifest['sources'])


@pytest.mark.parametrize('target_count', [5, 10])
def test_five_tap_slots_keep_local_work_at_four(store, monkeypatch, target_count):
    original = BrowserAssessment.assess
    tap_overlap = Barrier(5, timeout=10)
    local_overlap = Barrier(4, timeout=10)
    lock = Lock()
    entered = active = peak = 0

    def assess(self, document):
        nonlocal entered, active, peak
        with self.archive_search_slot():
            tap_overlap.wait()
        with lock:
            entered += 1
            active += 1
            peak = max(peak, active)
            first_wave = entered <= 4
        try:
            if first_wave:
                local_overlap.wait()
            return original(runner(), document)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    raw = ('name,ra,dec,redshift\n' + ''.join(f'target-{i},201,-43,0\n' for i in range(target_count))).encode()
    batch_id = execute_batch(values(intents=['LINE']), [ROW], raw,
                             runner=BrowserAssessment(live_archive=True), runs=store,
                             owner='browser-a', submission_token=TOKEN, max_workers=4, tap_workers=5)
    manifest = store.batches.get(batch_id, 'browser-a')
    assert entered == target_count and peak == 4
    assert all(s['reports'][0]['state'] == 'COMPLETED' for s in manifest['sources'])


@pytest.mark.parametrize('failed', [False, True])
def test_concurrent_queue_load_is_once_including_failure(failed):
    calls = []
    gate = Barrier(4, timeout=10)
    result = object()

    def loader():
        calls.append(True)
        if failed:
            raise OSError('snapshot unavailable')
        return result

    cached = memoized_loader(loader)

    def load():
        gate.wait()
        try:
            return cached()
        except OSError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(load) for _ in range(4)]
        results = [f.result() for f in futures]
    assert len(calls) == 1
    assert all(r is results[0] for r in results)
    assert isinstance(results[0], OSError) if failed else results[0] is result


def test_progress_keeps_source_counts_separate():
    progress = ProgressStore()
    progress.begin('batch')
    def event(source, stage, completed):
        progress.update('batch', dict(source_id=source, purpose='LINE', stage=stage,
                                     completed=completed, batch_total=2))
    event('line-2', 'archive_ready', 336)
    event('line-3', 'queue_ready', 3200)
    assert 'archive_ready' not in progress.get('batch')['stages']
    event('line-2', 'evaluation', 10)
    stages = progress.get('batch')['stages']
    assert stages['archive_ready']['completed'] == 336
    assert 'queue_ready' not in stages


@pytest.mark.parametrize('workers', [0, 5, True, 1.5, '2'])
def test_invalid_concurrency_rejected_before_execution(store, workers):
    with pytest.raises(ValueError, match='workers'):
        run(store, max_workers=workers)


@pytest.mark.parametrize('override, expected', [(None, 4), ('1', 1)])
def test_browser_environment_limits(monkeypatch, override, expected):
    from alma_duplicate.ui import create_app
    from tests.ui.test_runs import config
    if override is None:
        monkeypatch.delenv('ALMA_UI_BATCH_WORKERS', raising=False)
    else:
        monkeypatch.setenv('ALMA_UI_BATCH_WORKERS', override)
    monkeypatch.setenv('ALMA_UI_MAX_RETAINED_BYTES', '2147483648')
    app = create_app(config())
    try:
        assert app.config['BATCH_MAX_WORKERS'] == expected
        assert app.extensions['assessment_runs']._max_bytes == 2147483648
    finally:
        app.extensions['assessment_runs'].close()
        app.extensions['source_uploads'].close()
        app.extensions['mosaic_uploads'].close()
