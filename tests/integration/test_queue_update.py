"""Use the committed 13-row Queue regression fixture, never live ALMA HTTP."""

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_update import (
    QueueUpdateBusyError, _exclusive_update_lock, run_update,
)
from alma_duplicate.clients.queue_downloader import DownloadedQueue, QueueDownloadError
from alma_duplicate.storage import QueueSnapshotStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "queue" / "queue_pipeline_v1.csv"
URL = "https://almascience.eso.org/documents-and-tools/latest/duplication-check-csv"
T0 = datetime(2026, 10, 14, 8, tzinfo=UTC)
T1 = datetime(2026, 10, 15, 8, tzinfo=UTC)


def delivery(raw, time=T0):
    return lambda: DownloadedQueue(raw, URL, time)


def history(root):
    return [json.loads(line) for line in (root / "checks.jsonl").read_text().splitlines()]


def test_valid_first_acquisition_and_unchanged_followup(tmp_path):
    raw = FIXTURE.read_bytes()
    first = run_update(tmp_path, downloader=delivery(raw), clock=lambda: T0)
    assert first["status"] == "NEW_VALIDATED"
    assert first["activated"] is False
    assert first["source_as_of"] == "2026-03-03"
    assert first["snapshot_sha256"] == sha256(raw).hexdigest()
    store = QueueSnapshotStore(tmp_path)
    source = store.read_source(first["source_id"])
    assert source.raw_bytes == raw
    assert source.metadata["source_url_kind"] == "DOWNLOAD_URL"
    assert source.metadata["retrieved_at"] == T0.isoformat()
    second = run_update(tmp_path, downloader=delivery(raw, T1), clock=lambda: T1)
    assert second["status"] == "UNCHANGED"
    assert second["source_id"] == first["source_id"]
    assert store.list_sources() == (first["source_id"],)
    assert store.list_runs() == (first["run_id"],)
    assert [item["status"] for item in history(tmp_path)] == ["NEW_VALIDATED", "UNCHANGED"]
    assert not (tmp_path / "current.json").exists()


def test_changed_content_creates_a_new_preserved_source(tmp_path):
    raw = FIXTURE.read_bytes()
    changed = raw.replace(b"NGC6240", b"NGC6241", 1)
    assert changed != raw
    a = run_update(tmp_path, downloader=delivery(raw), clock=lambda: T0)
    b = run_update(tmp_path, downloader=delivery(changed, T1), clock=lambda: T1)
    assert a["status"] == b["status"] == "NEW_VALIDATED"
    assert a["source_id"] != b["source_id"]
    store = QueueSnapshotStore(tmp_path)
    assert store.read_source(a["source_id"]).raw_bytes == raw
    assert store.read_source(b["source_id"]).raw_bytes == changed
    assert len(store.list_runs()) == 2


def test_invalid_content_stored_but_never_accepted_or_duplicated(tmp_path):
    raw = b"not a Queue CSV\n"
    first = run_update(tmp_path, downloader=delivery(raw), clock=lambda: T0)
    assert first["status"] == "VALIDATION_FAILED"
    source = QueueSnapshotStore(tmp_path).read_source(first["source_id"])
    assert source.raw_bytes == raw
    second = run_update(tmp_path, downloader=delivery(raw, T1), clock=lambda: T1)
    assert second["status"] == "KNOWN_INVALID"
    assert len(QueueSnapshotStore(tmp_path).list_sources()) == 1
    assert len(QueueSnapshotStore(tmp_path).list_runs()) == 1


def test_failed_download_does_not_modify_old_evidence(tmp_path):
    raw = FIXTURE.read_bytes()
    first = run_update(tmp_path, downloader=delivery(raw), clock=lambda: T0)
    original_source = QueueSnapshotStore(tmp_path).read_source(first["source_id"])

    def offline():
        raise QueueDownloadError("offline")

    second = run_update(tmp_path, downloader=offline, clock=lambda: T1)
    assert second["status"] == "DOWNLOAD_FAILED"
    assert len(QueueSnapshotStore(tmp_path).list_sources()) == 1
    assert QueueSnapshotStore(tmp_path).read_source(first["source_id"]) == original_source
    assert history(tmp_path)[-1]["status"] == "DOWNLOAD_FAILED"


def test_orphaned_source_reparsed_without_duplicate_download(tmp_path):
    raw = FIXTURE.read_bytes()
    original = QueueSnapshotStore(tmp_path).save_source(raw)
    result = run_update(tmp_path, downloader=delivery(raw), clock=lambda: T0)
    assert result["status"] == "NEW_VALIDATED"
    assert result["source_id"] == original.source_id
    assert len(QueueSnapshotStore(tmp_path).list_sources()) == 1


def test_no_activation_and_no_flask_changes(tmp_path):
    result = run_update(tmp_path, downloader=delivery(FIXTURE.read_bytes()), clock=lambda: T0)
    assert result["activated"] is False
    assert not (tmp_path / "current.json").exists()
    assert not (tmp_path / "latest.csv").exists()


def test_concurrent_check_cannot_enter(tmp_path):
    with _exclusive_update_lock(tmp_path):
        with pytest.raises(QueueUpdateBusyError):
            run_update(tmp_path, downloader=lambda: pytest.fail("must not download"),
                       clock=lambda: T0)


def test_new_invalid_does_not_modify_previously_valid_evidence(tmp_path):
    good = run_update(tmp_path, downloader=delivery(FIXTURE.read_bytes()), clock=lambda: T0)
    original = QueueSnapshotStore(tmp_path).read_source(good["source_id"])
    bad = run_update(tmp_path, downloader=delivery(b"new invalid layout", T1),
                     clock=lambda: T1)
    assert bad["status"] == "VALIDATION_FAILED"
    assert QueueSnapshotStore(tmp_path).read_source(good["source_id"]) == original
    assert not (tmp_path / "current.json").exists()
