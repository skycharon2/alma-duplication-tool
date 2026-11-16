"""Offline execution parity, fixed snapshots and branch-failure isolation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.batch_assessment import BatchValidationError, execute_batch
from alma_duplicate.ui.proposed import validate_form
from alma_duplicate.ui.run_store import RunStore
from alma_duplicate.ui.runs import BrowserAssessment
from tests.ui.test_batch_requests import form, ROW
from tests.ui.test_cli_parity import normalized_times

ROOT = Path(__file__).parents[2]
RAW = b'name,ra,dec,redshift\nfirst,201.365,-43.019,0.024\nsecond,201.365,-43.019,0\n'
TOKEN = 'a' * 32


def values(v2=False, intents=None, kind='SKY', sources=None):
    return form(v2, intents or ['LINE', 'CONTINUUM'], kind) | dict(
        radius_mode='EXPLICIT', radius='30', sources=sources or ['ARCHIVE', 'QUEUE'])


def runner(queue=None):
    return BrowserAssessment(
        archive_replay=str(ROOT / 'examples/confirmed_line/archive/manifest.json'),
        queue_csv=str(queue or ROOT / 'examples/acceptance/queue/dual-source-line.csv'))


@pytest.fixture
def store(tmp_path):
    instance = RunStore(directory=tmp_path)
    yield instance
    instance.close()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request',
                        lambda *a, **k: pytest.fail('Unexpected external source access'))


def run(store, data=None, **kwargs):
    return execute_batch(data or values(), [ROW], RAW, runs=store,
                         owner=kwargs.pop('owner', 'browser-a'), submission_token=kwargs.pop('submission_token', TOKEN),
                         runner=kwargs.pop('runner', runner()),
                         **kwargs)


def downloaded(store, run_id, kind):
    return json.loads(b''.join(store.open_download(run_id, kind)))


@pytest.mark.parametrize('v2', [False, True])
@pytest.mark.parametrize('intents', [['LINE'], ['CONTINUUM'], ['LINE', 'CONTINUUM']])
@pytest.mark.parametrize('kind', ['SKY', 'REST'])
def test_saved_reports_equal_independently_submitted_targets(store, v2, intents, kind):
    data = values(v2, intents, kind)
    before = deepcopy(data)
    fixed_runner = runner().pin_queue_for_submission(True)
    batch_id = run(store, data, runner=fixed_runner)
    manifest = store.batches.get(batch_id, 'browser-a')
    assert manifest['execution_complete'] and data == before
    for source in manifest['sources']:
        metadata = source['source']
        for report in source['reports']:
            assert report['state'] == 'COMPLETED' and report['availability'] == 'AVAILABLE', report
            standalone = data | dict(target_name=metadata['name'], ra=metadata['original']['ra'],
                dec=metadata['original']['dec'], ra_format='DEG', dec_format='DEG',
                redshift=metadata['redshift'], frequency_local_redshift='0', continuum_redshift='',
                intents=[report['purpose']], **{ROW + '_redshift': ''})
            document, validation, _ = validate_form(standalone, [ROW], require_line_complete=True)
            assert validation.is_valid and validation.can_search
            assert downloaded(store, report['run_id'], 'request') == document
            direct = fixed_runner.assess(document)
            expected = json.loads(report_json_text(direct.document))
            actual = downloaded(store, report['run_id'], 'report')
            assert all(s['status'] == 'COMPLETED' for s in actual['sources'].values())
            assert actual['context_evaluations']
            assert normalized_times(actual) == normalized_times(expected)


def test_one_snapshot_and_order_even_when_csv_changes(store, tmp_path, monkeypatch):
    csv_path = tmp_path / 'queue.csv'
    original_bytes = (ROOT / 'examples/acceptance/queue/dual-source-line.csv').read_bytes()
    csv_path.write_bytes(original_bytes)
    calls, pins, snapshots, events = [], [], [], []
    assess, pin = BrowserAssessment.assess, BrowserAssessment.pin_queue_for_submission
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient
    parse = QueueCsvClient.parse_bytes

    def parse_once(self, raw, *args, **kwargs):
        snapshots.append(raw)
        return parse(self, raw, *args, **kwargs)

    def pinned(self, selected):
        pins.append(selected)
        return pin(self, selected)

    def assess_after_change(self, document):
        calls.append((document['request']['target_name'], document['request']['intents'][0]))
        csv_path.write_bytes(b'changed after snapshot pinning')
        return assess(self, document)

    monkeypatch.setattr(QueueCsvClient, 'parse_bytes', parse_once)
    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', pinned)
    monkeypatch.setattr(BrowserAssessment, 'assess', assess_after_change)
    batch = run(store, runner=runner(csv_path), progress=events.append)
    assert pins == [True] and snapshots == [original_bytes]
    assert calls == [('first', 'LINE'), ('first', 'CONTINUUM'), ('second', 'LINE'), ('second', 'CONTINUUM')]
    assert events[-1]['stage'] == 'batch_finished' and events[-1]['batch_completed'] == 4
    assert {e['source_id'] for e in events if e['source_id']} == {'line-2', 'line-3'}
    assert all(e['batch_id'] == batch for e in events)


@pytest.mark.parametrize('failure', ['raise', 'no_report', 'storage'])
def test_branch_failure_does_not_stop_later_work(store, monkeypatch, failure):
    assess, add = BrowserAssessment.assess, store.add
    calls = []

    def assessment(self, document):
        calls.append(document['request']['target_name'])
        if len(calls) == 2:
            if failure == 'raise':
                raise RuntimeError('source error')
            if failure == 'no_report':
                return SimpleNamespace(document=None)
        return assess(self, document)

    def storage(document, result):
        if len(calls) == 2:
            raise OSError('disk full')
        return add(document, result)

    monkeypatch.setattr(BrowserAssessment, 'assess', assessment)
    if failure == 'storage':
        monkeypatch.setattr(store, 'add', storage)
    batch = run(store)
    manifest = store.batches.get(batch, 'browser-a')
    assert manifest['execution_complete'] and len(calls) == 4
    assert [r['state'] for s in manifest['sources'] for r in s['reports']] == [
        'COMPLETED', 'FAILED', 'COMPLETED', 'COMPLETED']


def test_preflight_all_targets_before_any_pinning(store, monkeypatch):
    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission',
                        lambda *a: pytest.fail('pinning before complete preflight'))
    with pytest.raises(BatchValidationError) as caught:
        execute_batch(values(kind='REST'), [ROW], RAW.replace(b',0\n', b',\n'), runner=runner(),
                      runs=store, owner='browser-a', submission_token=TOKEN)
    assert not caught.value.preflights['LINE']['can_search']
    with pytest.raises(ValueError, match='submission'):
        run(store, submission_token=None)


def test_duplicate_submission_is_atomic_while_first_call_is_running(store, monkeypatch):
    started, release = Event(), Event()
    original = BrowserAssessment.assess
    calls = []

    def blocked(self, document):
        calls.append(document)
        if len(calls) == 1:
            started.set()
            assert release.wait(10)
        return original(self, document)

    monkeypatch.setattr(BrowserAssessment, 'assess', blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, store)
        try:
            assert started.wait(10)
            repeated = pool.submit(run, store).result(timeout=10)
            assert not store.batches.get(repeated, 'browser-a')['execution_complete']
            assert len(calls) == 1
        finally:
            release.set()
        assert first.result(timeout=10) == repeated
    assert run(store) == repeated and len(calls) == 4
    with pytest.raises(ValueError, match='different inputs'):
        run(store, values() | {'angular': '0.4'})
    assert len(calls) == 4


def test_manifest_capacity_checked_before_source_access(tmp_path, monkeypatch):
    store = RunStore(directory=tmp_path, max_batch_bytes=100)
    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', lambda *a: pytest.fail('source touched'))
    try:
        with pytest.raises(ValueError, match='budget'):
            run(store)
    finally:
        store.close()


def test_progress_observer_failure_does_not_change_execution(store):
    def broken(event):
        raise RuntimeError('observer unavailable')
    batch = run(store, values(intents=['LINE']), progress=broken)
    assert store.batches.get(batch, 'browser-a')['execution_complete']


def test_source_setup_exception_marks_every_branch_without_assessing(store, monkeypatch):
    def failed(*args):
        raise OSError('snapshot unavailable')
    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', failed)
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('assessment invoked'))
    batch = run(store)
    manifest = store.batches.get(batch, 'browser-a')
    assert manifest['execution_complete']
    assert all(r['state'] == 'FAILED' for s in manifest['sources'] for r in s['reports'])


@pytest.mark.parametrize('source', ['ARCHIVE', 'QUEUE'])
def test_selected_source_scope_is_preserved(store, monkeypatch, source):
    pins = []
    original = BrowserAssessment.pin_queue_for_submission

    def pin(self, selected):
        pins.append(selected)
        return original(self, selected)

    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', pin)
    batch = run(store, values(intents=['LINE'], sources=[source]))
    assert pins == [source == 'QUEUE']
    for child in store.batches.get(batch, 'browser-a')['sources']:
        report = downloaded(store, child['reports'][0]['run_id'], 'report')
        assert report['sources'][source]['status'] == 'COMPLETED'
        other = 'QUEUE' if source == 'ARCHIVE' else 'ARCHIVE'
        assert report['sources'][other]['status'] == 'NOT_SELECTED'


def test_real_missing_snapshot_failure_is_frozen_for_every_branch(store, tmp_path, monkeypatch):
    missing = tmp_path / 'not-yet-present.csv'
    original = BrowserAssessment.assess

    def assess(self, document):
        missing.write_bytes((ROOT / 'examples/acceptance/queue/dual-source-line.csv').read_bytes())
        return original(self, document)

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    batch = run(store, runner=runner(missing))
    manifest = store.batches.get(batch, 'browser-a')
    for source in manifest['sources']:
        for branch in source['reports']:
            # Source failure is evidence in a saved report, not a fabricated empty success.
            assert branch['state'] == 'COMPLETED'
            report = downloaded(store, branch['run_id'], 'report')
            assert report['sources']['QUEUE']['status'] == 'FAILED'
            assert report['sources']['ARCHIVE']['status'] == 'COMPLETED'


def test_five_targets_ten_reports_and_eviction_remains_explicit(tmp_path):
    raw = b'name,ra,dec,redshift\n' + b''.join(
        f'target-{i},201.365,-43.019,0.024\n'.encode() for i in range(5))
    store = RunStore(directory=tmp_path, max_runs=2)
    try:
        batch = execute_batch(values(), [ROW], raw, runs=store, runner=runner(),
                              owner='browser-a', submission_token=TOKEN)
        manifest = store.batches.get(batch, 'browser-a')
        reports = [r for s in manifest['sources'] for r in s['reports']]
        assert manifest['execution_complete'] and len(reports) == 10
        assert all(r['state'] == 'COMPLETED' for r in reports)
        assert [r['availability'] for r in reports] == ['EVICTED'] * 8 + ['AVAILABLE'] * 2
    finally:
        store.close()


def test_expired_parent_stops_subsequent_queries(tmp_path, monkeypatch):
    now = [0]
    store = RunStore(directory=tmp_path, max_age=10, clock=lambda: now[0])
    original = BrowserAssessment.assess
    calls = []

    def assess(self, document):
        calls.append(document)
        result = original(self, document)
        now[0] = 11
        return result

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    try:
        with pytest.raises(KeyError, match='unavailable'):
            run(store)
        assert len(calls) == 1
    finally:
        store.close()


def test_same_token_is_scoped_to_owner(store):
    first = run(store, values(intents=['LINE']))
    second = run(store, values(intents=['LINE']), owner='browser-b')
    assert first != second
    assert store.batches.get(second, 'browser-a') is None


def test_managed_queue_activation_during_batch_does_not_change_snapshot(store, tmp_path, monkeypatch):
    from tests.ui.test_managed_queue import acquired, FIXTURE, NOW
    from alma_duplicate.storage.queue_active import QueueActiveRegistry
    root = tmp_path / 'managed'
    first = acquired(root)
    registry = QueueActiveRegistry(root, clock=lambda: NOW)
    registry.activate(first['source_id'], first['run_id'], reason='Initial test snapshot')
    second = acquired(root, FIXTURE.read_bytes().replace(b'2026 March 3.', b'2026 March 10.'))
    original = BrowserAssessment.assess
    changed = []

    def assess(self, document):
        if not changed:
            registry.activate(second['source_id'], second['run_id'], reason='Later test snapshot')
            changed.append(True)
        return original(self, document)

    monkeypatch.setattr(BrowserAssessment, 'assess', assess)
    managed = BrowserAssessment(managed_queue_root=str(root))
    batch = run(store, values(sources=['QUEUE']), runner=managed)
    for source in store.batches.get(batch, 'browser-a')['sources']:
        for branch in source['reports']:
            report = downloaded(store, branch['run_id'], 'report')
            assert report['sources']['QUEUE']['managed_snapshot']['source_id'] == first['source_id']
            assert report['sources']['QUEUE']['managed_snapshot']['source_as_of'] == '2026-03-03'
    assert registry.current()['source_id'] == second['source_id']
