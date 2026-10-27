# Archive Mosaic hierarchical browser report

## Scope and rationale

The browser evaluates fixed-target Archive Mosaic requests with the existing
`archive_mosaic_backend_2` path. PR A introduced the `mosaic_browser_view_1`
presentation index. This increment exposes the index in a readable report with
independent candidate filtering, Member grouping, context-specific decisions,
criterion explanations, and bounded pointing and spectral-window details.

The report is a presentation of stored data. Candidate discovery, `s_region`
classification, angular, continuum, spectral-line evaluation, and decision
aggregation are unchanged. The original request and full assessment report are
still available as byte-identical downloads.

## Hierarchy and identities

- **Assessment overview:** candidate categories, discovery status and assessment
  completeness are sourced from PR A's saved `mosaic_overview`.
- **Archive Member OUS:** an exact, nonempty `member_ous_uid` is the only
  permitted grouping key. Candidates without a Member identifier stay separate.
  Grouping is within a displayed page, not an assertion about an entire Member.
- **Target/candidate identity:** every `(member_ous_uid, source_name)` record
  remains separate and retains its original `candidate_index`.
- **Comparison context:** the exact recorded `context_id` is shown. No ASDM,
  spectral-window or execution identity is inferred from a generated ID.
- **Scientific criteria:** outcomes, reasons and operands are read from recorded
  context and LINE pair records. Existing single-point criterion presentation
  helpers are reused where their meaning is shared. `POS-MOSAIC` receives a
  dedicated label and strict-majority explanation.
- **Evidence:** `s_region` coverage counts are shown without recomputation.
  At most 20 pointing rows, 10 matching LINE pairs and 10 other LINE pairs are
  rendered for one context; the complete report contains every original record.

## Navigation and classification

The candidate categories in `mosaic_browser_view_1` are `MATCH`, `NOT_MET`,
`NEEDS_REVIEW`, and `UNAVAILABLE`. A candidate belongs to one category, but
its contexts may contain multiple branch outcomes. `MATCH` means at least one
recorded `CRITERIA_MET` branch. It is not a Member-wide duplication verdict.
An unavailable metadata acquisition is distinct from an evaluated but
indeterminate scientific comparison. The review tab includes both categories;
the overview reports their counts separately. An `INDETERMINATE` branch within
an otherwise matching candidate remains visible in the matching tab.

The available views are `all`, `matching`, `review`, and `not_met`. Each selects
candidate indexes from the saved PR A index without evaluating rules or reading
unselected full candidate payloads. Results retain discovery order and are
paginated at 20 candidates per page. Previously issued Mosaic URLs with no
`view` parameter retain the historical all-candidate behavior; the legacy
`view=matches` spelling is an alias for `all`. Single-point report selectors
retain their separate, established behavior.

## Evidence and completeness limits

A `COMPLETED` acquisition status is not proof of complete Archive recall.
A candidate that satisfies one branch can remain unresolved in another. Missing
`coverage`, LINE pairs or branch results must not be converted to negative
scientific judgments. The adopted Archive `s_region` policy is reported as a
project interpretation of half-power coverage, not a universally proven
primary-beam reconstruction. Scientific method approval is unchanged.

Grouping uses only stored Member identifiers. Member boundaries can span pages;
there is no cross-page merged verdict. Rendering still loads the complete
records for up to 20 selected candidates; per-context evidence tables are
bounded in HTML, but a single candidate may carry a large context collection.
Future lazy detail endpoints require a separate performance and access review.

The saved `view.json` projection and `report.json` publication schema remain
unchanged. PR A produces the index; this increment adds an ephemeral per-page
view model, a template, CSS, and URL selection. The page template does not issue
queries or mutate assessment data.

## Validation

Local checks:

```sh
python -m pytest -q tests/ui/test_mosaic_hierarchical_report.py \
    tests/ui/test_mosaic_report_view.py tests/ui/test_mosaic_execution.py \
    tests/ui/test_run_store.py tests/ui/test_report_presentation.py
python -m pytest -q
python -m compileall -q src/alma_duplicate/ui tests/ui/test_mosaic_hierarchical_report.py
git diff --check
```

Acceptance covers saved-category filtering, original candidate order, Member
identity boundaries, empty results, invalid pagination, selective disk reads,
byte-identical downloads and Jinja template parsing. Run the captured Mosaic
browser path and Single Pointing report checks to guard the shared helpers.
Record measured timings and real browser observations separately; a passed
unit test does not establish live Archive scientific acceptance.
