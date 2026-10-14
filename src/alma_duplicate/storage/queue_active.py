"""Manually selected, atomic Queue snapshot pointer (PR2, no auto-activation).

The pointer is an operational choice, not historical Queue evidence. Published
source bytes and parser run manifests remain immutable in QueueSnapshotStore.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable
from urllib.parse import urlsplit
from uuid import uuid4

from alma_duplicate.parsers.queue_csv import QUEUE_CSV_PARSER_VERSION
from alma_duplicate.queue_csv_contract import QUEUE_SCHEMA_VERSION
from alma_duplicate.queue_normalization import (
    QUEUE_FREQUENCY_DERIVATION_VERSION,
    QUEUE_UNIT_NORMALIZATION_VERSION,
    QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION,
)
from alma_duplicate.storage.queue_snapshots import QueueSnapshotStore, QueueSnapshotStoreError

POINTER_VERSION = 1
MAX_POINTER_BYTES = 64 * 1024
MAX_RECENT_HISTORY = 64
_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ENTRY_FIELDS = frozenset({
    "format_version", "kind", "revision", "source_id", "run_id",
    "snapshot_sha256", "source_manifest_sha256", "source_as_of",
    "activated_at", "reason",
})
_POINTER_FIELDS = _ENTRY_FIELDS | {"recent_history"}


class QueueActiveError(ValueError):
    """Invalid selection, stale reference, corrupt pointer or policy conflict."""


class QueueActiveBusyError(QueueActiveError):
    """Another active-selection operation holds the registry lock."""


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise QueueActiveError(f"duplicate pointer JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise QueueActiveError(f"non-JSON numeric constant: {value}")


def _aware_iso(text):
    if not isinstance(text, str):
        raise QueueActiveError("activation timestamp must be text")
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise QueueActiveError("invalid activation timestamp") from exc
    if result.utcoffset() is None:
        raise QueueActiveError("activation timestamp must include UTC offset")
    return result


def _entry(value, *, historical=False):
    if not isinstance(value, dict) or set(value) != _ENTRY_FIELDS:
        raise QueueActiveError("invalid active snapshot pointer fields")
    if type(value["format_version"]) is not int or value["format_version"] != POINTER_VERSION:
        raise QueueActiveError("unsupported active pointer version")
    if value["kind"] != "queue_active_snapshot":
        raise QueueActiveError("invalid active pointer kind")
    for name in ("revision", "source_id", "run_id"):
        if not isinstance(value[name], str) or _ID.fullmatch(value[name]) is None:
            raise QueueActiveError(f"invalid pointer {name}")
    for name in ("snapshot_sha256", "source_manifest_sha256"):
        if not isinstance(value[name], str) or _SHA.fullmatch(value[name]) is None:
            raise QueueActiveError(f"invalid pointer {name}")
    try:
        date.fromisoformat(value["source_as_of"])
    except (TypeError, ValueError) as exc:
        raise QueueActiveError("invalid active source date") from exc
    _aware_iso(value["activated_at"])
    if not isinstance(value["reason"], str) or not 1 <= len(value["reason"].strip()) <= 500:
        raise QueueActiveError("activation reason must contain 1-500 characters")
    return value


def _validate_pointer(value):
    if not isinstance(value, dict) or set(value) != _POINTER_FIELDS:
        raise QueueActiveError("invalid current.json shape")
    _entry({k: value[k] for k in _ENTRY_FIELDS})
    history = value["recent_history"]
    if not isinstance(history, list) or len(history) > MAX_RECENT_HISTORY:
        raise QueueActiveError("invalid recent activation history")
    seen = {value["revision"]}
    for item in history:
        _entry(item, historical=True)
        if item["revision"] in seen:
            raise QueueActiveError("duplicate activation revision")
        seen.add(item["revision"])
    return value


def _safe_official_source(metadata):
    """Require PR1-style official download provenance, not arbitrary local fixtures."""
    if metadata["source_url_kind"] != "DOWNLOAD_URL" or not metadata["retrieved_at"]:
        raise QueueActiveError("source lacks official download provenance")
    try:
        parsed = urlsplit(metadata["source_url"])
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise QueueActiveError("invalid source download URL") from exc
    if (parsed.scheme != "https" or parsed.hostname != "almascience.eso.org"
            or port not in (None, 443) or parsed.username is not None
            or parsed.password is not None or parsed.fragment
            or not parsed.path.startswith("/documents-and-tools/")
            or not parsed.path.endswith("/duplication-check-csv")):
        raise QueueActiveError("source is not the expected official Queue CSV download")


@contextmanager
def _selection_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".queue-active.lock"
    if path.is_symlink():
        raise QueueActiveError("refusing symlinked active-selection lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise QueueActiveBusyError("another active-selection operation is running") from exc
        yield
    finally:
        os.close(fd)


class QueueActiveRegistry:
    """Safely select an already validated official source/run, explicitly only."""

    def __init__(self, root: str | Path, *, clock: Callable[[], datetime] | None = None):
        self.root = Path(root)
        self.store = QueueSnapshotStore(self.root)
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self):
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise QueueActiveError("clock must return timezone-aware datetime")
        return value

    def _read_pointer(self):
        path = self.root / "current.json"
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise QueueActiveError("cannot read active pointer safely") from exc
        try:
            with os.fdopen(fd, "rb") as handle:
                raw = handle.read(MAX_POINTER_BYTES + 1)
        except OSError as exc:
            raise QueueActiveError("cannot read active pointer") from exc
        if len(raw) > MAX_POINTER_BYTES:
            raise QueueActiveError("active pointer exceeds size limit")
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys,
                              parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QueueActiveError("invalid active pointer JSON") from exc
        return _validate_pointer(data)

    def _validated_pair(self, source_id: str, run_id: str):
        for name, value in (("source_id", source_id), ("run_id", run_id)):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise QueueActiveError(f"invalid {name}")
        try:
            source = self.store.read_source(source_id)
            run = self.store.read_run(run_id)
        except QueueSnapshotStoreError as exc:
            raise QueueActiveError("source or parse-run evidence is missing or corrupt") from exc
        metadata, summary = source.metadata, run.summary
        _safe_official_source(metadata)
        if (summary["source_id"] != source_id
                or summary["snapshot_sha256"] != metadata["snapshot_sha256"]
                or summary["source_manifest_sha256"] != source.manifest_sha256):
            raise QueueActiveError("parse-run provenance does not bind to the selected source")
        counts = summary["counts"]
        if (summary["status"] not in ("COMPLETE", "COMPLETE_WITH_WARNINGS")
                or counts["raw_rows"] <= 0
                or counts["raw_rows"] != counts["row_inputs"]
                or summary["source_as_of_status"] != "PARSED"
                or not summary["source_as_of"]):
            raise QueueActiveError("Queue parse-run did not pass PR1 validation gate")
        current_versions = {
            "units": QUEUE_UNIT_NORMALIZATION_VERSION,
            "frequency": QUEUE_FREQUENCY_DERIVATION_VERSION,
            "usable_bandwidth": QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION,
        }
        if (summary["parser_version"] != QUEUE_CSV_PARSER_VERSION
                or summary["schema_version"] != QUEUE_SCHEMA_VERSION
                or dict(summary["normalization_versions"]) != current_versions):
            raise QueueActiveError("parse-run uses old code versions; explicitly reparse before activation")
        return source, run

    def current(self):
        """Read and verify the active source/run without modifying either."""
        record = self._read_pointer()
        if record is None:
            return None
        source, run = self._validated_pair(record["source_id"], record["run_id"])
        if (record["snapshot_sha256"] != source.metadata["snapshot_sha256"]
                or record["source_manifest_sha256"] != source.manifest_sha256
                or record["source_as_of"] != run.summary["source_as_of"]):
            raise QueueActiveError("active pointer does not match source/parse-run evidence")
        return record

    def _atomic_publish(self, record):
        path = self.root / "current.json"
        if path.is_symlink():
            raise QueueActiveError("refusing symlinked active pointer")
        contents = (json.dumps(record, sort_keys=True, ensure_ascii=False,
                               allow_nan=False, indent=2) + "\n").encode("utf-8")
        if len(contents) > MAX_POINTER_BYTES:
            raise QueueActiveError("active pointer exceeds size limit")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".current-pending-",
                                             suffix=".json", dir=self.root, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _activate_locked(self, source_id, run_id, *, reason, rollback=False,
                         allow_same_date_change=False):
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
            raise QueueActiveError("activation reason must contain 1-500 characters")
        source, run = self._validated_pair(source_id, run_id)
        old = self.current()
        if old and old["source_id"] == source_id and old["run_id"] == run_id:
            return {"status": "ALREADY_ACTIVE", "active": old}
        candidate_date = date.fromisoformat(run.summary["source_as_of"])
        now = self._now()
        if candidate_date > now.date():
            raise QueueActiveError("official source date is in the future")
        if old is not None and not rollback:
            old_date = date.fromisoformat(old["source_as_of"])
            if candidate_date < old_date:
                raise QueueActiveError("older data requires explicit rollback to a prior revision")
            if (candidate_date == old_date
                    and source.metadata["snapshot_sha256"] != old["snapshot_sha256"]
                    and not allow_same_date_change):
                raise QueueActiveError("same-date changed bytes require --allow-same-date-change")
        history = list(old["recent_history"]) + [{k: old[k] for k in _ENTRY_FIELDS}] if old else []
        record = {
            "format_version": POINTER_VERSION,
            "kind": "queue_active_snapshot",
            "revision": uuid4().hex,
            "source_id": source_id,
            "run_id": run_id,
            "snapshot_sha256": source.metadata["snapshot_sha256"],
            "source_manifest_sha256": source.manifest_sha256,
            "source_as_of": run.summary["source_as_of"],
            "activated_at": now.isoformat(),
            "reason": reason.strip(),
            "recent_history": history[-MAX_RECENT_HISTORY:],
        }
        _validate_pointer(record)
        self._atomic_publish(record)
        return {"status": "ROLLED_BACK" if rollback else "ACTIVATED", "active": record}

    def activate(self, source_id: str, run_id: str, *, reason: str,
                 allow_same_date_change: bool = False):
        """Manually approve one validated pair. Never triggered by the downloader."""
        with _selection_lock(self.root):
            return self._activate_locked(source_id, run_id, reason=reason,
                                         allow_same_date_change=allow_same_date_change)

    def rollback(self, revision: str, *, reason: str):
        """Re-select a prior known-active revision; never restore stale file bytes."""
        if not isinstance(revision, str) or _ID.fullmatch(revision) is None:
            raise QueueActiveError("invalid rollback revision")
        with _selection_lock(self.root):
            old = self.current()
            if old is None:
                raise QueueActiveError("no active snapshot to roll back")
            previous = next((item for item in old["recent_history"]
                             if item["revision"] == revision), None)
            if previous is None:
                raise QueueActiveError("revision not in recent activation history")
            result = self._activate_locked(previous["source_id"], previous["run_id"],
                                           reason=reason, rollback=True)
            result["rolled_back_to"] = revision
            return result

    def history(self):
        """Return metadata-only recent selections; never reconstruct science."""
        current = self.current()
        if current is None:
            return ()
        return tuple(current["recent_history"])
