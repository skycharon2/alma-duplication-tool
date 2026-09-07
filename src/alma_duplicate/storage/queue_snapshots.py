"""Append-only Queue source acquisitions and historical parse summaries.

Published directories are the commit boundary. No complete Python parse result
is serialized; historical summary reads never run a parser.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from types import MappingProxyType
from uuid import uuid4

from alma_duplicate.domain.queue import QueueCsvParseResult
from alma_duplicate.parsers.queue_csv import DEFAULT_QUEUE_SOURCE_URL, parse_queue_csv_bytes
from alma_duplicate.queue_normalization import (
    QUEUE_FREQUENCY_DERIVATION_VERSION, QUEUE_UNIT_NORMALIZATION_VERSION,
    QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION,
)

FORMAT_VERSION = 1
_SOURCE_FIELDS = {
    "format_version", "kind", "source_id", "snapshot_sha256", "byte_length",
    "source_url", "source_url_kind", "retrieved_at", "saved_at", "source_note",
    "legacy_captured_at",
}
_RUN_FIELDS = {
    "format_version", "kind", "run_id", "source_id", "snapshot_sha256",
    "source_manifest_sha256", "parsed_at", "parser_version", "schema_version",
    "provenance_version", "normalization_versions", "status", "counts",
    "source_as_of", "source_as_of_raw", "source_as_of_status", "diagnostics",
}


class QueueSnapshotStoreError(ValueError):
    """Missing, corrupt, unsupported, or unsuccessfully published evidence."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise QueueSnapshotStoreError(message)


def _identifier(value: object) -> str:
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None,
             "invalid record ID; only published UUID-hex IDs are accepted")
    return value


def _hash(value: object) -> None:
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "invalid SHA-256")


def _time(value: object, *, nullable=False, legacy=False) -> datetime | None:
    if nullable and value is None:
        return None
    _require(isinstance(value, str), "timestamp must be an ISO string")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise QueueSnapshotStoreError("invalid timestamp") from exc
    _require(legacy or result.utcoffset() is not None, "timestamp requires timezone")
    return result


def _iso(value: datetime | None) -> str | None:
    _require(value is None or isinstance(value, datetime), "expected datetime or None")
    return value.isoformat() if value is not None else None


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate manifest key: {key}")
        result[key] = value
    return result


def _bad_constant(value):
    raise QueueSnapshotStoreError(f"non-JSON numeric constant: {value}")


def _read_manifest(path: Path, fields: set[str], kind: str):
    _require(not path.is_symlink(), "manifest symlinks are not supported")
    try:
        raw = path.read_bytes()
        obj = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    except (OSError, ValueError) as exc:
        raise QueueSnapshotStoreError(f"cannot read valid manifest: {path}") from exc
    _require(isinstance(obj, dict) and set(obj) == fields, "manifest fields do not match format")
    _require(type(obj["format_version"]) is int and obj["format_version"] == FORMAT_VERSION,
             "unsupported manifest version")
    _require(obj["kind"] == kind, "incorrect manifest kind")
    return obj, sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredQueueSource:
    source_id: str
    raw_bytes: bytes
    metadata: Mapping[str, object]
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class StoredQueueRun:
    run_id: str
    summary: Mapping[str, object]


class QueueSnapshotStore:
    """Explicit caller-selected directory; never download or rewrite records."""

    def __init__(self, root: str | Path, *, clock: Callable[[], datetime] | None = None):
        self.root = Path(root)
        self._clock = clock or (lambda: datetime.now(UTC))

    def _record_path(self, category: str, identifier: str) -> Path:
        path = self.root / category / _identifier(identifier)
        _require(not path.is_symlink() and path.is_dir(), "published record directory missing")
        return path

    @staticmethod
    def _sync_directory(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _publish(self, category, identifier, manifest, raw_bytes, validate):
        parent = self.root / category
        parent.mkdir(parents=True, exist_ok=True)
        destination = parent / _identifier(identifier)
        _require(not destination.exists(), "record already exists; overwrite forbidden")
        temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
        try:
            files = {"manifest.json": json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
            ).encode("utf-8") + b"\n"}
            if raw_bytes is not None:
                files["source.csv"] = raw_bytes
            for name, contents in files.items():
                with (temporary / name).open("xb") as stream:
                    stream.write(contents)
                    stream.flush()
                    os.fsync(stream.fileno())
            validate(temporary)
            self._sync_directory(temporary)
            _require(not destination.exists(), "record already exists; overwrite forbidden")
            os.rename(temporary, destination)
            self._sync_directory(parent)
        except (OSError, ValueError, TypeError) as exc:
            raise QueueSnapshotStoreError(f"could not publish {category} record") from exc
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def save_source(
        self, raw_bytes: bytes, *, source_url: str = DEFAULT_QUEUE_SOURCE_URL,
        source_url_kind: str | None = None, retrieved_at: datetime | None = None,
        source_note: str | None = None, legacy_captured_at: datetime | None = None,
    ) -> StoredQueueSource:
        """Publish exact bytes first, including unparseable CSV; no parser call."""
        _require(type(raw_bytes) is bytes, "source must be exact bytes")
        identifier = uuid4().hex
        manifest = {
            "format_version": FORMAT_VERSION, "kind": "queue_source",
            "source_id": identifier, "snapshot_sha256": sha256(raw_bytes).hexdigest(),
            "byte_length": len(raw_bytes), "source_url": source_url,
            "source_url_kind": (source_url_kind if source_url_kind is not None else
                                "SOURCE_PAGE" if source_url == DEFAULT_QUEUE_SOURCE_URL else
                                "UNSPECIFIED"),
            "retrieved_at": _iso(retrieved_at), "saved_at": _iso(self._clock()),
            "source_note": source_note, "legacy_captured_at": _iso(legacy_captured_at),
        }
        self._publish("sources", identifier, manifest, raw_bytes,
                      lambda path: self._read_source(path, identifier))
        return self.read_source(identifier)

    def _read_source(self, path: Path, identifier: str) -> StoredQueueSource:
        obj, manifest_hash = _read_manifest(path / "manifest.json", _SOURCE_FIELDS, "queue_source")
        _require(obj["source_id"] == identifier, "source ID mismatch")
        _hash(obj["snapshot_sha256"])
        _require(type(obj["byte_length"]) is int and obj["byte_length"] >= 0, "invalid byte length")
        _require(isinstance(obj["source_url"], str) and bool(obj["source_url"].strip()), "invalid source URL")
        _require(obj["source_url_kind"] in ("SOURCE_PAGE", "DOWNLOAD_URL", "UNSPECIFIED"), "invalid URL kind")
        _require(obj["source_note"] is None or isinstance(obj["source_note"], str), "invalid source note")
        _time(obj["retrieved_at"], nullable=True)
        _time(obj["saved_at"])
        _time(obj["legacy_captured_at"], nullable=True, legacy=True)
        csv_path = path / "source.csv"
        _require(not csv_path.is_symlink(), "CSV symlinks are not supported")
        try:
            raw = csv_path.read_bytes()
        except OSError as exc:
            raise QueueSnapshotStoreError("source.csv missing or unreadable") from exc
        _require(len(raw) == obj["byte_length"], "source byte length mismatch")
        _require(sha256(raw).hexdigest() == obj["snapshot_sha256"], "source checksum mismatch")
        return StoredQueueSource(identifier, raw, _freeze(obj), manifest_hash)

    def read_source(self, source_id: str) -> StoredQueueSource:
        """Validate saved source facts without parsing or changing any time."""
        return self._read_source(self._record_path("sources", source_id), source_id)

    def reparse(self, source_id: str) -> tuple[StoredQueueRun, QueueCsvParseResult]:
        """Use the current parser and publish a new historical summary."""
        source = self.read_source(source_id)
        metadata = source.metadata
        result = parse_queue_csv_bytes(
            source.raw_bytes, source_url=metadata["source_url"],
            source_url_kind=metadata["source_url_kind"],
            retrieved_at=_time(metadata["retrieved_at"], nullable=True),
            captured_at=_time(metadata["legacy_captured_at"], nullable=True, legacy=True),
            parsed_at=self._clock(),
        )
        identifier = uuid4().hex
        snapshot = result.snapshot
        summary = {
            "format_version": FORMAT_VERSION, "kind": "queue_parse_summary",
            "run_id": identifier, "source_id": source_id,
            "snapshot_sha256": metadata["snapshot_sha256"],
            "source_manifest_sha256": source.manifest_sha256,
            "parsed_at": _iso(snapshot.parsed_at), "parser_version": snapshot.parser_version,
            "schema_version": snapshot.schema_version, "provenance_version": snapshot.provenance_version,
            "normalization_versions": {
                "units": QUEUE_UNIT_NORMALIZATION_VERSION,
                "frequency": QUEUE_FREQUENCY_DERIVATION_VERSION,
                "usable_bandwidth": QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION,
            },
            "status": result.status.value,
            "counts": {"raw_rows": len(result.raw_rows), "row_inputs": len(result.row_inputs),
                       "field_metadata": len(result.field_metadata), "issues": len(result.issues)},
            "source_as_of": snapshot.source_as_of.isoformat() if snapshot.source_as_of else None,
            "source_as_of_raw": snapshot.source_as_of_raw,
            "source_as_of_status": snapshot.source_as_of_status,
            "diagnostics": [{"kind": issue.kind.value, "severity": issue.severity.value,
                             "message": issue.message, "column": issue.column,
                             "row_id": issue.row_id.value if issue.row_id else None}
                            for issue in result.issues],
        }
        self._publish("runs", identifier, summary, None,
                      lambda path: self._read_run(path, identifier))
        return self.read_run(identifier), result

    def _read_run(self, path: Path, identifier: str) -> StoredQueueRun:
        obj, _ = _read_manifest(path / "manifest.json", _RUN_FIELDS, "queue_parse_summary")
        _require(obj["run_id"] == identifier, "run ID mismatch")
        source = self.read_source(_identifier(obj["source_id"]))
        _require(obj["snapshot_sha256"] == source.metadata["snapshot_sha256"], "run source hash mismatch")
        _require(obj["source_manifest_sha256"] == source.manifest_sha256, "run source provenance mismatch")
        _time(obj["parsed_at"])
        for name in ("parser_version", "schema_version", "provenance_version"):
            _require(isinstance(obj[name], str) and bool(obj[name]), f"invalid {name}")
        versions = obj["normalization_versions"]
        _require(isinstance(versions, dict) and set(versions) == {"units", "frequency", "usable_bandwidth"},
                 "invalid normalization versions")
        _require(all(isinstance(v, str) and bool(v) for v in versions.values()), "invalid version value")
        _require(obj["status"] in ("COMPLETE", "COMPLETE_WITH_WARNINGS", "ERROR"), "invalid parse status")
        counts = obj["counts"]
        _require(isinstance(counts, dict) and set(counts) == {"raw_rows", "row_inputs", "field_metadata", "issues"},
                 "invalid counts")
        _require(all(type(v) is int and v >= 0 for v in counts.values()), "invalid count value")
        _require(counts["row_inputs"] <= counts["raw_rows"], "inconsistent row counts")
        diagnostics = obj["diagnostics"]
        _require(isinstance(diagnostics, list) and len(diagnostics) == counts["issues"], "invalid diagnostics count")
        for diagnostic in diagnostics:
            _require(isinstance(diagnostic, dict) and set(diagnostic) == {"kind", "severity", "message", "column", "row_id"},
                     "invalid diagnostic")
            _require(all(isinstance(diagnostic[key], str) for key in ("kind", "severity", "message")), "invalid diagnostic text")
            _require(diagnostic["severity"] in ("INFO", "WARNING", "ERROR"), "invalid severity")
            _require(all(diagnostic[key] is None or isinstance(diagnostic[key], str) for key in ("column", "row_id")),
                     "invalid diagnostic location")
        _require(obj["source_as_of_status"] in ("PARSED", "MISSING", "INVALID", "UNRECOGNIZED", "AMBIGUOUS"),
                 "invalid source date status")
        _require(obj["source_as_of_raw"] is None or isinstance(obj["source_as_of_raw"], str), "invalid date declaration")
        if obj["source_as_of_status"] == "PARSED":
            try:
                date.fromisoformat(obj["source_as_of"])
            except (TypeError, ValueError) as exc:
                raise QueueSnapshotStoreError("invalid source date") from exc
        else:
            _require(obj["source_as_of"] is None, "unexpected source date")
        return StoredQueueRun(identifier, _freeze(obj))

    def read_run(self, run_id: str) -> StoredQueueRun:
        """Return validated historical summary only; never rerun the parser."""
        return self._read_run(self._record_path("runs", run_id), run_id)

    def list_sources(self) -> tuple[str, ...]:
        return self._list("sources", self.read_source)

    def list_runs(self) -> tuple[str, ...]:
        return self._list("runs", self.read_run)

    def _list(self, category, reader):
        parent = self.root / category
        if not parent.exists():
            return ()
        identifiers = sorted(path.name for path in parent.iterdir()
                             if re.fullmatch(r"[0-9a-f]{32}", path.name))
        for identifier in identifiers:
            reader(identifier)
        return tuple(identifiers)
