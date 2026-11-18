# Persistent report artifacts — Phase 2, step 05

This increment provides immutable local bundles, transactional publication and
workspace-scoped saved-report reads. It does not replace current browser
submission execution, install login or start a worker. The preceding submission,
job and lease must already exist before publication.

## Publication and failure semantics

`publish_report(engine, store, workspace_id, job_id, ...)` reuses RunStore's exact
serializer, inspection and indexed view generation in a temporary directory.
Scientific rules are not rerun. A configured per-report byte budget applies to
that serialization. The local ArtifactStore copies the files to a private staging
directory, hashes bytes, fsyncs files and directory, renames to an immutable random
bundle ID, and fsyncs the root. Published names are never reused or overwritten.

Only then does a database transaction lock and validate the active job lease,
append the Run and Artifact indexes, and mark the job completed while clearing
its lease fields. A failed transaction cannot expose a partially indexed report.
No filesystem/database distributed transaction is assumed:

- Interrupted copy: pending files are cleaned on a handled exception; a process
  crash can leave a `.pending-*` directory.
- Files published, database transaction fails: an unreferenced bundle remains.
- Commit response is lost: keep the bundle, because the commit may have succeeded.
- Published file becomes missing or corrupted: readers fail closed for that file;
  they never rerun acquisition to replace it silently.

There is deliberately no automatic orphan deletion. Later reconciliation must
compare database references and apply a grace period before deleting anything.
The service-owned artifact root must be on a persistent local filesystem; storing
it in `/tmp` defeats durability. Keep the database and artifact root together in
backup/restore procedures. Network filesystem durability and multi-host object
storage are not validated here. Disk-wide quotas and cleanup remain later work.

## Reading and existing URLs

`SavedReport(engine, store, authorized_workspace_id, run_id)` exposes indexed
`page`, `queue_page`, original download streams and the saved document. It requires
a completed job with the corresponding attempt and required artifact indexes.
Every opened file is size- and SHA-256-verified before use. This adds sequential
verification I/O to reads; no unbounded verification cache is introduced.

The Flask application supports an optional
`app.extensions['persistent_report_resolver']` callable. It receives a run ID and
must authorize the **current request's** workspace before returning a SavedReport.
It may return None or raise RecordUnavailable. It must not hard-code a shared
workspace in a public deployment. No resolver is configured by default, and no
unscoped lookup or default identity fallback is provided.

Existing `/runs/<id>`, `/runs/<id>/visualization`, `/runs/<id>/mosaic-visualization`,
Queue views and download paths first retain their temporary-store behavior, then
can read authorized persistent artifacts through this adapter. Persistent report
pages display saved-storage wording, not temporary-expiry wording. Browser writes
and Batch history migration remain deferred to the planned Web/worker integration.

## Local store boundary

The root is trusted operator configuration, not an upload field. Bundle keys are
strict UUID-hex/name pairs, with fixed allowed filenames. Reads reject symlink
bundles/files and verify the opened descriptor. Root access must be restricted to
the service account: this is not a defense against an administrator concurrently
rewriting directory trees. No arbitrary path is accepted from report URLs.
Files are immutable by storage contract, not a guarantee against direct local
filesystem modification; checksum failures make such modification detectable.

## Verification and limits

`python -m pytest -q tests/persistence` covers byte-identical export, corruption,
path traversal, symlink rejection, interrupted copy, stale leases, index-write
rollback, cross-workspace rejection and existing Flask routes across app restarts.
A fresh subprocess reopens the on-disk SQLite test index and local bundle,
generates visualization data and downloads the saved report with assessment
execution disabled. SQLite is a test harness, not a production database fallback.

PostgreSQL variants use the disposable schema fixture when
`ALMA_TEST_DATABASE_URL` is provided. Local tests do not establish PostgreSQL
commit/locking behavior or power-loss durability. Native PostgreSQL CI execution,
real-worker restart recovery, persistent Batch history, login, backup restoration
and storage cleanup remain explicit subsequent acceptance work.
