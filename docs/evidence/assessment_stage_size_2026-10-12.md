# Assessment stage timing and report size — 2026-10-12

## Scope

Baseline: `a920761` (PR #133), with the instrumentation and size analyzer in this
change. These measurements use the production `BrowserAssessment` and `RunStore`
through the diagnostic CLI. No scientific method, search radius, candidate cap,
report representation or retention budget was changed. This is performance
diagnosis, not a new scientific acceptance claim or an optimization benchmark.

Requests are the Queue LINE circinus and Archive CONTINUUM CASE1 inputs from the
[browser verification](browser_single_point_acceptance_2026-10-12.md). Queue uses
the complete 3200-row official snapshot dated 2026-03-03. Its SHA-256 is
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
Archive uses live TAP and live AQ. Both runs use AUTO and matching-detail reports.
The temporary storage budget remains 1 GiB.

Full timings, input hashes, source diagnostics and size tables are in the
[measurement JSON](assessment_stage_size_2026-10-12.json).

## Queue LINE

| Stage | Wall seconds |
| --- | ---: |
| CSV load | 0.672 |
| Context construction | 0.269 |
| Retrieval filtering | 1.821 |
| Scientific evaluation | 22.979 |
| Report assembly | 8.274 |
| Report encoding, hashing and writing | 16.545 |
| Inspection writing | 0.586 |
| Whole measured workflow, including other stages | **51.876** |

Results remain 3200 contexts: 1 LINE match, 118 not met, 3081 indeterminate,
matching the earlier browser run's counts. Source acquisition completed.

The report is **431,316,785 bytes**. The size analyzer reproduced that exact
file size, both for the newly generated document and the previous saved report.
Inspection adds 15,918,014 bytes; view indexing adds 229,204 bytes.

| Report field | Formatted bytes |
| --- | ---: |
| All context evaluations | 425,843,362 |
| Beam variants within those contexts | 415,635,842 |
| LINE pairs within those beam variants | 380,586,258 |
| Criteria within those LINE pairs | 333,108,434 |
| Source records | 5,463,897 |

The table contains nested subsets: **do not add its rows**. Beam variants occupy
96.36% of the report. The source records occupy only 1.27%.

Code inspection explains this distribution: `reporting._summary_results()`
preserves every pair's identity, criteria, reasons and method references,
recursively for each beam variant. Removing full calculation payloads from a
nonmatching context therefore still leaves substantial pair-level output.
The analyzer also finds identical LINE-pair lists under different beam variants;
the JSON records example paths without copying their scientific values.

Removing indentation alone would produce 247,813,322 bytes, still a large report.
That is a calculated size, not a newly written format. The stronger next target
is a compact representation of nonmatching pair decisions and shared repeated
evidence, preserving identities, method versions, missing reasons, outcome counts
and inspection behavior. Any change needs explicit report-reader compatibility
and scientific parity checks. This increment does not discard those records.

Report assembly plus report writing took 24.819 seconds. This identifies a
substantial optimization target; it does not predict how much time a revised
representation will save. Scientific evaluation is another separate cost.

## Archive CONTINUUM

| Stage | Wall seconds |
| --- | ---: |
| Optional-column metadata | 0.386 |
| TAP count | 46.883 |
| TAP retrieval | 47.330 |
| TAP total, including the three rows above | **94.612** |
| AQ discovery and 68 Member requests, including validation | **14.324** |
| Scientific evaluation | 0.176 |
| Report assembly | 0.063 |
| Report encoding, hashing and writing | 0.167 |
| Whole measured workflow | **109.831** |

Results remain 336 contexts: 16 CONTINUUM matches and 320 not met. TAP and AQ
completed. The report is 3,770,977 bytes. No unit-metadata query was needed in
this run; absent timing stages do not imply failed requests.

Here TAP dominates. Count and retrieval each took about 47 seconds. Their similar
durations motivate investigation of the two ADQL requests, but these client-side
timings do not reveal the server execution plan. The next Archive investigation
should examine query cost and how completeness is established. Simply dropping
the count query, reducing the search radius or limiting retrieved rows could
invalidate completeness guarantees. AQ optimization remains a separate, smaller
target for this particular run.

## Reproduce

Using the local artifacts from the browser verification:

```bash
python -m alma_duplicate.cli.profile_assessment \
  reports/pre-supervisor-2026-10-12/queue-line/request.json \
  --queue-csv ~/Downloads/duplication-check-csv.csv --analyze-size \
  --output reports/performance/queue-line-new.json

python -m alma_duplicate.cli.profile_assessment \
  reports/pre-supervisor-2026-10-12/archive-continuum/request.json \
  --live-archive --live-aq --analyze-size \
  --output reports/performance/archive-continuum-new.json

python -m alma_duplicate.cli.analyze_report_size \
  reports/pre-supervisor-2026-10-12/queue-line/report.json \
  --output reports/performance/saved-report-size-new.json
```

These local report artifacts are not committed; request values are documented in
the linked browser verification. Choose new output names for repeated measurements.

## Limits and validation

- One run per input. Local test processes ran during parts of the Queue diagnostic
  session; resource contention was not controlled. Repeat measurements on a quiet
  machine before claiming a speedup.
- The elapsed workflow excludes HTTP routing, Jinja, browser rendering and polling.
  These numbers are not click-to-page latency measurements.
- Size analysis runs afterward and adds 32.431 seconds for Queue and 0.418 seconds
  for Archive. It does not run on normal browser requests. Standalone loading and
  analysis of the saved Queue report took 35.732 seconds.
- TAP/AQ child timers include decoding/materialization. Write timers include
  serialization and hashing, so neither is a pure network or disk timer.
- Nested timing uses parent IDs and exclusive durations to avoid double counting.
  Repeated-container and field-group byte counts also overlap and are not additive.
- Full regression: **1898 passed, 12 skipped**. Focused checks cover nested timing,
  failure/reset behavior, unchanged scientific records, real stored-file sizes,
  Unicode serialization, duplicate detection and existing-output protection.
  Ruff F checks and `git diff --check` passed.
