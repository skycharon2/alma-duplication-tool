# Managed Queue source in the browser (PR3)

PR3 lets an operator opt the Flask assessment into PR2's approved `current.json`
without requiring visitors to upload or choose a CSV path. Queue acquisition
(PR1), explicit selection (PR2), and reading a frozen assessment input (PR3)
remain separate operations. A GET, form validation, assessment or health check
never contacts the Queue download service or updates a snapshot.

## Configuration and startup

From the repository root (Python 3.11+, `.[test,ui]` installed):

```bash
unset ALMA_UI_QUEUE_CSV ALMA_UI_ARCHIVE_REPLAY ALMA_UI_ARCHIVE_ARRAY_EVIDENCE
export ALMA_UI_LIVE_ARCHIVE=1
export ALMA_UI_LIVE_ARCHIVE_AQ=1
export ALMA_UI_QUEUE_SNAPSHOT_ROOT="$PWD/data/cache/queue-snapshots"
python -m flask --app alma_duplicate.ui.app:create_app run --host 127.0.0.1 --port 5050
```

`ALMA_UI_QUEUE_SNAPSHOT_ROOT` should be an **absolute persistent storage** path
for production. It must contain a source/run pair previously validated and
activated with the PR2 CLI. Configuration simultaneously specifying this root
and `ALMA_UI_QUEUE_CSV` fails at startup, rather than guessing a data source.
Leaving the managed root unset preserves the original offline file behavior.

For example, to check the state (the operator does this, not a visitor):

```bash
python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots status
```

To perform an explicit one-shot upstream acquisition, separately run:

```bash
python -m alma_duplicate.cli.queue_update \
  --once --store-root data/cache/queue-snapshots
```

That command does **not** switch `current.json`. Only an operator-approved
`queue_active activate` or `rollback` switches the active selection. PR3 does
not install a scheduler or auto-approve newer snapshots; scheduling remains a
separate deployment task. `NEW_VALIDATED` should be reviewed before activation.

## What the page shows

The Proposed Observation form shows the active Queue's official **data-as-of**
date, a checksum prefix, acquisition identity, and update-check status with its
last reported time. The acquisition log timestamps and scientific dataset date
are different facts. If the check log reports a failure, the page says so while
still showing the last validated active snapshot. No active pointer, corrupt
pointer, or corrupt log is not silently shown as a current Queue.

Each search-ready assessment using Queue pins approved exact raw bytes once,
**before** the source search executes. Its downloadable browser report receives
`document.sources.QUEUE.managed_snapshot`, including `source_id`, `run_id`,
`revision`, byte SHA-256, source-as-of date, original URL and retrieval time.
The report and display remain tied to that selection if the pointer changes
while the assessment runs. Legacy file-mode reports do not receive this field.
Archive-only runs do not access Queue snapshots. A missing/invalid active
snapshot is a failed Queue source, never a zero-candidate Queue result; Archive
can still be evaluated independently.

## Verification

```bash
python -m pytest -q \
  tests/ui/test_managed_queue.py \
  tests/integration/test_queue_update_provenance.py \
  tests/integration/test_queue_update.py \
  tests/integration/test_queue_active_flow.py
python -m pytest -q
python -m alma_duplicate.cli.acceptance \
  --catalog examples/acceptance/catalog.json \
  --output-dir reports/queue-pr3-acceptance
```

Default automated tests use synthetic/reduced offline Queue fixtures. The
committed fixture is **not** an official complete export. This PR does not
change scientific coverage, rule thresholds, Archive/AQ behavior or the report
version. A production deployment still needs authentication, persistent
server storage, a scheduled updater and explicit review/approval operations.
