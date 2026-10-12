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
from alma_duplicate.ui.run_store import RunStore, _utf8_blocks, _indexed_report_blocks
from alma_duplicate.ui.runs import BrowserAssessment

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope='module')
def assessment():
    request = json.loads((ROOT / 'examples/confirmed_line/request.json').read_bytes())
    # Storage tests also cover legacy full v4 documents, including synthetic
    # mutations unrelated to the v5 detail-policy contract.
    result = BrowserAssessment(archive_replay=ROOT / 'examples/confirmed_line/archive/manifest.json',
                               report_detail='full').assess(request)
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
    assert {p.name for p in item.directory.iterdir()} == {
        'report.json', 'inspection.json', 'request.json', 'view.json',
    }
    assert item.byte_size == sum(p.stat().st_size for p in item.directory.iterdir())
    assert result.document == before
    root = store.directory
    store.close()
    assert not root.exists()


def test_streaming_serializer_preserves_unicode_and_rejects_invalid_numbers():
    doc = {'label': '谱线 µm', 'array': [None, 1.2, {'value': True}]}
    assert ''.join(report_json_chunks(doc)) == json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with pytest.raises(ValueError):
        ''.join(report_json_chunks({'invalid': float('inf')}))


def test_batched_utf8_preserves_bytes_across_unicode_and_large_tokens():
    document = {'label': '谱线 🔭', 'large': 'µ🌌' * 100_000,
                'values': list(range(10_000))}
    blocks = list(_utf8_blocks(report_json_chunks(document)))
    assert b''.join(blocks) == report_json_text(document).encode('utf-8')
    assert all(0 < len(block) <= 256 * 1024 for block in blocks)
    assert list(_utf8_blocks(iter(['', '']))) == []
    with pytest.raises(ValueError):
        list(_utf8_blocks(report_json_chunks({'invalid': float('nan')})))


@pytest.mark.parametrize('contexts', [[], [{}], [
    {'label': '谱线 🌌 \\ " \n\t', 'nested': {'context_evaluations': [1, 2]},
     'values': [None, True, False, 1.25, -0.0, {'x': []}], 'large': 'µ🌌' * 40_000},
    {'context_id': 'next', 'empty': {}},
]])
@pytest.mark.parametrize('placement', [0, 1, 2])
def test_indexed_publication_is_byte_identical_and_ranges_decode(contexts, placement):
    items = [('before', {'名字': ['α', 3]}), ('after', [1, {}])]
    items.insert(placement, ('context_evaluations', contexts))
    document = dict(items)
    offsets = []
    raw = b''.join(_indexed_report_blocks(document, offsets))
    assert raw == report_json_text(document).encode('utf-8')
    assert len(offsets) == len(contexts)
    for (start, length), context in zip(offsets, contexts, strict=True):
        assert json.loads(raw[start:start + length]) == context
    with pytest.raises(ValueError):
        b''.join(_indexed_report_blocks({'context_evaluations': [{'x': float('nan')}]}, []))


def test_two_runs_fit_budget_without_duplicate_context_files(tmp_path, assessment):
    request, result = assessment
    # Distinct evidence checks both isolation and Unicode byte offsets.
    document = deepcopy(result.document)
    document['context_evaluations'][0]['storage_test_label'] = '另一次观测 🌌'
    changed = replace(result, document=document)
    with_store = RunStore(directory=tmp_path)
    try:
        first = with_store.add(request, result)
        second = with_store.add(request, changed)
        budget = with_store._size
    finally:
        with_store.close()
    store = RunStore(directory=tmp_path, max_bytes=budget)
    try:
        first = store.add(request, result)
        second = store.add(request, changed)
        assert store.page(first, view='all')['contexts'] == result.document['context_evaluations']
        assert store.page(second, view='all')['contexts'] == document['context_evaluations']
        for _ in range(2):
            assert download(store, first, 'report') == report_json_text(result.document).encode()
            assert download(store, second, 'report') == report_json_text(document).encode()
        assert store._size == budget
        assert not list(store.directory.rglob('contexts.jsonl'))
    finally:
        store.close()


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
    assert store.unavailable_reason(run_id) == 'EXPIRED'
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
    assert store.unavailable_reason(first) == 'EVICTED'
    assert old_dir.exists()
    lease.close()  # Also supports a response closed before iteration starts.
    assert not old_dir.exists()
    size = store._runs[second].byte_size
    store._max_bytes = size + 1024
    third = store.add(request, result)
    assert store.page(second) is None and store.page(third) is not None
    assert store.unavailable_reason(second) == 'EVICTED'
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


def test_removal_notices_are_bounded_and_session_identity_is_explicit(tmp_path, assessment, monkeypatch):
    from alma_duplicate.ui import run_store
    monkeypatch.setattr(run_store, 'MAX_REMOVAL_NOTICES', 2)
    request, result = assessment
    store = RunStore(max_runs=1, directory=tmp_path)
    other = RunStore(directory=tmp_path)
    try:
        ids = [store.add(request, result) for _ in range(4)]
        assert store.unavailable_reason(ids[-1]) is None
        assert store.unavailable_reason(ids[0]) == 'UNKNOWN'
        assert store.unavailable_reason(ids[1]) == 'EVICTED'
        assert len(store._removal_notices) == 2
        assert other.unavailable_reason(ids[-1]) == 'OTHER_SESSION'
        for invalid in ['../../outside', 'a' * 32, 'invalid.' + 'b' * 32]:
            assert other.unavailable_reason(invalid) == 'UNKNOWN'
    finally:
        store.close()
        other.close()


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
