"""PR3 regression: identical bytes without PR2-approved provenance must be reacquired."""

from datetime import UTC, datetime
from pathlib import Path

from alma_duplicate.cli.queue_update import run_update
from alma_duplicate.clients.queue_downloader import DownloadedQueue
from alma_duplicate.storage import QueueSnapshotStore
from alma_duplicate.storage.queue_active import QueueActiveRegistry

FIXTURE = Path(__file__).parents[1] / "fixtures" / "queue" / "queue_pipeline_v1.csv"
URL = "https://almascience.eso.org/documents-and-tools/cycle13/duplication-check-csv"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def test_equal_bytes_missing_provenance_are_reacquired(tmp_path):
    store = QueueSnapshotStore(tmp_path)
    raw = FIXTURE.read_bytes()
    old = store.save_source(raw)  # SOURCE_PAGE, retrieved_at=None
    old_run, _ = store.reparse(old.source_id)

    downloaded = run_update(tmp_path, downloader=lambda: DownloadedQueue(raw, URL, NOW),
                            clock=lambda: NOW)
    assert downloaded["status"] == "NEW_VALIDATED"
    assert downloaded["source_id"] != old.source_id
    assert downloaded["run_id"] != old_run.run_id
    assert store.read_source(old.source_id).metadata["retrieved_at"] is None
    new = store.read_source(downloaded["source_id"])
    assert new.metadata["source_url_kind"] == "DOWNLOAD_URL"
    assert new.metadata["retrieved_at"] == NOW.isoformat()
    assert store.read_source(old.source_id).raw_bytes == new.raw_bytes == raw
    assert QueueActiveRegistry(tmp_path, clock=lambda: NOW).activate(
        downloaded["source_id"], downloaded["run_id"], reason="Reviewed")['status'] == "ACTIVATED"

    repeated = run_update(tmp_path, downloader=lambda: DownloadedQueue(raw, URL, NOW),
                          clock=lambda: NOW)
    assert repeated["status"] == "UNCHANGED"
    assert repeated["source_id"] == downloaded["source_id"]
    assert len(store.list_sources()) == 2
    assert len(store.list_runs()) == 2
