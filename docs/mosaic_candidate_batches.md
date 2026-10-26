# Bounded Mosaic candidate preparation and resume

Discovery may return more candidates than one acquisition invocation should process.
Preparation now accepts up to 10000 unique Member/target identities and attempts at
most 100 per invocation (or a smaller explicit `--max-candidates` budget). Every
remaining identity is retained as PENDING / NOT_STARTED. No candidate is truncated
or interpreted as non-duplicating because its acquisition has not started.

Each candidate runs the existing preparation worker, which still automatically
selects its product and applies download, weblog and expanded-byte limits. The
aggregate report records discovered, attempted, pending and failed-or-unready counts,
effective per-package limits and the conservative per-invocation download ceiling
(candidate budget times per-product byte cap). Cache hits consume an attempt but do
not download again. This ceiling is not a measured byte total or a quota spanning
all future resumes. Metadata queries have their existing independent bounds.

## Preparation CLI

```sh
python -m alma_duplicate.cli.mosaic_candidate_preparation \
  --discovery reports/mosaic-dev/case2-live-discovery-01/discovery.json \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/case2-batches-01 \
  --max-candidates 5
```

Use the same command with `--resume` to attempt the next five pending candidates.
Keep the same discovery file, cache path, offline/live mode and per-package limits.
The candidate count budget may change between invocations. Explicit large-package
flags remain available. The example's five-attempt default-download ceiling is
1.5 GB; larger CASE2 package limits require explicit flags and raise that ceiling.

## Common assessment entry

The evaluate entry automatically uses bounded preparation. Pending candidates are
reported without metadata requests or branch evaluation, and the overall assessment
remains INCOMPLETE. To continue, use the same proposal, OT input, discovery margin,
cache and limits, a fresh evaluation work directory/output file, and add:

```text
--mosaic-resume-preparation /absolute/path/to/first-workdir/preparation
```

The stored discovery plan must equal the plan for the supplied pointings and margin.
The preparation checkpoint verifies the full discovery fingerprint, mode, cache and
limits. Completed candidates are re-evaluated using the normal package/readiness
validation and fresh Archive metadata; pending candidates stay explicit. Discovery
is reused for this resume, not refreshed silently.

## Checkpoint and failure behavior

Each candidate has a separate directory. After it returns, its receipt hash is saved
in an atomically replaced checkpoint. Resume validates receipt hashes, candidate
identities and expected paths before reusing scheduling results. The main assessment
still reparses package evidence and validates readiness; a scheduling receipt is not
scientific validation of a package.

Recorded failures are preserved and are not automatically retried on resume. Once
all candidates have been attempted, any failed/unready candidate keeps the report
INCOMPLETE. A future targeted retry should use a new run containing those identities.
An interrupted worker may leave an uncheckpointed directory; recovery currently
refuses to overwrite it and requires a new run. Automatic partial-download recovery
and retry-in-place are not implemented. There is no support for concurrent writers
to the same preparation directory.

Tests cover 214 candidates over 100 + 100 + 14 attempts, retained failures, identity
changes, modified receipts, uncheckpointed work, invalid budgets, and the main-entry
pending/resume path. The 214-case scheduling test uses a synthetic acquisition worker;
it does not download all 214 live Archive candidates.
