from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from alma_duplicate.storage import QueueSnapshotStore, QueueSnapshotStoreError
from alma_duplicate.storage import queue_snapshots as module

FIXTURE = Path(__file__).parents[1] / "fixtures" / "queue" / "queue_pipeline_v1.csv"
FIRST = datetime(2026, 9, 1, 12, tzinfo=UTC)
SECOND = FIRST + timedelta(days=7)


def _saved(tmp_path, raw=None, **kwargs):
    store = QueueSnapshotStore(tmp_path, clock=lambda: FIRST)
    source = store.save_source(FIXTURE.read_bytes() if raw is None else raw, **kwargs)
    return store, source


def _source_path(root, source):
    return root / "sources" / source.source_id


def _change_manifest(path, update):
    obj = json.loads(path.read_text())
    update(obj)
    path.write_text(json.dumps(obj))


@pytest.mark.parametrize("retrieved", [None, FIRST])
def test_source_roundtrip_without_parser_or_clock(tmp_path, monkeypatch, retrieved):
    raw = b"\xef\xbb\xbf  exact bytes\r\n\xff\x00"
    store, saved = _saved(tmp_path, raw, retrieved_at=retrieved, source_note="old download")

    def forbidden(*args, **kwargs):
        pytest.fail("historical read must not parse or generate timestamps")

    monkeypatch.setattr(module, "parse_queue_csv_bytes", forbidden)
    reopened = QueueSnapshotStore(tmp_path, clock=forbidden)
    loaded = reopened.read_source(saved.source_id)
    assert loaded == saved
    assert loaded.raw_bytes == raw
    assert loaded.metadata["retrieved_at"] == (retrieved.isoformat() if retrieved else None)
    assert loaded.metadata["source_note"] == "old download"
    assert "parsed_at" not in loaded.metadata and "parser_version" not in loaded.metadata
    assert reopened.list_sources() == (saved.source_id,)
    with pytest.raises(TypeError):
        loaded.metadata["retrieved_at"] = "changed"


def test_same_bytes_keep_separate_acquisition_provenance(tmp_path):
    store, first = _saved(tmp_path, retrieved_at=FIRST)
    second = store.save_source(first.raw_bytes, retrieved_at=SECOND,
                               source_url="https://example.invalid/download.csv",
                               source_url_kind="DOWNLOAD_URL")
    assert first.source_id != second.source_id
    assert first.metadata["snapshot_sha256"] == second.metadata["snapshot_sha256"]
    assert first.metadata["retrieved_at"] != second.metadata["retrieved_at"]
    assert first.metadata["source_url"] != second.metadata["source_url"]
    assert len(store.list_sources()) == 2


@pytest.mark.parametrize("mutation", ["byte", "truncate", "missing_csv", "missing_manifest", "bad_json"])
def test_corrupt_or_missing_source_is_rejected(tmp_path, mutation):
    store, source = _saved(tmp_path)
    directory = _source_path(tmp_path, source)
    csv = directory / "source.csv"
    manifest = directory / "manifest.json"
    if mutation == "byte":
        raw = csv.read_bytes()
        csv.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    elif mutation == "truncate":
        csv.write_bytes(csv.read_bytes()[:-1])
    elif mutation == "missing_csv":
        csv.unlink()
    elif mutation == "missing_manifest":
        manifest.unlink()
    else:
        manifest.write_text("{")
    with pytest.raises(QueueSnapshotStoreError):
        store.read_source(source.source_id)
    with pytest.raises(QueueSnapshotStoreError):
        store.list_sources()


@pytest.mark.parametrize("field,value", [
    ("format_version", 99), ("format_version", True), ("byte_length", -1),
    ("retrieved_at", "yesterday"), ("retrieved_at", "2026-09-01T12:00:00"),
    ("source_url", ""), ("snapshot_sha256", "invalid"), ("source_id", "0" * 32),
])
def test_source_manifest_validation(tmp_path, field, value):
    store, source = _saved(tmp_path)
    path = _source_path(tmp_path, source) / "manifest.json"
    _change_manifest(path, lambda obj: obj.update({field: value}))
    with pytest.raises(QueueSnapshotStoreError):
        store.read_source(source.source_id)


def test_missing_and_duplicate_keys_rejected(tmp_path):
    store, source = _saved(tmp_path)
    path = _source_path(tmp_path, source) / "manifest.json"
    original = path.read_text()
    _change_manifest(path, lambda obj: obj.pop("retrieved_at"))
    with pytest.raises(QueueSnapshotStoreError):
        store.read_source(source.source_id)
    path.write_text(original[:-2] + ', "format_version": 1}\n')
    with pytest.raises(QueueSnapshotStoreError):
        store.read_source(source.source_id)


def test_interrupted_publish_never_lists_partial_source(tmp_path, monkeypatch):
    store = QueueSnapshotStore(tmp_path, clock=lambda: FIRST)

    def interrupt(*args):
        raise OSError("injected interruption before rename")

    monkeypatch.setattr(module.os, "rename", interrupt)
    with pytest.raises(QueueSnapshotStoreError):
        store.save_source(b"raw")
    assert store.list_sources() == ()
    # Simulate debris left by a process killed before its finally clause.
    pending = tmp_path / "sources" / ".pending-killed"
    pending.mkdir()
    (pending / "source.csv").write_bytes(b"incomplete")
    assert store.list_sources() == ()
    with pytest.raises(QueueSnapshotStoreError):
        store.read_source(".pending-killed")


def test_existing_record_is_not_overwritten(tmp_path, monkeypatch):
    store, source = _saved(tmp_path)
    monkeypatch.setattr(module, "uuid4", lambda: SimpleNamespace(hex=source.source_id))
    with pytest.raises(QueueSnapshotStoreError):
        store.save_source(b"different")
    assert store.read_source(source.source_id) == source


@pytest.mark.parametrize("raw", [None, b"\xff", b"no Queue layout"])
def test_reparse_adds_summary_without_overwriting_history(tmp_path, monkeypatch, raw):
    store, source = _saved(tmp_path, raw, legacy_captured_at=datetime(2020, 1, 1))
    source_files = {p.name: p.read_bytes() for p in _source_path(tmp_path, source).iterdir()}
    first_run, first_result = store.reparse(source.source_id)
    first_run_bytes = (tmp_path / "runs" / first_run.run_id / "manifest.json").read_bytes()
    reopened = QueueSnapshotStore(tmp_path, clock=lambda: SECOND)
    second_run, second_result = reopened.reparse(source.source_id)
    assert first_run.run_id != second_run.run_id
    assert first_result.snapshot.parsed_at == FIRST
    assert second_result.snapshot.parsed_at == SECOND
    assert first_result.snapshot.retrieved_at is second_result.snapshot.retrieved_at is None
    assert second_result.snapshot.captured_at == datetime(2020, 1, 1)
    assert source_files == {p.name: p.read_bytes() for p in _source_path(tmp_path, source).iterdir()}
    assert (tmp_path / "runs" / first_run.run_id / "manifest.json").read_bytes() == first_run_bytes
    assert first_run.summary["status"] == first_result.status.value
    assert first_run.summary["counts"]["raw_rows"] == len(first_result.raw_rows)
    if raw is not None:
        assert first_run.summary["status"] == "ERROR"
        assert first_run.summary["diagnostics"]
    monkeypatch.setattr(module, "parse_queue_csv_bytes", lambda *a, **k: pytest.fail("must not reparse history"))
    assert reopened.read_run(first_run.run_id) == first_run
    assert len(reopened.list_runs()) == 2
    with pytest.raises(TypeError):
        first_run.summary["counts"]["raw_rows"] = 999


@pytest.mark.parametrize("field,value", [
    ("format_version", 99), ("status", "invented"), ("parser_version", None),
    ("counts", {}), ("diagnostics", []), ("source_manifest_sha256", "0" * 64),
])
def test_run_summary_validation(tmp_path, field, value):
    store, source = _saved(tmp_path, b"bad CSV")
    run, _ = store.reparse(source.source_id)
    path = tmp_path / "runs" / run.run_id / "manifest.json"
    _change_manifest(path, lambda obj: obj.update({field: value}))
    with pytest.raises(QueueSnapshotStoreError):
        store.read_run(run.run_id)


def test_source_metadata_change_invalidates_run_link(tmp_path):
    store, source = _saved(tmp_path)
    run, _ = store.reparse(source.source_id)
    path = _source_path(tmp_path, source) / "manifest.json"
    _change_manifest(path, lambda obj: obj.update(source_note="changed"))
    with pytest.raises(QueueSnapshotStoreError, match="provenance mismatch"):
        store.read_run(run.run_id)


def test_parse_exception_does_not_destroy_saved_source(tmp_path, monkeypatch):
    store, source = _saved(tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError("parser bug")
    monkeypatch.setattr(module, "parse_queue_csv_bytes", fail)
    with pytest.raises(RuntimeError):
        store.reparse(source.source_id)
    assert store.read_source(source.source_id) == source
    assert store.list_runs() == ()


def test_run_publish_interruption_preserves_source_and_previous_run(tmp_path, monkeypatch):
    store, source = _saved(tmp_path)
    run, _ = store.reparse(source.source_id)

    def interrupt(*args):
        raise OSError("injected run publication failure")

    monkeypatch.setattr(module.os, "rename", interrupt)
    with pytest.raises(QueueSnapshotStoreError):
        store.reparse(source.source_id)
    assert store.read_source(source.source_id) == source
    assert store.read_run(run.run_id) == run
    assert store.list_runs() == (run.run_id,)


def test_new_process_reads_history_without_parser(tmp_path):
    store, source = _saved(tmp_path, retrieved_at=FIRST)
    run, _ = store.reparse(source.source_id)
    program = '''
import sys
from alma_duplicate.storage import QueueSnapshotStore
from alma_duplicate.storage import queue_snapshots
def forbidden(*args, **kwargs):
    raise AssertionError("historical read must not run parser")
queue_snapshots.parse_queue_csv_bytes = forbidden
store = QueueSnapshotStore(sys.argv[1], clock=forbidden)
source = store.read_source(sys.argv[2])
run = store.read_run(sys.argv[3])
assert source.metadata["retrieved_at"] == sys.argv[4]
assert run.summary["snapshot_sha256"] == source.metadata["snapshot_sha256"]
sys.stdout.buffer.write(source.raw_bytes)
'''
    completed = subprocess.run(
        [sys.executable, "-c", program, str(tmp_path), source.source_id,
         run.run_id, FIRST.isoformat()], capture_output=True, check=True,
    )
    assert completed.stdout == source.raw_bytes
