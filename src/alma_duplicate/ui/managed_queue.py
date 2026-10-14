"""Read-only browser adapter for manually approved Queue snapshots (PR3).

Requests never trigger downloads, reparses of historical run records, or
activation. Each assessment pins exact verified source bytes at its beginning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.storage.queue_active import QueueActiveError, QueueActiveRegistry
from alma_duplicate.storage.queue_snapshots import QueueSnapshotStoreError

MAX_CHECK_LOG_TAIL = 256 * 1024
SUCCESS_CHECK_STATUSES = frozenset({"NEW_VALIDATED", "UNCHANGED"})


@dataclass(frozen=True)
class PinnedQueue:
    """A single run's verified source bytes and immutable provenance."""

    raw_bytes: bytes
    source_url: str
    source_url_kind: str
    retrieved_at: datetime
    provenance: dict

    def parse(self):
        """Parse only these bytes, regardless of later current.json changes."""
        result = QueueCsvClient(self.source_url, source_url_kind=self.source_url_kind).parse_bytes(
            self.raw_bytes, retrieved_at=self.retrieved_at,
        )
        if (result.snapshot.snapshot_sha256 != self.provenance["snapshot_sha256"]
                or not result.can_reconstruct
                or result.snapshot.source_as_of is None
                or result.snapshot.source_as_of.isoformat() != self.provenance["source_as_of"]):
            raise QueueActiveError("pinned Queue bytes failed current parser/source-date gate")
        return result


def pin_active_queue(root: str | Path) -> PinnedQueue:
    """Choose once, reverify bytes, and retain them in memory for this assessment."""
    registry = QueueActiveRegistry(root)
    active = registry.current()  # Validates pointer and bound source/parse-run.
    if active is None:
        raise QueueActiveError("no approved Queue snapshot is active")
    try:
        source = registry.store.read_source(active["source_id"])
    except QueueSnapshotStoreError as exc:
        raise QueueActiveError("active Queue source was removed or became corrupt") from exc
    if (source.metadata["snapshot_sha256"] != active["snapshot_sha256"]
            or source.manifest_sha256 != active["source_manifest_sha256"]
            or sha256(source.raw_bytes).hexdigest() != active["snapshot_sha256"]):
        raise QueueActiveError("active Queue source changed while being selected")
    retrieved = source.metadata["retrieved_at"]
    if retrieved is None:
        raise QueueActiveError("active Queue source has no retrieval timestamp")
    provenance = {
        "source_id": active["source_id"],
        "run_id": active["run_id"],
        "revision": active["revision"],
        "snapshot_sha256": active["snapshot_sha256"],
        "source_manifest_sha256": active["source_manifest_sha256"],
        "source_as_of": active["source_as_of"],
        "retrieved_at": retrieved,
        "source_url": source.metadata["source_url"],
        "activated_at": active["activated_at"],
    }
    return PinnedQueue(
        raw_bytes=source.raw_bytes,
        source_url=source.metadata["source_url"],
        source_url_kind=source.metadata["source_url_kind"],
        retrieved_at=datetime.fromisoformat(retrieved),
        provenance=provenance,
    )


def _last_checks(root: Path):
    """Read a bounded tail of the append-only operational log, never the full file."""
    path = root / "checks.jsonl"
    if path.is_symlink():
        raise ValueError("symlinked Queue check log")
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            end = stream.tell()
            stream.seek(max(0, end - MAX_CHECK_LOG_TAIL))
            raw = stream.read(MAX_CHECK_LOG_TAIL)
    except FileNotFoundError:
        return None, None
    if end > MAX_CHECK_LOG_TAIL:
        raw = raw.partition(b"\n")[2]  # Ignore the first possibly partial record.
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        return None, None
    # Never guess whether malformed JSON was a successful or failed check.
    records = []
    for line in lines:
        item = json.loads(line)
        if not isinstance(item, dict) or not isinstance(item.get("status"), str):
            raise ValueError("invalid Queue check record")
        records.append(item)
    latest = records[-1]
    successful = next((item for item in reversed(records)
                       if item["status"] in SUCCESS_CHECK_STATUSES), None)
    return latest, successful


def managed_queue_status(root: str | Path) -> dict:
    """Metadata-only status, including last check failure; never trigger network."""
    location = Path(root)
    result = {
        "mode": "MANAGED", "status": "NOT_ACTIVATED", "source_as_of": None,
        "source_id": None, "run_id": None, "revision": None,
        "snapshot_sha256": None, "checked_at": None,
        "check_status": "NOT_CHECKED", "last_successful_check_at": None,
        "check_error": None, "update_waiting_for_approval": False,
    }
    try:
        active = QueueActiveRegistry(location).current()
    except (QueueActiveError, OSError, ValueError) as exc:
        result.update(status="INVALID", error=str(exc))
        active = None
    if active is not None:
        result.update(status="ACTIVE", source_as_of=active["source_as_of"],
                      source_id=active["source_id"], run_id=active["run_id"],
                      revision=active["revision"], snapshot_sha256=active["snapshot_sha256"])
    try:
        latest, successful = _last_checks(location)
        if latest:
            result.update(checked_at=latest.get("checked_at"),
                          check_status=latest["status"],
                          check_error=latest.get("error"))
            if (active is not None and latest["status"] == "NEW_VALIDATED"
                    and latest.get("snapshot_sha256") != active["snapshot_sha256"]):
                result["update_waiting_for_approval"] = True
        if successful:
            result["last_successful_check_at"] = successful.get("checked_at")
    except (OSError, ValueError, UnicodeError) as exc:
        result.update(check_status="CHECK_LOG_INVALID", check_error=str(exc))
    return result
