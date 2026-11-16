"""Bounded overlap, shared Queue initialization and isolated progress."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

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


def test_browser_environment_limits(monkeypatch):
    from alma_duplicate.ui import create_app
    from tests.ui.test_runs import config
    monkeypatch.setenv('ALMA_UI_BATCH_WORKERS', '1')
    monkeypatch.setenv('ALMA_UI_MAX_RETAINED_BYTES', '2147483648')
    app = create_app(config())
    try:
        assert app.config['BATCH_MAX_WORKERS'] == 1
        assert app.extensions['assessment_runs']._max_bytes == 2147483648
    finally:
        app.extensions['assessment_runs'].close()
        app.extensions['source_uploads'].close()
        app.extensions['mosaic_uploads'].close()
