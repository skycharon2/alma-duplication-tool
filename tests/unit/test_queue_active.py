"""PR2 registry contract: real append-only Queue snapshots, no network."""

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from alma_duplicate.storage import QueueSnapshotStore
from alma_duplicate.storage.queue_active import (
    QueueActiveBusyError, QueueActiveError, QueueActiveRegistry,
    _selection_lock,
)
from alma_duplicate.cli.queue_active import main

FIXTURE = Path(__file__).parents[1] / "fixtures" / "queue" / "queue_pipeline_v1.csv"
URL = "https://almascience.eso.org/documents-and-tools/cycle13/duplication-check-csv"
TODAY = datetime(2026, 10, 14, 12, tzinfo=UTC)


def evidence(root, raw=None, *, url=URL, kind="DOWNLOAD_URL"):
    store = QueueSnapshotStore(root, clock=lambda: TODAY)
    source = store.save_source(FIXTURE.read_bytes() if raw is None else raw,
                               source_url=url, source_url_kind=kind,
                               retrieved_at=TODAY)
    run, parsed = store.reparse(source.source_id)
    assert parsed.can_reconstruct
    return source, run


def registry(root):
    return QueueActiveRegistry(root, clock=lambda: TODAY)


def select(manager, source, run, *, reason="Researcher reviewed official source"):
    return manager.activate(source.source_id, run.run_id, reason=reason)


def test_first_activation_roundtrip_restart_and_no_evidence_writes(tmp_path):
    source, run = evidence(tmp_path)
    manager = registry(tmp_path)
    assert manager.current() is None
    before_source = (tmp_path / "sources" / source.source_id / "source.csv").read_bytes()
    before_run = (tmp_path / "runs" / run.run_id / "manifest.json").read_bytes()
    first = select(manager, source, run)
    assert first["status"] == "ACTIVATED"
    active = first["active"]
    assert active["source_id"] == source.source_id
    assert active["run_id"] == run.run_id
    assert active["source_as_of"] == "2026-03-03"
    assert active["snapshot_sha256"] == source.metadata["snapshot_sha256"]
    assert active["source_manifest_sha256"] == source.manifest_sha256
    assert active["recent_history"] == []
    assert registry(tmp_path).current() == active
    assert select(manager, source, run)["status"] == "ALREADY_ACTIVE"
    assert registry(tmp_path).current() == active
    assert (tmp_path / "sources" / source.source_id / "source.csv").read_bytes() == before_source
    assert (tmp_path / "runs" / run.run_id / "manifest.json").read_bytes() == before_run
    assert not (tmp_path / "checks.jsonl").exists()


def test_newer_activation_and_explicit_history_rollback(tmp_path):
    old_source, old_run = evidence(tmp_path)
    manager = registry(tmp_path)
    old = select(manager, old_source, old_run)["active"]
    changed = FIXTURE.read_bytes().replace(b"2026 March 3.", b"2026 March 10.", 1)
    newer_source, newer_run = evidence(tmp_path, changed)
    assert newer_run.summary["source_as_of"] == "2026-03-10"
    new = select(manager, newer_source, newer_run)["active"]
    assert new["source_as_of"] == "2026-03-10"
    assert len(new["recent_history"]) == 1
    assert new["recent_history"][0]["revision"] == old["revision"]
    with pytest.raises(QueueActiveError, match="older data requires"):
        select(manager, old_source, old_run)
    rolled = manager.rollback(old["revision"], reason="Scientific review requested prior snapshot")
    assert rolled["status"] == "ROLLED_BACK"
    assert rolled["rolled_back_to"] == old["revision"]
    assert rolled["active"]["source_id"] == old_source.source_id
    assert rolled["active"]["revision"] not in {new["revision"], old["revision"]}
    assert len(rolled["active"]["recent_history"]) == 2
    assert QueueSnapshotStore(tmp_path).list_sources() == tuple(sorted(
        (old_source.source_id, newer_source.source_id)))


def test_same_date_changed_bytes_require_explicit_approval(tmp_path):
    source, run = evidence(tmp_path)
    manager = registry(tmp_path)
    select(manager, source, run)
    changed = FIXTURE.read_bytes().replace(b"NGC6240", b"NGC6241", 1)
    replacement, new_run = evidence(tmp_path, changed)
    with pytest.raises(QueueActiveError, match="same-date changed bytes"):
        select(manager, replacement, new_run)
    adopted = manager.activate(replacement.source_id, new_run.run_id,
                               reason="Reviewed official corrected same-date export",
                               allow_same_date_change=True)
    assert adopted["status"] == "ACTIVATED"


def test_mismatched_run_source_is_refused_without_pointer(tmp_path):
    source1, _ = evidence(tmp_path)
    source2, run2 = evidence(tmp_path)
    with pytest.raises(QueueActiveError, match="does not bind"):
        select(registry(tmp_path), source1, run2)
    assert not (tmp_path / "current.json").exists()
    assert source1.source_id != source2.source_id


def test_unofficial_source_and_missing_timestamp_are_refused(tmp_path):
    source, run = evidence(tmp_path, url="https://example.org/duplication-check-csv")
    with pytest.raises(QueueActiveError, match="official Queue CSV"):
        select(registry(tmp_path), source, run)
    other, other_run = evidence(tmp_path, kind="SOURCE_PAGE")
    with pytest.raises(QueueActiveError, match="download provenance"):
        select(registry(tmp_path), other, other_run)


def test_current_refuses_corrupt_source_and_keeps_pointer(tmp_path):
    source, run = evidence(tmp_path)
    manager = registry(tmp_path)
    select(manager, source, run)
    pointer_before = (tmp_path / "current.json").read_bytes()
    source_path = tmp_path / "sources" / source.source_id / "source.csv"
    source_path.write_bytes(b"corrupted")
    with pytest.raises(QueueActiveError, match="missing or corrupt"):
        manager.current()
    assert (tmp_path / "current.json").read_bytes() == pointer_before


def test_corrupt_pointer_duplicate_keys_and_symlink_are_refused(tmp_path):
    source, run = evidence(tmp_path)
    manager = registry(tmp_path)
    select(manager, source, run)
    path = tmp_path / "current.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps(data)[:-1] + ', "reason": "forged"}')
    with pytest.raises(QueueActiveError, match="duplicate pointer"):
        manager.current()
    path.unlink()
    path.symlink_to(tmp_path / "outside.json")
    with pytest.raises(QueueActiveError, match="cannot read active pointer safely"):
        manager.current()
    with pytest.raises(QueueActiveError, match="cannot read active pointer safely|refusing symlink"):
        select(manager, source, run)


def test_atomic_publish_failure_does_not_change_old_selection(tmp_path, monkeypatch):
    source, run = evidence(tmp_path)
    manager = registry(tmp_path)
    first = select(manager, source, run)["active"]
    next_source, next_run = evidence(tmp_path, FIXTURE.read_bytes().replace(
        b"2026 March 3.", b"2026 March 10.", 1))
    from alma_duplicate.storage import queue_active as module
    def interrupt(*args):
        raise OSError("injected replacement failure")
    monkeypatch.setattr(module.os, "replace", interrupt)
    with pytest.raises(OSError, match="injected"):
        select(manager, next_source, next_run)
    assert manager.current() == first
    assert not list(tmp_path.glob(".current-pending-*"))


def test_update_lock_refuses_concurrent_selection(tmp_path):
    source, run = evidence(tmp_path)
    with _selection_lock(tmp_path):
        with pytest.raises(QueueActiveBusyError):
            select(registry(tmp_path), source, run)
    assert registry(tmp_path).current() is None


def test_rollback_only_accepts_known_history_and_requires_reason(tmp_path):
    source, run = evidence(tmp_path)
    manager = registry(tmp_path)
    first = select(manager, source, run)["active"]
    with pytest.raises(QueueActiveError, match="revision not in"):
        manager.rollback("a" * 32, reason="try to bypass")
    with pytest.raises(QueueActiveError, match="revision not in"):
        manager.rollback(first["revision"], reason="test")
    with pytest.raises(QueueActiveError, match="activation reason"):
        manager.activate(source.source_id, run.run_id, reason=" ")


def test_cli_status_activation_history_and_error_codes(tmp_path, capsys):
    source, run = evidence(tmp_path)
    prefix = ["--store-root", str(tmp_path)]
    assert main(prefix + ["status"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "NO_ACTIVE_SNAPSHOT"
    assert main(prefix + ["activate", "--source-id", source.source_id,
                          "--run-id", run.run_id, "--reason", "Manual review"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ACTIVATED"
    assert main(prefix + ["status"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ACTIVE"
    assert main(prefix + ["history"]) == 0
    assert json.loads(capsys.readouterr().out)["recent_history"] == []
    assert main(prefix + ["rollback", "--revision", "0" * 32,
                          "--reason", "no such revision"]) == 2
    assert "SELECTION_FAILED" in capsys.readouterr().err


def test_fail_closed_after_parser_version_changes(tmp_path, monkeypatch):
    source, run = evidence(tmp_path)
    from alma_duplicate.storage import queue_active as module
    monkeypatch.setattr(module, "QUEUE_CSV_PARSER_VERSION", "999")
    with pytest.raises(QueueActiveError, match="old code versions"):
        select(registry(tmp_path), source, run)
    assert registry(tmp_path).current() is None


def test_future_source_date_rejected(tmp_path):
    future = FIXTURE.read_bytes().replace(b"2026 March 3.", b"2027 March 3.", 1)
    source, run = evidence(tmp_path, future)
    with pytest.raises(QueueActiveError, match="in the future"):
        select(registry(tmp_path), source, run)


def test_pointer_does_not_change_pr1_check_log(tmp_path):
    source, run = evidence(tmp_path)
    log = tmp_path / "checks.jsonl"
    log.write_text('{"status":"NEW_VALIDATED"}\n')
    select(registry(tmp_path), source, run)
    assert log.read_text() == '{"status":"NEW_VALIDATED"}\n'
