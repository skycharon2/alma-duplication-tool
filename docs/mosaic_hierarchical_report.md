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
paginated at 20 candidates per page. Mosaic URLs without an explicit
`view` parameter now default to matching candidates, consistent with the
positive-result-first report. The legacy `view=matches` spelling selects
`matching`; an explicit `view=all` displays every candidate. Single-point report selectors
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

## PR D — Member-centric positive-result navigation

The default matching view selects **Member OUS identities with a recorded
matching candidate**, then loads all saved `(member_ous_uid, source_name)`
candidate identities for each selected Member. Every recorded comparison
context is visible, with matching contexts first and expanded; other contexts
are present but collapsed. The candidate and context indexes, statuses, and
raw byte-for-byte exports remain unchanged. This is presentation, never a
Member-wide scientific verdict.

Matching pagination is **20 complete Member groups per page**. One Member may
include more than 20 related target identities; the page does not silently
split it. The diagnostic `all`, `review`, and `not_met` views continue to page
at 20 candidate identities and may split a Member, which is now explained in
the diagnostic page. The `matches` URL alias still selects `matching`.

Proposal ID, Group OUS and ASDM IDs are shown only if explicitly present in
the *same candidate's* already saved Archive `metadata_rows`, with exact
Member and target identity equality. Multiple conflicting proposal codes are
reported as conflicting; no ID is inferred from the shape of a UID or
`context_id`. For LINE context captions, SPW and ASDM associations come only
from exact matching `line_pairs[*].attempt.reference.candidate_association`
identities. Those context associations are not guessed from metadata rows.

The term **complete Member** in the view means all Member-related candidates
*already saved in this report*. It does **not** promise retrieval of every
Archive target or execution for the Member outside the original spatial
discovery. No new TAP or AQ queries are introduced. Discovery and scientific
classification remain unchanged.

### PR D checks

```sh
python -m pytest -q tests/ui/test_mosaic_member_hierarchy.py \
    tests/ui/test_mosaic_hierarchical_report.py \
    tests/ui/test_mosaic_report_view.py tests/ui/test_mosaic_execution.py
python -m pytest -q
git diff --check
```

Verify a captured CASE2 result: one matching Member X9c3, Project
`2018.1.00294.S`, Group OUS `uid://A001/X133d/X9c2`, associated ASDM
`uid://A002/Xd40be0/X42e2`, and SPWs 25, 27, 29 and 31.
