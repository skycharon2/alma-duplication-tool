# Active Queue snapshot selection (PR2)

PR2 adds a **manual, atomic pointer** to an already archived, validated official
Queue CSV acquisition. It does not download files, schedule updates, change the
scientific evaluator, or switch the Flask UI's `ALMA_UI_QUEUE_CSV` configuration.
See [PR1 acquisition](queue_auto_update.md) and the existing
[append-only evidence store](queue_snapshot_store.md).

## Run from the repository root

Use a Python 3.11+ environment with the project installed. PR1 must already be
present on this branch. The checked CSV bytes and parse-run manifest must exist
in the same `--store-root` directory.

```bash
python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots status

python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots activate \
  --source-id ACTUAL_32_HEX_SOURCE_ID \
  --run-id ACTUAL_32_HEX_RUN_ID \
  --reason 'Manually reviewed official Queue source and date'

python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots history
```

Get the source ID and run ID from the PR1 updater's **actual JSON output** (or
validated manifests). An example is not a source ID. This activation command
must be called explicitly: PR1's `--once` never runs it. Success prints an
`ACTIVATED` record; the same source/run returns `ALREADY_ACTIVE` without rewriting
the pointer. `status` returns `NO_ACTIVE_SNAPSHOT` before initial activation.

## Safe-switch gate

The registry validates the exact stored acquisition and the linked parse-run,
requiring matching source ID, source manifest hash and CSV SHA-256; an official
HTTPS `DOWNLOAD_URL` with a recorded retrieval time; nonempty, fully adapted
Queue rows; `COMPLETE` or `COMPLETE_WITH_WARNINGS`; a parsed source-as-of date;
and parser/schema/normalization versions matching current code. It does **not**
claim the official source is independently cryptographically authenticated or
that scientific judgments have been independently reviewed.

A candidate with an **older declared source date** cannot replace a newer
active snapshot via `activate`. Instead use the explicit `rollback` command to
select a previously active revision. If source-as-of dates are equal but CSV
hashes differ, the operator must approve that exception explicitly by adding
`--allow-same-date-change` to `activate`, with a review reason. These guards are
scientific-data freshness guardrails, not assertions that the official queue is
updated daily. A future-dated source is refused.

If the project parser/schema/normalization versions change, reparse the source
with the new code and activate the new parse-run ID. Never silently rely on an
old parser's validation result. Unsupported or corrupt active records cause
`status` to fail closed; they do not automatically fall back to another source.

## Rollback and recent history

Each successful activation creates a new 32-hex `revision`. The active state
contains the most recent 64 previous activation *metadata* entries, with a
new revision created for each rollback. This bounded history lives **inside**
`current.json`, so the current choice and its recent audit trail change
atomically. Published `sources/` and `runs/` remain append-only; older raw
snapshots are preserved separately, even if their activation revision has aged
out of the 64-entry selection history.

Read the target revision in `history` and run:

```bash
python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots rollback \
  --revision ACTUAL_PREVIOUS_REVISION \
  --reason 'Explicit rollback after review'
```

Rollback revalidates the old source/run and its current parser compatibility.
It never copies or edits historical CSV bytes. To adopt historical bytes no longer
in the recent activation history, explicitly reparse and manually approve a new
candidate according to current policies; there is no automatic downgrade bypass.

## Persistence, locking and trust

`current.json` is JSON v1 under the same store root. Its fields include
`source_id`, `run_id`, `snapshot_sha256`, `source_manifest_sha256`, `source_as_of`,
`revision`, `reason`, `activated_at`, and `recent_history`. An exclusive
`.queue-active.lock` prevents concurrent registry modifications. Publication
writes and fsyncs a temporary file, atomically replaces `current.json`, then
syncs the directory. Readers see the prior or the new complete selection.

The directory must be on a trusted persistent local filesystem with atomic
rename and fsync support and kept outside publicly served paths. This is not a
multi-user security or permission system; the filesystem owner controls the
selection. Existing PR1 `.queue-update.lock` operates independently because
updater acquisition is append-only and publishes records atomically.

PR2 does not add a periodic job, web status display or report serialization.
These are separate PR3/deployment activities. `data/cache/` is git-ignored; do
not commit `current.json`, raw CSV snapshots or operational check logs to GitHub.
