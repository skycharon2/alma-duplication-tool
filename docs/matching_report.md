# Matching-detail reports (report v6)

New browser assessments generate report v6: full calculation evidence for
contexts with at least one recorded `CRITERIA_MET` branch, decision summaries
for all other contexts. Retrieval, evaluation and branch aggregation still run
over every retained context. No display limit changes scientific coverage.

The shared entry accepts `report_detail='matches'`. Its default remains `full`
(report v4), as does the evaluation CLI. To reproduce the browser representation:

```bash
python -m alma_duplicate.cli.evaluate --request REQUEST.json \
  --queue-csv SNAPSHOT.csv --queue-line --report-detail matches --output REPORT.json
```

Source flags and scientific options must match the intended run. Report detail
is a serialization choice, not an evaluator option. Solar exemptions continue
to use their existing v4 representation because no candidates are evaluated.

## Retention contract

Report v6 keeps the same request, source audit/provenance, request criteria and
evaluation-scope fields. `context_evaluations` retains every evaluated context
in its original order; counters and diagnostic links therefore keep their meaning.

`report_detail` declares mode `MATCHES_FULL_OTHER_SUMMARIES`, policy version `2`,
the full/summary context counts and the omitted field families. Each context has
`detail_level` equal to `FULL` or `SUMMARY`:

- **FULL:** all v4 context evidence is retained. A matching Member is still not
  a verdict on all its targets, executions or SPWs. A matching context retains
  all its pairs and beam variants, including their negative or unknown results.
- **SUMMARY:** retains source/context identity, display labels, branch results,
  methods/approvals, outcomes, reasons and issues. LINE pairs
  keep their original order, source-specific references, status and criteria.
  Beam variants remain separate with their original IDs and diameters. Bound
  Archive array provenance is retained.
- Summaries omit `evidence_states`, full `line_pairing` preparation, the prepared
  pair payloads, proposed/candidate criterion comparison values, derived calculation
  values and calculation-detail strings. Full matching contexts retain those values.
  The small `queue_geometry` label is retained for the existing scope explanation.

Missing details are deliberately omitted, not replaced with zero or fabricated
calculations. Unknown results remain unknown. Source failures, incomplete scope,
request gaps and all per-criterion missing-evidence reasons remain visible.
This is a decision report, not a lossless archive or an independent scientific
acceptance result.

## Generation, inspection and display

Selection happens on typed evaluator results **before** full evidence conversion.
The serializer never builds full nonmatching context documents and then discards
them. Full and summary records enter the same immutable browser storage path,
including byte offsets into the original report and original-byte downloads.
The browser stores each context once in `report.json`; page selection reads its
indexed byte range without loading the entire report.

Inspection v3 accepts v4, v5 and v6 and reports the actual input report version.
Gap counts, source statuses, branch counts and pair identities are unchanged for
the same evaluation. The reader rejects unknown policies, invalid references or
inconsistent detail labels/counts. Legacy v4/v5 reports remain readable without migration.

The normal page shows matching candidates with complete comparison tables.
The optional audit view groups equal recorded condition summaries for other candidates without
presenting omitted calculations as missing scientific input. Downloads clearly
identify the saved report, not a full-evidence export for every candidate.

## Validation and limits

Regression cases compare full and matching-detail serialization of the same
evaluation across Archive/Queue LINE, CONTINUUM, mixed intents, source failures,
missing evidence and 7 m/12 m variants. Full matching context records must equal
their v4 counterparts apart from the explicit detail label. Browser/CLI parity,
pagination, inspection and download lifecycle checks also apply to v6.

## Shared summaries in v6

Policy 2 declares `summary_encoding: SHARED_CRITERIA_REFERENCES`. In SUMMARY
contexts, each element of `criteria` (including inside LINE pairs and beam
variants) is a zero-based integer indexing the root `summary_criteria` table.
FULL contexts and request criteria continue to store inline criterion objects.
The table contains recorded decisions and diagnostic text; sharing is never a
scientific aggregation. Each occurrence retains its context, beam and pair identity.
Its context ID comes from the owning context rather than a shared table entry.

Interning happens on typed summary fields before JSON conversion. Each distinct
summary is converted once. No full nonmatching comparison payload is built for
this encoding. Readers use `report_summary.criterion_record()` to resolve a
reference; the page reader resolves only displayed contexts. References are
strict integers: booleans, negative/out-of-range values, missing tables and inline
records in v6 SUMMARY contexts are rejected.

Inspection v3 keeps the same occurrence locations, counts and pair references.
For a shared record it adds `criterion_record_location`, a JSON Pointer into
`summary_criteria`. The occurrence's pair `location` points to its integer
reference; the added pointer locates the criterion contents. Both are needed to
distinguish repeated occurrences from one stored decision. Missing reasons are
not deduplicated across distinct pairs or beam variants.

Report v5 policy 1 used inline summaries and retained comparison values. It is
readable as before. The measurements below describe those earlier implementations;
their versions and evidence have not been rewritten.

The default 1 GiB run-storage budget remains unchanged. Reports with many matches
or large source audits can still exceed it; storage failure stays explicit and
does not remove candidates or change outcomes. Live TAP/AQ acquisition time and
scientific evaluation time are unaffected by this retention policy.

## Complete CSV LINE measurement (2026-10-09)

The same `circinus_galaxy` request and complete CSV snapshot used in the
[initial performance investigation](evidence/assessment_performance_2026-10-09.md)
were measured again. Request and CSV SHA-256 values agree exactly. The
[new timing record](evidence/matching_report_performance_2026-10-09.json) preserves
all stage timings, artifact sizes, source statuses and outcome counts.

| Metric | Full v4 baseline | Matching-detail v5 |
| --- | ---: | ---: |
| Assessment, storage and first-page projection | 202.18 s | 55.34 s |
| Report assembly | 89.32 s | 7.39 s |
| Report serialization and write | 69.52 s | 17.09 s |
| Total stored artifacts | 2,526,521,309 bytes (2.35 GiB) | 690,790,632 bytes (658.79 MiB) |
| Storage budget used | 4096 MiB diagnostic override | Default 1024 MiB |
| Retained comparisons | 3200 | 3200 |
| LINE met / not met / indeterminate | 1 / 118 / 3081 | 1 / 118 / 3081 |

The new run completed and loaded its first results page within the default
retention budget. These are individual measurements on different runs, excluding
HTTP/Jinja/browser rendering; they do not guarantee a speedup for every request.
Many matching contexts can still produce a large report. The before/after
comparison shows the observed reduction, not a change to retrieval or evaluation.

Full regression: **1875 passed, 12 skipped**. Ruff `--select F` and
`git diff --check` passed. Browser checks used offline fixtures to confirm
matching comparison tables and nonmatching decision summaries render correctly.

## Single-copy browser storage (2026-10-12)

The browser now writes context byte offsets while publishing `report.json` and
uses that same file for pagination. Report, inspection and request downloads
retain their original bytes. This changes temporary storage only, not report
version, matching selection, scientific methods or evidence retention.

The same complete CSV LINE sample was assessed once and its exact result object
was saved by both the PR #131 store and the new store. The
[measurement record](evidence/indexed_report_storage_2026-10-12.json) records input
hashes, file sizes and download hashes. All three exports matched byte for byte
as verified by SHA-256. Both stores displayed the same matching comparison.

| Metric | PR #131 storage | Indexed original report |
| --- | ---: | ---: |
| Total retained bytes per run | 690,790,632 | 447,028,283 |
| Separate context file | 243,766,059 bytes | None |
| Store operation, including inspection and projection | 26.16 s | 21.36 s |

Storage falls by approximately 35.3%. Two runs now occupy 894,056,566 bytes and
remain readable together under the unchanged 1 GiB budget; their repeated exports
were also verified. This is one sequential comparison on the same machine,
excluding source access, scientific evaluation and browser rendering. It does
not establish a general query-time improvement. Large matching reports can still
reach the budget, and process-local reports remain temporary.

Verification for this storage increment: **1887 passed, 12 skipped**; Ruff
`--select F` and `git diff --check` passed. Tests cover Unicode byte offsets,
unchanged v4/v5 exports, indexed pagination, consecutive runs, expiry, count/byte
eviction, interrupted writes and active download leases. Local browser review
checked the normal report and distinct expiry, eviction and other-session pages
using offline fixtures. No live Archive acquisition was needed for this change.

## Shared-summary measurement (2026-10-12)

The same complete Queue LINE snapshot and request from the
[stage investigation](evidence/assessment_stage_size_2026-10-12.md) were run with
v6 summaries. [Measured results](evidence/shared_summary_performance_2026-10-12.json)
include input hashes, timings, byte counts and parity checks.

| Metric | v5, single-copy storage | v6, shared summaries |
| --- | ---: | ---: |
| Backend, storage and first-page projection | 51.876 s | 33.710 s |
| Scientific evaluation | 22.979 s | 23.630 s |
| Report assembly | 8.274 s | 3.078 s |
| Report encoding, hashing and writing | 16.545 s | 2.691 s |
| Report bytes | 431,316,785 | 71,075,300 |
| Total retained bytes per run | 447,465,312 | 88,885,217 |
| Retained comparisons | 3200 | 3200 |
| LINE met / not met / indeterminate | 1 / 118 / 3081 | 1 / 118 / 3081 |

The report is 83.5% smaller, and this measured workflow was 35.0% shorter. These
are individual runs, excluding browser/HTTP rendering. The earlier diagnostic
session had uncontrolled local test activity, so the figures are observations,
not a guarantee of speedup. Live Archive acquisition was not retested for this
serialization change; its dominant TAP cost remains separate.

Only 28 distinct nonmatching criterion summaries were needed. Every candidate
branch, pair order/reference, retained criterion decision and missing-evidence
occurrence was compared against the previous saved report. Matching contexts
remain exactly equal. Inspection equals the previous result after normalizing
the report version and removing the new storage-reference pointers.
Inspection itself grows slightly (15,918,014 to 17,552,348 bytes) because it now
also links to the shared criterion records; it retains all diagnostic occurrences.
Size analysis took another 6.023 seconds outside the measured workflow and is
not performed by browser requests.

Browser checks opened the real saved CSV report on localhost:5150, expanded the
matching circinus SPW 3 comparison, and checked the audit page's common-condition
and grouped LINE summaries. Historical v5 display, current exports and inspection
downloads are covered by tests. Full regression: **1906 passed, 12 skipped**;
final presentation/parity checks: **94 passed**. Ruff F and diff whitespace checks
passed.
