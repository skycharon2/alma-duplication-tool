"""Batch retention, ownership and report availability using real saved reports."""
from copy import deepcopy
import json

import pytest

from alma_duplicate.parsers.source_list import parse_source_list
from alma_duplicate.ui.run_store import RunStore
from tests.ui.test_run_store import assessment as assessment_fixture

assessment = assessment_fixture

RAW = b'name,ra,dec,redshift\nsame,0,0,0\nsame,1,1,1\n'


def create(store, owner='browser-a', purposes=('LINE', 'CONTINUUM')):
    preview = parse_source_list(RAW)
    return store.batches.create(owner, {'frequency_kind': 'REST'}, preview['sources'],
                                preview['input_sha256'], purposes)


@pytest.fixture
def store(tmp_path):
    instance = RunStore(directory=tmp_path)
    yield instance
    instance.close()


def test_order_identity_detached_manifest_and_scoped_history(store, assessment):
    batch = create(store)
    original = store.batches.get(batch, 'browser-a')
    assert [s['source_id'] for s in original['sources']] == ['line-2', 'line-3']
    assert [r['purpose'] for r in original['sources'][0]['reports']] == ['LINE', 'CONTINUUM']
    assert not original['execution_complete']
    original['sources'].clear()
    assert len(store.batches.get(batch, 'browser-a')['sources']) == 2
    assert store.batches.get(batch, 'browser-b') is None
    assert store.batches.summaries([batch, batch, 'missing'], 'browser-a') == [dict(
        batch_id=batch, created_at=original['created_at'], source_count=2, execution_complete=False)]
    assert store.batches.summaries([batch], 'browser-b') == []
    run = store.add(*assessment)
    store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'RUNNING')
    store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
    assert store.batches.lookup_run(run, 'browser-a') == dict(batch_id=batch, source_id='line-2', purpose='LINE')
    assert store.batches.lookup_run(run, 'browser-b') is None
    snapshot = store.batches.get(batch, 'browser-a')
    assert snapshot['sources'][0]['reports'][0]['availability'] == 'AVAILABLE'
    json.dumps(snapshot, allow_nan=False)


def test_failed_branch_preserves_completed_siblings_and_terminal_results(store, assessment):
    batch = create(store)
    run = store.add(*assessment)
    store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
    for source, purpose in [('line-2', 'CONTINUUM'), ('line-3', 'LINE'), ('line-3', 'CONTINUUM')]:
        store.batches.update(batch, 'browser-a', source, purpose, 'FAILED', error='Source unavailable')
    manifest = store.batches.get(batch, 'browser-a')
    assert manifest['execution_complete']
    assert manifest['sources'][0]['reports'][0]['run_id'] == run
    # Exact duplicate completion is idempotent; retry/replacement is not implicit.
    store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
    with pytest.raises(ValueError, match='Terminal'):
        store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'FAILED')
    assert store.batches.get(batch, 'browser-a') == manifest


def test_report_eviction_is_visible_and_reverse_link_survives(tmp_path, assessment):
    store = RunStore(max_runs=1, directory=tmp_path)
    try:
        batch = create(store)
        run = store.add(*assessment)
        store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
        lease = store.open_download(run, 'report')
        store.add(*assessment)
        report = store.batches.get(batch, 'browser-a')['sources'][0]['reports'][0]
        assert report['state'] == 'COMPLETED' and report['availability'] == 'EVICTED'
        assert store.batches.lookup_run(run, 'browser-a')['batch_id'] == batch
        assert json.loads(b''.join(lease))
    finally:
        store.close()


def test_older_report_expiry_then_batch_expiry_and_close(tmp_path, assessment):
    now = [0]
    store = RunStore(directory=tmp_path, max_age=10, clock=lambda: now[0])
    try:
        run = store.add(*assessment)
        now[0] = 1
        batch = create(store)
        store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
        now[0] = 10
        assert store.batches.get(batch, 'browser-a')['sources'][0]['reports'][0]['availability'] == 'EXPIRED'
        now[0] = 11
        store.prune()
        assert store.batches.get(batch, 'browser-a') is None
        assert store.batches.lookup_run(run, 'browser-a') is None
        create(store)
        store.close()
        assert store.batches.summaries([batch], 'browser-a') == []
        with pytest.raises(ValueError, match='closed'):
            create(store)
    finally:
        store.close()


def test_capacity_protects_active_batches_and_evicts_finished(tmp_path, assessment):
    store = RunStore(directory=tmp_path, max_batches=1)
    try:
        batch = create(store, purposes=['LINE'])
        with pytest.raises(ValueError, match='active'):
            create(store)
        run = store.add(*assessment)
        store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
        store.batches.update(batch, 'browser-a', 'line-3', 'LINE', 'FAILED')
        next_batch = create(store)
        assert store.batches.get(batch, 'browser-a') is None
        assert store.batches.lookup_run(run, 'browser-a') is None
        assert store.batches.get(next_batch, 'browser-a') is not None
        assert store.unavailable_reason(run) is None  # Manifest eviction does not delete report files.
    finally:
        store.close()


def test_byte_budget_failures_are_atomic(tmp_path):
    store = RunStore(directory=tmp_path, max_batch_bytes=2500)
    try:
        batch = create(store)
        before = store.batches.get(batch, 'browser-a')
        with pytest.raises(ValueError, match='budget'):
            store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'FAILED', error='x' * 2000)
        assert store.batches.get(batch, 'browser-a') == before
        preview = parse_source_list(RAW)
        with pytest.raises(ValueError, match='budget'):
            store.batches.create('browser-a', {'large': 'x' * 3000}, preview['sources'],
                                 preview['input_sha256'], ['LINE'])
        assert store.batches.get(batch, 'browser-a') == before
    finally:
        store.close()


def test_invalid_links_and_scope_cannot_mutate_manifest(store, assessment):
    batch = create(store)
    before = store.batches.get(batch, 'browser-a')
    with pytest.raises(KeyError):
        store.batches.update(batch, 'browser-b', 'line-2', 'LINE', 'RUNNING')
    for kwargs in [dict(state='COMPLETED', run_id='missing'), dict(state='COMPLETED'),
                   dict(state='FAILED', run_id='invalid'), dict(state='PENDING'),
                   dict(state='RUNNING', error='invalid')]:
        with pytest.raises(ValueError):
            store.batches.update(batch, 'browser-a', 'line-2', 'LINE', **kwargs)
    assert store.batches.get(batch, 'browser-a') == before
    run = store.add(*assessment)
    store.batches.update(batch, 'browser-a', 'line-2', 'LINE', 'COMPLETED', run_id=run)
    with pytest.raises(ValueError, match='already'):
        store.batches.update(batch, 'browser-a', 'line-3', 'LINE', 'COMPLETED', run_id=run)
    with pytest.raises(ValueError, match='Unknown'):
        store.batches.update(batch, 'browser-a', 'missing', 'LINE', 'FAILED')


def test_manifest_input_is_copied_and_invalid_sources_rejected(store):
    parsed = parse_source_list(RAW)
    setup = {'nested': [1]}
    before = deepcopy(parsed)
    batch = store.batches.create('a', setup, parsed['sources'], parsed['input_sha256'], ['LINE'])
    setup['nested'].clear()
    parsed['sources'][0]['name'] = 'changed'
    assert store.batches.get(batch, 'a')['shared_setup'] == {'nested': [1]}
    assert store.batches.get(batch, 'a')['sources'][0]['source'] == before['sources'][0]
    for sources in [[], before['sources'] * 3, [before['sources'][0]] * 2,
                    [dict(before['sources'][0], is_valid=False)]]:
        with pytest.raises(ValueError):
            store.batches.create('a', {}, sources, parsed['input_sha256'], ['LINE'])


def test_concurrent_completion_cannot_assign_one_report_twice(store, assessment):
    from concurrent.futures import ThreadPoolExecutor
    batch = create(store)
    run = store.add(*assessment)

    def attach(source):
        try:
            store.batches.update(batch, 'browser-a', source, 'LINE', 'COMPLETED', run_id=run)
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attach, ['line-2', 'line-3']))
    assert sorted(outcomes) == [False, True]
    manifest = store.batches.get(batch, 'browser-a')
    assert sum(r['run_id'] == run for s in manifest['sources'] for r in s['reports']) == 1


def test_byte_pressure_evicts_finished_manifest_only(tmp_path):
    store = RunStore(directory=tmp_path, max_batch_bytes=2500)
    try:
        batch = create(store)
        for source in ('line-2', 'line-3'):
            for purpose in ('LINE', 'CONTINUUM'):
                store.batches.update(batch, 'browser-a', source, purpose, 'FAILED')
        second = create(store)
        assert store.batches.get(batch, 'browser-a') is None
        assert store.batches.get(second, 'browser-a') is not None
    finally:
        store.close()
