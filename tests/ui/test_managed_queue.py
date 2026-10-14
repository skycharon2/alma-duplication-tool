"""PR3 managed Queue browser tests: no live HTTP and no hidden activation."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_update import run_update
from alma_duplicate.clients.queue_downloader import DownloadedQueue
from alma_duplicate.storage.queue_active import QueueActiveRegistry
from alma_duplicate.ui import create_app
from alma_duplicate.ui import runs as execution
from alma_duplicate.ui.managed_queue import managed_queue_status, pin_active_queue
from tests.ui.test_runs import line_form

FIXTURE = Path(__file__).parents[1] / "fixtures" / "queue" / "queue_pipeline_v1.csv"
URL = "https://almascience.eso.org/documents-and-tools/cycle13/duplication-check-csv"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def acquired(root, raw=None):
    original = FIXTURE.read_bytes() if raw is None else raw
    result = run_update(root, downloader=lambda: DownloadedQueue(original, URL, NOW),
                        clock=lambda: NOW)
    assert result["status"] == "NEW_VALIDATED"
    return result


def app(root, **changes):
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None,
                       "OFFLINE_ARCHIVE_REPLAY": None, "OFFLINE_QUEUE_CSV": None,
                       "LIVE_ARCHIVE": False, "MANAGED_QUEUE_ROOT": str(root)} | changes)


def queue_form():
    data = line_form()
    data.setlist("sources", ["QUEUE"])
    return data


def test_no_pointer_is_visible_and_never_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "assess_observation",
                        lambda *a, **k: pytest.fail("validation page must not assess"))
    client = app(tmp_path).test_client()
    page = client.get("/proposed")
    assert page.status_code == 200
    assert b"Queue snapshot not activated" in page.data
    assert not (tmp_path / "sources").exists()
    assert not (tmp_path / "current.json").exists()


def test_managed_queue_report_pins_ids_and_raw_evidence(tmp_path):
    first = acquired(tmp_path)
    active = QueueActiveRegistry(tmp_path, clock=lambda: NOW).activate(
        first["source_id"], first["run_id"], reason="Reviewed Queue")['active']
    client = app(tmp_path).test_client()
    page = client.get("/proposed")
    assert page.status_code == 200
    assert b"Queue data as of: 2026-03-03" in page.data
    assert b"Last successful check:" in page.data
    response = client.post("/proposed", data=queue_form())
    assert response.status_code == 303
    report = client.get(response.location + "/download/report").get_json()
    meta = report["sources"]["QUEUE"]["managed_snapshot"]
    assert meta["source_id"] == first["source_id"]
    assert meta["run_id"] == first["run_id"]
    assert meta["revision"] == active["revision"]
    assert meta["snapshot_sha256"] == first["snapshot_sha256"]
    assert meta["source_as_of"] == "2026-03-03"
    assert first["source_id"] in client.get(response.location).get_data(as_text=True)


def test_changed_active_pointer_during_assessment_is_pinned(tmp_path, monkeypatch):
    first = acquired(tmp_path)
    registry = QueueActiveRegistry(tmp_path, clock=lambda: NOW)
    registry.activate(first["source_id"], first["run_id"], reason="First")
    later = acquired(tmp_path, FIXTURE.read_bytes().replace(b"2026 March 3.",
                                                          b"2026 March 10.", 1))
    original = execution.assess_observation

    def change_during_run(*args, **kwargs):
        registry.activate(later["source_id"], later["run_id"], reason="Second")
        return original(*args, **kwargs)

    monkeypatch.setattr(execution, "assess_observation", change_during_run)
    client = app(tmp_path).test_client()
    response = client.post("/proposed", data=queue_form())
    assert response.status_code == 303
    report = client.get(response.location + "/download/report").get_json()
    meta = report["sources"]["QUEUE"]["managed_snapshot"]
    assert meta["source_id"] == first["source_id"]
    assert meta["source_as_of"] == "2026-03-03"
    assert registry.current()["source_id"] == later["source_id"]


def test_invalid_pointer_does_not_claim_data_ready(tmp_path):
    first = acquired(tmp_path)
    registry = QueueActiveRegistry(tmp_path, clock=lambda: NOW)
    registry.activate(first["source_id"], first["run_id"], reason="First")
    (tmp_path / "current.json").write_text("{broken", encoding="utf-8")
    assert managed_queue_status(tmp_path)["status"] == "INVALID"
    client = app(tmp_path).test_client()
    assert b"Queue snapshot unavailable" in client.get("/proposed").data
    response = client.post("/proposed", data=queue_form())
    assert response.status_code == 303
    report = client.get(response.location + "/download/report").get_json()
    assert report["sources"]["QUEUE"]["status"] == "FAILED"
    assert "managed_snapshot" not in report["sources"]["QUEUE"]


def test_read_only_status_and_failed_check_use_existing_active(tmp_path):
    first = acquired(tmp_path)
    QueueActiveRegistry(tmp_path, clock=lambda: NOW).activate(
        first["source_id"], first["run_id"], reason="First")
    (tmp_path / "checks.jsonl").open("a", encoding="utf-8").write(
        json.dumps({"status": "DOWNLOAD_FAILED", "checked_at": "2026-10-15T08:00:00+00:00",
                    "error": "network offline"}) + "\n")
    status = managed_queue_status(tmp_path)
    assert status["status"] == "ACTIVE"
    assert status["check_status"] == "DOWNLOAD_FAILED"
    assert status["last_successful_check_at"] == first["checked_at"]
    assert "offline" in status["check_error"]
    assert pin_active_queue(tmp_path).provenance["source_id"] == first["source_id"]


def test_managed_and_manual_config_conflict(tmp_path):
    with pytest.raises(ValueError, match="mutually exclusive"):
        app(tmp_path, OFFLINE_QUEUE_CSV="/unused.csv")


def test_no_managed_mode_leaves_legacy_ui_unchanged(tmp_path):
    client = app(tmp_path, MANAGED_QUEUE_ROOT=None).test_client()
    assert b"queue-source-status" not in client.get("/proposed").data
