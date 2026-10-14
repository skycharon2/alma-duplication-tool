"""One-shot Queue source acquisition: python -m alma_duplicate.cli.queue_update --once.

PR1 records acquisitions and verification only. It never changes which Queue
snapshot the Flask UI selects and never creates an active-snapshot pointer.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Callable

from alma_duplicate.clients.queue_downloader import (
    DownloadedQueue, QueueDownloadError, download_queue_csv,
)
from alma_duplicate.storage import QueueSnapshotStore, QueueSnapshotStoreError
from alma_duplicate.storage.queue_active import QueueActiveError, _safe_official_source

GOOD_STATUSES = {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
SUCCESS_STATUSES = {"NEW_VALIDATED", "UNCHANGED"}


class QueueUpdateBusyError(RuntimeError):
    """Another updater owns this storage root's update lock."""


@contextmanager
def _exclusive_update_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock_file = root / ".queue-update.lock"
    if lock_file.is_symlink():
        raise OSError("refusing a symlinked Queue update lock")
    fd = os.open(lock_file, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise QueueUpdateBusyError("another Queue update is in progress") from exc
        yield
    finally:
        os.close(fd)


def _record_check(root: Path, record: dict) -> None:
    """Append one fsynced operational event; never overwrite source evidence."""
    path = root / "checks.jsonl"
    if path.is_symlink():
        raise OSError("refusing a symlinked Queue check log")
    encoded = (json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False)
               + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if os.write(fd, encoded) != len(encoded):
            raise OSError("incomplete Queue check log write")
        os.fsync(fd)
    finally:
        os.close(fd)


def _valid_summary(summary) -> bool:
    counts = summary["counts"]
    return (
        summary["status"] in GOOD_STATUSES
        and counts["raw_rows"] > 0
        and counts["raw_rows"] == counts["row_inputs"]
        and summary["source_as_of_status"] == "PARSED"
        and bool(summary["source_as_of"])
    )


def _outcome(*, status: str, checked_at: str, **details) -> dict:
    return {"status": status, "checked_at": checked_at,
            "activated": False, **details}


def run_update(
    store_root: str | Path,
    *,
    downloader: Callable[[], DownloadedQueue] = download_queue_csv,
    clock: Callable[[], datetime] | None = None,
) -> dict:
    """Download, deduplicate and parse an official Queue CSV without activation.

    The snapshot store remains append-only. Matching old bytes with no historical
    parse are reparsed *under the original source ID*, not saved a second time.
    """
    root = Path(store_root)
    instant = (clock or (lambda: datetime.now(UTC)))()
    if not isinstance(instant, datetime) or instant.utcoffset() is None:
        raise ValueError("check clock must return timezone-aware datetime")
    checked_at = instant.isoformat()
    with _exclusive_update_lock(root):
        details: dict = {}
        try:
            download = downloader()
            if not isinstance(download, DownloadedQueue):
                raise TypeError("downloader must return DownloadedQueue")
            checksum = sha256(download.raw_bytes).hexdigest()
            details.update({
                "snapshot_sha256": checksum,
                "retrieved_at": download.retrieved_at.isoformat(),
                "download_url": download.final_url,
                "http_etag": download.etag,
                "http_last_modified": download.last_modified,
            })
            store = QueueSnapshotStore(root)
            same_sources = []
            for source_id in store.list_sources():
                saved = store.read_source(source_id)
                if saved.metadata["snapshot_sha256"] != checksum:
                    continue
                # Identical bytes are not equivalent acquisitions if older
                # metadata lacks the official retrieval proof required by PR2.
                # Preserve the legacy evidence, but reacquire under a new ID.
                try:
                    _safe_official_source(saved.metadata)
                except QueueActiveError:
                    continue
                same_sources.append(saved)
            same_ids = {item.source_id for item in same_sources}
            matched_runs = []
            if same_ids:
                for run_id in store.list_runs():
                    previous = store.read_run(run_id).summary
                    if previous["source_id"] in same_ids:
                        matched_runs.append(previous)
            accepted = next((record for record in matched_runs if _valid_summary(record)), None)
            if accepted is not None:
                details.update({"source_id": accepted["source_id"],
                                "run_id": accepted["run_id"],
                                "source_as_of": accepted["source_as_of"]})
                status = "UNCHANGED"
            elif same_sources and matched_runs:
                # Identical bytes already failed our adoption gate. Do not call it unchanged.
                details.update({"source_id": same_sources[0].source_id,
                                "run_id": matched_runs[0]["run_id"],
                                "source_as_of": matched_runs[0]["source_as_of"],
                                "error": "identical bytes were previously rejected"})
                status = "KNOWN_INVALID"
            else:
                if same_sources:
                    source = same_sources[0]
                else:
                    source = store.save_source(
                        download.raw_bytes, source_url=download.final_url,
                        source_url_kind="DOWNLOAD_URL",
                        retrieved_at=download.retrieved_at,
                        source_note="Automatic official Queue acquisition (PR1; not activated)",
                    )
                details["source_id"] = source.source_id
                try:
                    run, parsed = store.reparse(source.source_id)
                except Exception as exc:
                    status = "PARSE_FAILED"
                    details["error"] = f"Queue parser raised {type(exc).__name__}: {exc}"
                    record = _outcome(status=status, checked_at=checked_at, **details)
                    _record_check(root, record)
                    return record
                details.update({"run_id": run.run_id,
                                "source_as_of": run.summary["source_as_of"],
                                "parse_status": run.summary["status"],
                                "raw_rows": run.summary["counts"]["raw_rows"]})
                if (parsed.can_reconstruct and len(parsed.raw_rows) > 0
                        and parsed.snapshot.source_as_of_status == "PARSED"):
                    status = "NEW_VALIDATED"
                else:
                    status = "VALIDATION_FAILED"
                    details["error"] = "CSV did not meet reconstruction/source-date adoption gate"
        except (QueueDownloadError, QueueSnapshotStoreError, OSError,
                ValueError, TypeError) as exc:
            status = ("DOWNLOAD_FAILED" if isinstance(exc, QueueDownloadError)
                      else "STORAGE_FAILED")
            details["error"] = str(exc)
        record = _outcome(status=status, checked_at=checked_at, **details)
        _record_check(root, record)
        return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check/store official ALMA Queue CSV; no active swap")
    parser.add_argument("--once", action="store_true", required=True,
                        help="perform a single bounded check; no scheduler is started")
    parser.add_argument("--store-root", type=Path,
                        default=Path("data/cache/queue-snapshots"))
    args = parser.parse_args(argv)
    try:
        result = run_update(args.store_root)
    except (QueueUpdateBusyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "UPDATE_UNAVAILABLE", "error": str(exc)}),
              file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] in SUCCESS_STATUSES else 2


if __name__ == "__main__":
    raise SystemExit(main())
