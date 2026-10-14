# Official Queue CSV acquisition (PR1)

This is a **one-shot, opt-in acquisition command**, not automatic scheduling or
active snapshot selection. It uses the official ALMA latest Queue CSV endpoint.
The ALMA source's `source_as_of` date can remain old even when the download
check succeeded today. Archive and Queue are separate evidence sources.

## Usage

Install the project on Python 3.11 or later, from the repository root:

```bash
python -m pip install -e '.[test,ui]'
python -m alma_duplicate.cli.queue_update --once \
  --store-root data/cache/queue-snapshots
```

This command contacts the official service. The first valid download produces
`NEW_VALIDATED`; identical bytes with previously validated parse history return
`UNCHANGED`. `activated` is always false in PR1. A rejected new source returns
`VALIDATION_FAILED`; repeated previously rejected bytes return `KNOWN_INVALID`.
`DOWNLOAD_FAILED` and `STORAGE_FAILED` are distinct. `UPDATE_UNAVAILABLE` means
the storage/update lock could not be obtained. Non-success states exit with code 2.

The check is bounded to 64 MiB and HTTPS on `almascience.eso.org`, with timeouts,
checked redirects, and HTML/error response refusal. HTTP ETag/Last-Modified
headers may be recorded but **do not** establish whether contents changed;
SHA-256 of the downloaded bytes does. Conditional HTTP caching is not implemented
in PR1.

## Files and history

`data/cache/queue-snapshots/sources/<source_id>/` retains original bytes and
source manifests. `runs/<run_id>/` preserves parse summaries. `checks.jsonl`
records check results, including failed attempts. `.queue-update.lock` prevents
concurrent updater invocations. `data/cache/` is git-ignored; do not commit actual
operational CSV bytes or reports into a public repository.

This updater does **not** create `current.json`, set `ALMA_UI_QUEUE_CSV`, refresh
Queue when a researcher opens the website, or publish a fresh-data claim.
Existing browser assessments still use the manually configured CSV path.

The validation gate requires `QueueCsvParseResult.can_reconstruct`, at least one
row and a successfully parsed Queue source-as-of date. A `COMPLETE_WITH_WARNINGS`
parser result may pass this basic gate; any warnings and raw source evidence remain
available for review. This is not human scientific approval, proof of official
freshness or proof that the current Queue is exhaustive. PR2 will implement a
separate, stricter activation gate (date monotonicity, unusual population/schema
changes and manual review of suspicious changes).

## Offline verification

```bash
python -m pytest -q tests/unit/test_queue_downloader.py \
  tests/integration/test_queue_update.py \
  tests/unit/test_queue_snapshot_store.py
python -m pytest -q
python -m alma_duplicate.cli.acceptance \
  --catalog examples/acceptance/catalog.json \
  --output-dir reports/queue-pr1-acceptance
```

Tests use simulated HTTP; they do not contact the ALMA service. The 13-row
fixture is for engineering regression and is **not** a complete or current
Queue export. Avoid reusing an existing acceptance output directory.
