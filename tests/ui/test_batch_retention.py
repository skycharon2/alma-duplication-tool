"""Atomic protection across count/byte pressure, concurrency and expiry."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from alma_duplicate.ui.run_store import RunStore, RetentionCapacityError
from tests.ui.test_run_store import assessment as assessment_fixture

assessment = assessment_fixture


def test_protected_publication_blocks_eviction_and_expires_with_download(tmp_path, assessment):
    now = [0]
    store = RunStore(directory=tmp_path, max_runs=1, max_age=10, clock=lambda: now[0])
    request, result = assessment
    try:
        first = store.add(request, result, protect=True)
        lease = store.open_download(first, 'request')
        with pytest.raises(RetentionCapacityError):
            store.add(request, result)
        assert store.unavailable_reason(first) is None
        assert store.retention_budget()['protected_runs'] == 1
        now[0] = 11
        store.prune()
        assert store.unavailable_reason(first) == 'EXPIRED'
        assert store.retention_budget()['protected_runs'] == 0
        assert store.retention_budget()['retired_download_bytes'] > 0
        assert b''.join(lease)
        assert store.retention_budget()['retired_download_bytes'] == 0
        assert store.add(request, result, protect=True)
        assert not list(store.directory.glob('.pending-*'))
    finally:
        store.close()


def test_parallel_publish_keeps_first_report_and_rejects_second(tmp_path, assessment):
    store = RunStore(directory=tmp_path, max_runs=1)
    def publish():
        try:
            return store.add(*assessment, protect=True)
        except RetentionCapacityError:
            return None
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: publish(), range(2)))
        saved = [r for r in results if r is not None]
        assert len(saved) == 1 and store.unavailable_reason(saved[0]) is None
        assert store.retention_budget()['protected_runs'] == 1
        assert not list(store.directory.glob('.pending-*'))
    finally:
        store.close()


def test_byte_pressure_failure_does_not_delete_evictable_or_protected_report(tmp_path, assessment):
    store = RunStore(directory=tmp_path)
    try:
        ordinary = store.add(*assessment)
        protected = store.add(*assessment, protect=True)
        # Even evicting the ordinary report cannot make this publication fit.
        store._max_bytes = store._runs[protected].byte_size + 1
        with pytest.raises(RetentionCapacityError):
            store.add(*assessment, protect=True)
        assert store.unavailable_reason(ordinary) is None
        assert store.unavailable_reason(protected) is None
        assert not list(store.directory.glob('.pending-*'))
    finally:
        store.close()


def test_later_batch_cannot_evict_completed_batch(tmp_path):
    from tests.ui.test_batch_assessment import run, values
    store = RunStore(directory=tmp_path, max_runs=2)
    try:
        first = run(store, values(intents=['LINE']), max_workers=2)
        second = run(store, values(intents=['LINE']), max_workers=2,
                     owner='browser-b', submission_token='b' * 32)
        saved = store.batches.get(first, 'browser-a')
        failed = store.batches.get(second, 'browser-b')
        assert all(r['availability'] == 'AVAILABLE' for s in saved['sources'] for r in s['reports'])
        assert all(r['state'] == 'FAILED' and 'storage capacity limit' in r['error']
                   for s in failed['sources'] for r in s['reports'])
        assert saved['storage_budget']['protected_runs'] == 2
    finally:
        store.close()


def test_capacity_can_reclaim_unprotected_report_while_preserving_protected(tmp_path, assessment):
    store = RunStore(directory=tmp_path, max_runs=2)
    try:
        protected = store.add(*assessment, protect=True)
        ordinary = store.add(*assessment)
        later = store.add(*assessment, protect=True)
        assert store.unavailable_reason(protected) is None
        assert store.unavailable_reason(later) is None
        assert store.unavailable_reason(ordinary) == 'EVICTED'
        assert store.retention_budget()['protected_runs'] == 2
    finally:
        store.close()
