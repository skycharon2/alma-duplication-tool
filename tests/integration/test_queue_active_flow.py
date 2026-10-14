"""Offline PR1->PR2 integration: acquisition alone never activates a snapshot."""

from datetime import UTC, datetime
from pathlib import Path

from alma_duplicate.cli.queue_update import run_update
from alma_duplicate.clients.queue_downloader import DownloadedQueue
from alma_duplicate.storage.queue_active import QueueActiveRegistry

FIXTURE = Path(__file__).parents[1] / "fixtures" / "queue" / "queue_pipeline_v1.csv"
URL = "https://almascience.eso.org/documents-and-tools/cycle13/duplication-check-csv"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def _download(raw):
    return lambda: DownloadedQueue(raw, URL, NOW)


def test_explicit_activation_after_pr1_and_frozen_prior_selection(tmp_path):
    registry = QueueActiveRegistry(tmp_path, clock=lambda: NOW)
    first = run_update(tmp_path, downloader=_download(FIXTURE.read_bytes()), clock=lambda: NOW)
    assert first["status"] == "NEW_VALIDATED"
    assert first["activated"] is False
    assert registry.current() is None

    chosen = registry.activate(first["source_id"], first["run_id"],
                               reason="Approved first official snapshot")["active"]
    unchanged = run_update(tmp_path, downloader=_download(FIXTURE.read_bytes()), clock=lambda: NOW)
    assert unchanged["status"] == "UNCHANGED"
    assert registry.current() == chosen

    newer_bytes = FIXTURE.read_bytes().replace(b"2026 March 3.", b"2026 March 10.", 1)
    newer = run_update(tmp_path, downloader=_download(newer_bytes), clock=lambda: NOW)
    assert newer["status"] == "NEW_VALIDATED"
    assert registry.current() == chosen  # PR1 did not activate anything

    active = registry.activate(newer["source_id"], newer["run_id"],
                               reason="Reviewed and approved more recent Queue export")["active"]
    assert active["source_as_of"] == "2026-03-10"
    assert chosen["revision"] in {entry["revision"] for entry in registry.history()}
    restored = registry.rollback(chosen["revision"], reason="Review discovered a data issue")
    assert restored["active"]["source_id"] == first["source_id"]
    assert restored["status"] == "ROLLED_BACK"


def test_rejected_pr1_download_cannot_displace_active_pointer(tmp_path):
    registry = QueueActiveRegistry(tmp_path, clock=lambda: NOW)
    first = run_update(tmp_path, downloader=_download(FIXTURE.read_bytes()), clock=lambda: NOW)
    active = registry.activate(first["source_id"], first["run_id"],
                               reason="Approved initial official source")["active"]
    failed = run_update(tmp_path, downloader=_download(b"<html>not a Queue CSV</html>"),
                        clock=lambda: NOW)
    assert failed["status"] in {"VALIDATION_FAILED", "KNOWN_INVALID"}
    assert registry.current() == active
