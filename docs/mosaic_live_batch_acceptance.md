# Live small-batch preparation acceptance

On 2026-10-26, the saved 214-candidate NGC253 discovery was prepared against live
Archive inventory, DataLink and AQ services. The first invocation attempted five
candidates using default per-package limits. A second invocation used the same
discovery, cache and limits with `--resume --max-candidates 5`.

| Stage | Attempted | Prepared | Failed or unready | Pending |
| --- | ---: | ---: | ---: | ---: |
| First invocation | 5 | 3 | 2 | 209 |
| After resume | 10 | 5 | 5 | 204 |

The first five checkpoint receipt hashes were unchanged after resume. Those
candidates were not reacquired. Five candidates used the single-field metadata/AQ
path; two Mosaic candidates had no usable auxiliary product. Three more failed
at package reconstruction because their advertised package size exceeded the default
300 MB download limit. No limit was raised for this live batch, and these failures
are not negative duplication verdicts. No package cache hit occurred in these ten
attempts, so they alone do not verify cached package reconstruction.

Local evidence: `reports/mosaic-dev/live-batch-acceptance-01/`. Exit code 3 and
INCOMPLETE are expected while candidates remain pending or failed. This is acquisition
acceptance, not final evaluation of all ten candidates or all 214 observations.

## Timing and terminal output

Each newly attempted candidate now records `preparation_elapsed_seconds` using a
monotonic clock. The checkpoint binds the updated receipt. Resume retains recorded
timings. Reports add prepared/cache-reuse counts, `measured_candidate_count` and
`measured_candidate_seconds`; older receipts without timing are not treated as
measured zero-duration attempts. The sum is measured candidate work only, not
whole-run wall time or transfer throughput.

The first live batch ran before timing was added. The second batch measured five
candidate attempts, approximately 3.32 seconds combined. Historical timing was not
fabricated. The CLI prints attempted statuses and a compact summary instead of
printing hundreds of PENDING lines; all pending entries remain in the JSON report.

## Separate cache check

A separate one-candidate offline replay uses the captured CASE2 X9c3 inventory,
DataLink and AQ responses with the actual cached 932 MB auxiliary tar. Explicit
large-package limits remain required. The run revalidates the archive hash, rescans
its contents and reconstructs readiness through the same preparation scheduler.
Evidence is in `reports/mosaic-dev/live-batch-cache-acceptance-01/`. This separates
real cache reuse from the ten-candidate live run rather than claiming a cache hit
that did not occur there.

## Next work

Recorded failures are not retried by `--resume`. A targeted new run can reconsider
size-limited products under explicit budgets, while genuinely missing products stay
unresolved. No reason exists to download the remaining 204 candidates automatically
as part of this acceptance. Reliable metadata exclusions, user-visible pending and
failure reasons, and targeted retry remain the next integration work.
