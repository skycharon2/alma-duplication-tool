# Scoped metadata repositories — Phase 2, step 04

`WorkspaceRepository(session, workspace_id)` works inside the caller's
`transaction(engine)` context. It never commits independently. The caller must
roll back on database errors; it must not catch an integrity failure and continue
using the transaction. No repository is connected to Flask or live scientific
acquisition in this increment.

The workspace ID must come from a trusted, authorized caller. Merely constructing
a repository does not authenticate a user. Identity/login and workspace membership
checks belong to the later authorization step. Every record lookup and listing
is constrained by workspace; missing and foreign-workspace IDs produce the same
`RecordUnavailable` result. Composite foreign keys remain the second boundary
for parent associations.

## Operations

- `create_submission`: validate metadata, coordinates, input digest and paired
  Queue snapshot key/digest before writing; insert one submission, ordered source
  rows and pending jobs in the caller's transaction. Duplicate names/coordinates
  remain distinct source rows; missing redshift remains null. Multi input stays
  limited to five sources, matching the current browser contract.
- `get_submission`, `get_source`, `get_job`, `get_run`: detached dictionaries;
  editing a returned object does not update database JSON metadata.
- `list_submissions`: bounded pagination (up to 100), newest first with ID as a
  deterministic tie-breaker. Offset pagination is not a fixed history snapshot.
- `sources_for_submission`, `jobs_for_submission`: parent scope checked first;
  ordered by source ordinal (and purpose for jobs).
- `record_run`: append metadata only for a running, unexpired job lease matching
  attempt number and token. Locks the job row for the transaction on PostgreSQL;
  duplicate `(job_id, attempt)` fails rather than overwriting. Uses database time,
  with PostgreSQL `clock_timestamp()` rather than transaction-start time.

`record_run` deliberately leaves the job running: metadata does not establish
that artifact files exist or that publication is complete. Artifact storage and
atomic ready-state publication are subsequent work. There are no generic update
or delete methods for submissions or runs. A new assessment creates a new
submission; no idempotent HTTP submission key is introduced yet.

## Validation boundary

Metadata objects are JSON-compatible, finite and limited to one million UTF-8
bytes each. SHA-256 strings must be 64 lowercase hexadecimal characters. Source
coordinates are finite ICRS degrees; redshift is null or within the schema range.
These are persistence input checks, not a replacement for the existing scientific
request validator. Purpose values are LINE/CONTINUUM, and scientific status and
source provenance are preserved without interpreting UNKNOWN as a negative result.
Snapshot keys are bounded opaque metadata; artifact path validation belongs to
ArtifactStore and must not treat these keys as trusted filesystem paths.

## Tests and remaining scope

`python -m pytest -q tests/persistence` exercises creation, duplicate source
identity, cross-workspace reads, source order, rollback, bad inputs, inactive and
expired leases, stale tokens, duplicate run attempts and preservation of UNKNOWN.
The shared fixture also runs these cases on PostgreSQL when
`ALMA_TEST_DATABASE_URL` is provided. SQLite does not prove row-lock or concurrent
worker semantics; PostgreSQL execution remains necessary before worker rollout.
No scheduling, lease acquisition, retries, file publication, migration of legacy
reports or browser history integration is claimed by this step.
