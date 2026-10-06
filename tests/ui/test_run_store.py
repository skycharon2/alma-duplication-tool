"""Disk lifecycle, indexed reads and immutable browser run downloads."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alma_duplicate.reporting import report_json_text, report_json_chunks
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.ui.run_store import RunStore
from alma_duplicate.ui.runs import BrowserAssessment

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope='module')
def assessment():
    request = json.loads((ROOT / 'examples/confirmed_line/request.json').read_bytes())
    result = BrowserAssessment(archive_replay=ROOT / 'examples/confirmed_line/archive/manifest.json').assess(request)
    return request, result


@pytest.fixture
def store(tmp_path):
    instance = RunStore(directory=tmp_path)
    yield instance
    instance.close()


def download(store, run_id, kind):
    lease = store.open_download(run_id, kind)
    assert lease is not None
    raw = b''.join(lease)
    assert len(raw) == lease.size
    return raw


def test_exact_exports_private_files_and_only_descriptors_retained(store, assessment):
    request, result = assessment
    before = deepcopy(result.document)
    run_id = store.add(request, result)
    assert download(store, run_id, 'report') == report_json_text(result.document).encode()
    assert download(store, run_id, 'inspection') == report_json_text(inspect_report(result.document, inspection_version='3')).encode()
    assert download(store, run_id, 'request') == report_json_text(request).encode()
    item = store._runs[run_id]
    assert not hasattr(item, 'document') and not hasattr(item, 'raw')
    assert store.directory.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in item.directory.iterdir())
    assert item.sha256 == hashlib.sha256(download(store, run_id, 'report')).hexdigest()
    assert result.document == before
    root = store.directory
    store.close()
    assert not root.exists()


def test_streaming_serializer_preserves_unicode_and_rejects_invalid_numbers():
    doc = {'label': '谱线 µm', 'array': [None, 1.2, {'value': True}]}
    assert ''.join(report_json_chunks(doc)) == json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with pytest.raises(ValueError):
        ''.join(report_json_chunks({'invalid': float('inf')}))


def test_large_report_exceeds_old_limit_but_default_store_and_small_page_work(store, assessment, monkeypatch):
    request, result = assessment
    document = deepcopy(result.document)
    context = document['context_evaluations'][0]
    context['retained_test_evidence'] = 'x' * (33 * 1024 * 1024)
    for c in document['context_evaluations']:
        for branch in c['branches']:
            branch['status'] = 'CRITERIA_NOT_MET'
    run_id = store.add(request, replace(result, document=document))
    assert store._runs[run_id].downloads['report'][0] > 32 * 1024 * 1024
    original_read = Path.read_bytes
    def read_only_index(path):
        assert path.name == 'view.json', 'Page loaded a whole report or inspection'
        return original_read(path)
    monkeypatch.setattr(Path, 'read_bytes', read_only_index)
    page = store.page(run_id)
    assert page['contexts'] == [] and page['match_count'] == 0
    assert 'context_evaluations' not in page['document']
    assert len(json.dumps({k:v for k,v in page.items() if k not in ('item','run')})) < 1024 * 1024
    lease = store.open_download(run_id, 'report')
    digest = hashlib.sha256()
    for chunk in lease:
        assert len(chunk) <= 64 * 1024
        digest.update(chunk)
    assert digest.hexdigest() == store._runs[run_id].sha256


def test_audit_page_reads_only_indexed_contexts(store, assessment, monkeypatch):
    request, result = assessment
    document = deepcopy(result.document)
    original = document['context_evaluations'][0]
    document['context_evaluations'] = [dict(original, context_id=f'context-{i}') for i in range(41)]
    run_id = store.add(request, replace(result, document=document))
    original_loads = json.loads
    context_reads = []
    def loads(data, *args, **kwargs):
        value = original_loads(data, *args, **kwargs)
        if isinstance(value, dict) and 'context_id' in value:
            context_reads.append(value['context_id'])
        return value
    monkeypatch.setattr(json, 'loads', loads)
    page = store.page(run_id, page=2, view='all')
    assert page['context_indices'] == list(range(20, 40))
    assert context_reads == [f'context-{i}' for i in range(20, 40)]
    with pytest.raises(IndexError):
        store.page(run_id, page=4, view='all')


def test_expiry_and_active_download_finish_before_files_are_deleted(tmp_path, assessment):
    request, result = assessment
    now = [100]
    store = RunStore(directory=tmp_path, max_age=10, clock=lambda: now[0])
    run_id = store.add(request, result)
    directory = store._runs[run_id].directory
    lease = store.open_download(run_id, 'report')
    now[0] = 110
    assert store.page(run_id) is None
    assert store.open_download(run_id, 'report') is None
    assert directory.exists()
    assert b''.join(lease) == report_json_text(result.document).encode()
    assert not directory.exists()
    store.close()


def test_count_and_byte_eviction_do_not_truncate_active_download(tmp_path, assessment):
    request, result = assessment
    store = RunStore(max_runs=1, directory=tmp_path)
    first = store.add(request, result)
    lease = store.open_download(first, 'report')
    old_dir = store._runs[first].directory
    second = store.add(request, result)
    assert store.page(first) is None and store.page(second) is not None
    assert old_dir.exists()
    lease.close()  # Also supports a response closed before iteration starts.
    assert not old_dir.exists()
    size = store._runs[second].byte_size
    store._max_bytes = size + 1024
    third = store.add(request, result)
    assert store.page(second) is None and store.page(third) is not None
    assert store._size <= store._max_bytes
    store.close()


def test_oversized_or_failed_write_keeps_existing_run_and_removes_staging(store, assessment, monkeypatch):
    request, result = assessment
    first = store.add(request, result)
    document = deepcopy(result.document)
    document['too_large'] = 'x' * 4096
    store._max_bytes = 100
    with pytest.raises(ValueError, match='disk retention'):
        store.add(request, replace(result, document=document))
    assert store.page(first) is not None
    assert not list(store.directory.glob('.pending-*'))
    store._max_bytes = 1024 * 1024 * 1024
    original_open = Path.open
    def fail(path, *args, **kwargs):
        if path.name == 'inspection.json' and args == ('xb',):
            raise OSError('simulated disk full')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail)
    with pytest.raises(OSError, match='simulated disk full'):
        store.add(request, result)
    assert store.page(first) is not None
    assert not list(store.directory.glob('.pending-*'))


def test_leased_bytes_count_toward_disk_budget_and_close_waits_for_download(tmp_path, assessment):
    request, result = assessment
    store = RunStore(max_runs=1, directory=tmp_path)
    first = store.add(request, result)
    store._max_bytes = store._runs[first].byte_size + 1024
    lease = store.open_download(first, 'request')
    with pytest.raises(ValueError, match='active downloads'):
        store.add(request, result)
    assert store.page(first) is not None
    assert not list(store.directory.glob('.pending-*'))
    store.close()
    assert store.directory.exists()
    lease.close()
    assert not store.directory.exists()


def test_invalid_ids_never_become_paths_and_bad_reports_never_publish(store, assessment):
    request, result = assessment
    assert store.page('../../outside') is None
    assert store.open_download('../../outside', 'report') is None
    with pytest.raises(ValueError):
        store.open_download('anything', '../outside')
    with pytest.raises(ValueError):
        store.add(request, SimpleNamespace(document=None))
    broken = deepcopy(result.document)
    broken['context_evaluations'][0].pop('criteria')
    with pytest.raises((ValueError, KeyError)):
        store.add(request, replace(result, document=broken))
    assert not list(store.directory.iterdir())


def test_close_waits_for_staged_write_and_rejects_later_add(store, assessment, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    request, result = assessment
    entered, release, close_started = Event(), Event(), Event()
    original = store._add

    def paused_add(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    def close():
        close_started.set()
        store.close()

    monkeypatch.setattr(store, '_add', paused_add)
    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(store.add, request, result)
        assert entered.wait(5)
        closer = executor.submit(close)
        try:
            assert close_started.wait(5)
            assert not closer.done()
            assert store.directory.exists()
        finally:
            release.set()
        writer.result(timeout=10)
        closer.result(timeout=10)
    assert not store.directory.exists()
    with pytest.raises(ValueError, match='closed'):
        store.add(request, result)
