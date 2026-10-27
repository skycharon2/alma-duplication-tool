# Archive Mosaic browser report projection

## Scope

The Archive Mosaic browser backend emits `archive_mosaic_backend_2`. Its report
contains candidate identities, Archive metadata, per-context scientific records,
pointing classifications, and spectral-window comparisons. The initial browser
renderer loads up to 20 candidate records per page from the immutable report.

`mosaic_browser_view_1` adds a separate, read-only presentation index to
`view.json`. The index is constructed at publication time from the recorded
report. It distinguishes Archive candidate identity, metadata comparison
context, and recorded branch/criterion outcomes. It does not alter the report
schema, candidate evaluation, discovery, or source acquisition.

## Rationale

`EVALUATED` is a metadata-processing state, not a duplication verdict. Only a
stored `CRITERIA_MET` branch supports a matching-comparison label. A stored
`CRITERIA_NOT_MET` branch rejects that branch within its evaluation scope.
`INDETERMINATE`, missing branches, and unrecognized statuses must not be
interpreted as negative decisions. Failed or incomplete candidate acquisition
remains separate from scientifically unresolved evaluated contexts.

The candidate-level display bucket uses the following precedence:

1. A candidate other than `EVALUATED` is `UNAVAILABLE` regardless of any
   attached partial scientific records.
2. An evaluated candidate with at least one `CRITERIA_MET` branch is `MATCH`.
3. An evaluated candidate with one or more branches, all exactly
   `CRITERIA_NOT_MET`, is `NOT_MET`.
4. Every other evaluated candidate is `NEEDS_REVIEW`.

This precedence is for navigation only. A `MATCH` candidate can contain other
unresolved or failing branches, whose exact statuses remain independently
indexed. A `NOT_MET` candidate means none of its recorded branches satisfy the
conditions; it does not establish an archive-wide negative result. Counts refer
to candidate identities, not unique executions or scientifically independent
observations.

## Indexed data

`view.json` retains the existing `mosaic`, `summary`, `document`,
`candidate_count`, and `offsets` keys. The new fields are:

- `projection_schema_version`: `mosaic_browser_view_1`.
- `mosaic_overview`: candidate and context totals, candidate display buckets,
  evaluated branch-status counts, and original candidate processing statuses.
- `candidate_summaries`: one entry per report candidate in original order,
  containing its index, Member OUS, source name, processing status, display
  bucket, and lightweight context summaries.
- Each context summary retains its position within the candidate,
  `context_id`, branch names and statuses, criterion IDs, recorded outcomes,
  formal aggregation eligibility, and spectral-line pair status counts.

The index omits original OT coordinates, Archive metadata rows, full `s_region`
polygons, criterion operands, calculated values, raw line pair bindings, and
free-text evidence. These remain available through the original indexed report
and unchanged download. The index is derived once during storage publication;
there is no scientific calculation at page-render time.

Browser pages continue using the existing 20-candidate pagination. Page data
contains the complete candidate records only for that page, the matching
`candidate_summaries` slice, and the global `mosaic_overview`. This increment
does not change navigation defaults, add status filters, or redesign the Jinja
template. Those changes belong to the separate hierarchical-report increment.

## Limits and interpretation

Counts are based on the reported branch statuses, not the Boolean `truth` field
or criterion outcomes. Criterion summaries are evidence labels, not substitute
branch decisions. Unknown and future status identifiers are retained and counted
under `OTHER_OR_UNRECORDED`; their candidate remains `NEEDS_REVIEW` unless an
independently recorded matching branch exists. A candidate without any branch
results is never classified `NOT_MET`.

One candidate can contain several contexts and several branches. Context-level
summaries preserve this multiplicity, while candidate bucket counts count each
candidate once. The projected overview never asserts complete discovery or
search-wide non-duplication; the original discovery and assessment statuses
remain visible separately.

The index is stored with the report under the existing per-run disk budget and
retention policy. It does not introduce persistent multi-user storage. The
projection is not a replacement for report JSON, external science review, or
source-completeness evidence.

## Verification

Run the focused tests:

```bash
python -m pytest -q tests/ui/test_mosaic_report_view.py tests/ui/test_mosaic_execution.py tests/ui/test_run_store.py
```

Run the full regression and static checks using the repository's existing CI
commands. The focused tests cover category precedence, mixed matched and
unresolved branches, missing and future statuses, incomplete metadata,
context/criterion identity, unchanged report bytes, and page-level indexed reads.

A successful test run verifies deterministic presentation behavior and storage
integrity. It does not establish the scientific equivalence of Archive `s_region`
and reconstructed half-power coverage or validate independently reviewed
proposals.

## Development verification record

Baseline reviewed: `main` at `2cac89acd4a4a355a09c088dfc9ad17e2d79ba09`
(2026-10-27, PR #183 merged).

The new projection module and test file passed Python syntax compilation.
Four projection-level pytest cases passed in an isolated package harness; the
store integration case was deselected because the full repository and its
runtime dependencies were not available in that harness. The patch passed a
`git apply --check` check against the exact targeted base-file excerpts. An
isolated immutability/status-count smoke test also passed.

These checks do not constitute a complete repository regression. Run the
focused and complete suites against the pinned working-tree baseline before
merging. Record the actual command output and the tested commit in the PR.
