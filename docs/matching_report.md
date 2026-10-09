# Matching-detail reports (report v5)

New browser assessments generate report v5: full calculation evidence for
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

Report v5 keeps the same request, source audit/provenance, request criteria and
evaluation-scope fields. `context_evaluations` retains every evaluated context
in its original order; counters and diagnostic links therefore keep their meaning.

`report_detail` declares mode `MATCHES_FULL_OTHER_SUMMARIES`, policy version `1`,
the full/summary context counts and the omitted field families. Each context has
`detail_level` equal to `FULL` or `SUMMARY`:

- **FULL:** all v4 context evidence is retained. A matching Member is still not
  a verdict on all its targets, executions or SPWs. A matching context retains
  all its pairs and beam variants, including their negative or unknown results.
- **SUMMARY:** retains source/context identity, display labels, branch results,
  criterion values, methods/approvals, outcomes, reasons and issues. LINE pairs
  keep their original order, source-specific references, status and criteria.
  Beam variants remain separate with their original IDs and diameters. Bound
  Archive array provenance is retained.
- Summaries omit `evidence_states`, full `line_pairing` preparation, the prepared
  pair payloads, derived calculation values and calculation-detail strings.
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
including the indexed context file and original-byte downloads.

Inspection v3 accepts v4 and v5 and reports the actual input report version.
Gap counts, source statuses, branch counts and pair identities are unchanged for
the same evaluation. The reader rejects unknown v5 policies or inconsistent
detail labels/counts. Legacy full v4 reports remain readable without migration.

The normal page shows matching candidates with complete comparison tables.
The optional audit view shows decision summaries for other candidates without
presenting omitted calculations as missing scientific input. Downloads clearly
identify the saved report, not a full-evidence export for every candidate.

## Validation and limits

Regression cases compare full and matching-detail serialization of the same
evaluation across Archive/Queue LINE, CONTINUUM, mixed intents, source failures,
missing evidence and 7 m/12 m variants. Full matching context records must equal
their v4 counterparts apart from the explicit detail label. Browser/CLI parity,
pagination, inspection and download lifecycle checks also apply to v5.

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
