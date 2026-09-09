# Queue source snapshots and parse summaries

`alma_duplicate.storage.QueueSnapshotStore` implements format version 1.
It accepts caller-supplied bytes and does not download files. Existing Queue
parser/client contracts and strict reconstruction gates are unchanged.

## Records and operations

| Operation | Saved or returned evidence |
| --- | --- |
| `save_source(bytes, ...)` | New acquisition ID, exact `source.csv`, source `manifest.json`; no parsing |
| `read_source(source_id)` | Validated bytes and acquisition facts; no clock or parser call |
| `reparse(source_id)` | New run ID and historical summary, plus the current full parse result in memory |
| `read_run(run_id)` | Validated saved summary; no current-parser replay |
| `list_sources()` / `list_runs()` | Sorted IDs, each validated; pending directories ignored; corrupt published records raise |

The caller selects a root, for example the already git-ignored
`data/cache/queue-snapshots`. Published sources live in
`sources/<source_id>/source.csv` and `sources/<source_id>/manifest.json`.
Published run summaries live in `runs/<run_id>/manifest.json`.
IDs are UUID hex strings, not chronological keys.

The source manifest contains `format_version`, `kind`, `source_id`,
`snapshot_sha256`, `byte_length`, `source_url`, `source_url_kind`, `retrieved_at`,
`saved_at`, `source_note`, and `legacy_captured_at`.
`saved_at` is the local storage time, never an inferred download time.
Unknown retrieval time remains null. No time is inferred from file names or
mtime. The default URL is the existing Queue source page; a custom URL defaults
to `UNSPECIFIED` unless the caller supplies its kind. `source_note` preserves a
caller-supplied provenance description. Original CSV declarations remain in the
exact bytes, including when they cannot be decoded.

Each acquisition is stored independently, even for identical bytes. This
preserves separate retrieval times and origins. There is no overwrite API or
checksum-only deduplication. Legacy capture timestamps are retained separately,
including naive values, and are never reinterpreted as retrieval timestamps.
New retrieval/storage/parse timestamps require timezone information.

The run manifest contains its format and run/source IDs, the CSV checksum and
the checksum of the exact source manifest, `parsed_at`, parser/schema/provenance
versions, normalization versions, status, counts, interpreted source date,
original date declaration, date status, and structured diagnostics. It binds
the interpretation to the acquisition facts used for that run.

Historical summaries retain counts of raw rows, adapted inputs, FIELD metadata
and diagnostics, plus diagnostic kind, severity, message, column and row ID.
They **do not restore a full historical parse result**: full rows, metadata and
derived objects require a new explicit `reparse`. `source_as_of` is interpreted
by the parser and therefore stored with the run, while its original declaration
remains in the source bytes. The compatible runtime `QueueSnapshot` still
combines these fields; it is not used as the persistence schema.

## Publication and validation

Writers use a `.pending-*` directory on the same filesystem, write and fsync
files, validate them, fsync the directory, then rename it to the final ID and
fsync the parent directory. Readers accept only published ID directories.
An interruption before publication leaves no readable partial record; remnants
of a killed process are ignored. A failure after rename may leave a complete
record, so callers should inspect published IDs before retrying. Filesystem
rename and fsync support are required; this is a local filesystem contract.

Every source read checks manifest version and fields, IDs, timestamp syntax,
byte length and SHA-256. Missing files, invalid JSON, duplicate keys, unsupported
versions, and checksum mismatches fail explicitly. Run reads also validate the
linked source and its exact manifest checksum. Readers never repair manifests.
Returned bytes and metadata/summary mappings are immutable through this API.

Append-only behavior is enforced by the API, not filesystem access control.
These checks detect content corruption relative to the stored manifest; they
are not signatures or protection against coordinated malicious rewriting of
all evidence. An invalid CSV may be a fully intact source snapshot: semantic
`ERROR` is stored separately in its run summary. An unexpected parser exception
propagates, leaves the source intact, and does not fabricate a successful run.

## Example

Run from the repository root with the project environment active. This example
uses the committed 13-row regression fixture, not a complete or current queue
export. It creates source and run records on disk under the git-ignored
`data/cache/queue-snapshots` directory. Repeating it creates new records:

```bash
python - <<'PY'
from pathlib import Path
from alma_duplicate.storage import QueueSnapshotStore

root = Path("data/cache/queue-snapshots")
store = QueueSnapshotStore(root)
source = store.save_source(
    Path("tests/fixtures/queue/queue_pipeline_v1.csv").read_bytes(),
    source_note="Committed regression fixture; incomplete queue; retrieval time unknown",
)
# The source is already published even if parsing now fails.
run, result = store.reparse(source.source_id)
print("source_id:", source.source_id)
print("run_id:", run.run_id)
print("retrieved_at:", source.metadata["retrieved_at"])
print("status:", run.summary["status"])
print("counts:", dict(run.summary["counts"]))

# A new store instance reads history without recomputing it.
reopened = QueueSnapshotStore(root)
assert reopened.read_source(source.source_id) == source
assert reopened.read_run(run.run_id) == run
print("Historical source and summary verified")
PY
```

For an optional full-snapshot run, replace the fixture path with a controlled
local CSV and record its actual provenance in `source_note`, `source_url` and
`retrieved_at` where known. Full operational snapshots are not committed; the
example filename is not evidence of a retrieval time. See the
[fixture scope](../tests/fixtures/queue/README.md).

Retain the printed IDs to reopen specific records later. Calling `reparse`
again creates a new run and fresh parse time; it does not overwrite the old run.
There is no automatic reconstruction, download, database, retention policy,
full historical-object serialization or Archive persistence in this module.
