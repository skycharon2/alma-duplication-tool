# Assessment performance investigation

Reviewed code baseline: `016d784` (PR #130), with the opt-in timing instrumentation
delivered alongside this record. Measurements use the browser backend and temporary
run storage, excluding HTTP/Jinja/browser rendering. Original UTC timestamps,
request hashes, source modes, budgets, stage timings and artifact sizes are in
[the timing records](assessment_performance_2026-10-09.json), together with the
four request documents. The CSV itself is not included.

## Initial sequential runs (2026-10-08 UTC)

| Input | Source result | Total elapsed | Main stages | Retained contexts |
| --- | --- | ---: | --- | ---: |
| Queue NGC6240 CONTINUUM | Completed | 22.67 s | Evaluation 5.52 s; report assembly 5.52 s; report write 6.55 s | 3200 |
| Queue circinus_galaxy LINE | Completed with diagnostic storage budget | 202.18 s | Evaluation 27.16 s; report assembly 89.32 s; report write 69.52 s; context index write 10.91 s | 3200 |
| Archive CASE1 CONTINUUM | Completed, live TAP + AQ | 113.01 s | TAP 97.00 s; AQ 14.88 s | 336 |
| Archive IRAS09245 LINE | Source failed; failure report saved | 29.26 s | TAP client 29.13 s; no retained contexts | 0 |

Both Queue runs used the same complete local CSV snapshot (1,448,241 bytes;
SHA-256 recorded in the timing files), not a newly downloaded snapshot. Each
produced 1 matching, 118 nonmatching and 3081 indeterminate branch comparisons.
These counts describe this snapshot and input; they do not establish independent
scientific acceptance. Archive CONTINUUM produced 16 matching and 320 nonmatching
comparisons. Counts are comparison contexts, not unique Members or projects.

The original Archive LINE record predates detailed source diagnostics. Its cause
cannot be recovered from that record alone. It must not be treated as a successful
LINE benchmark or a zero-duplication result.

## Archive LINE follow-up (2026-10-09 UTC)

The same request was first retried in the restricted network environment. It
returned `SERVICE_ERROR` in 0.11 s; AQ was correctly skipped with
`TAP_NOT_COMPLETED`. This restricted-access attempt is not a service-speed
measurement and does not establish the cause of the original October 8 failure.

A subsequent run with network access completed successfully in **97.84 s**:
TAP acquisition 97.20 s, AQ acquisition 0.58 s, scientific evaluation 0.02 s.
It retained 4 contexts: **1 LINE comparison met criteria and 3 did not**.
AQ status was `COMPLETED`. Both follow-up records are retained alongside the
original failure; none of the results overwrite earlier measurements.

Thus the successful live Archive measurements both point to TAP acquisition as
the dominant elapsed stage for these inputs. They remain individual observations,
not an estimate of typical remote-service latency.

## Storage and timing limits

Queue LINE artifacts totaled 2,526,521,309 bytes (2.35 GiB), including a
1,695,650,984-byte report and an 814,743,060-byte context index. That measurement
explicitly used a 4096 MiB diagnostic budget. The browser's default 1024 MiB budget
was unchanged and cannot retain these artifacts. This run therefore does not
demonstrate successful default browser storage for this input.

Queue CONTINUUM artifacts totaled 300,989,022 bytes. CSV loading took less than
one second in both runs. Report assembly, inspection, serialization, index
construction and writes accounted for about 85% of the Queue LINE elapsed time.
Write spans include encoding and hashing, so these numbers do not isolate disk
latency. TAP and AQ spans include client parsing and validation as well as HTTP.
Thread CPU measurements are retained as diagnostics, not used to infer pure
network or disk wait time.

These are single-run observations. External service load, local scheduling and
filesystem caches can change timings substantially; no speedup is claimed.

## Next engineering increment

1. Reduce repeated report conversion/serialization work. `reporting.py` converts
   criterion and pair evidence and then recursively converts the assembled report
   again. Measure this path before and after changing it, keeping scientific
   records and exported report content equivalent.
2. Address large stored reports and the repeated context index deliberately.
   Faster serialization alone will not solve the default storage-budget failure.
   Preserve full evaluation, provenance and page/download consistency; do not
   silently drop candidates or evidence to fit the quota.
3. Investigate Archive acquisition separately, repeating the successful LINE and
   CONTINUUM inputs before choosing a caching or query optimization.

CSV download caching alone would not address the dominant cost observed here.
No scientific formula, retrieval scope, candidate limit or progress semantics
was changed for these measurements.

## Implementation verification

Full offline regression: **1852 passed, 12 skipped**. Focused tests cover timing
scope reset, unchanged scientific records with recording enabled, storage failure,
and a saved failure report distinguished from successful source acquisition.
Ruff `--select F` on changed Python files and `git diff --check` passed.
