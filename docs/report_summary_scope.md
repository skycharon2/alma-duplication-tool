# Report summary and evidence scope

The browser projects stored results and never recalculates a scientific verdict.

For each requested intent, standard context counts are disjoint:

- `met`: one recorded `CRITERIA_MET` branch.
- `not_met`: one recorded `CRITERIA_NOT_MET` branch.
- `review`: one recorded branch with another status.
- `unreported`: no branch, or conflicting/duplicate branch records. This is shown
  separately as missing or conflicting saved results, with a review group linking
  to the affected contexts.
- `excluded`: explicit `TP_IGNORED_FOR_DUPLICATION` contexts. These remain in the
  report but are excluded from assessment totals and unresolved counts.

Queue contexts superseded by a completed geometry assessment remain counted in
that assessment only. Batch and text reports use the same summary projection.
Queue geometry matched, unresolved and not-met configuration counts remain
separate. Identical counts across different proposed targets can occur because
all supplied Queue configurations are considered; a repeated count alone does
not establish a computational error or authorize removing unknown results.

Array ownership notices are grouped by recorded project/target and identical
ownership/limitation content on the displayed page. Missing object identities
never authorize grouping unrelated candidates. Scientific configurations, array
branches, SPW comparisons and per-configuration UNKNOWN notes remain independent.
No 12-m result is generalized to an unassessed ACA 7-m array.

TAP observation retrieval and AQ array acquisition have separate outcomes.
If observations were retrieved but AQ failed, overview labels explicitly name
both states. Saved error code, failed Member and mirror attempts are displayed.
New AQ failures also record safe completeness diagnostics: timeout, failed shards,
early termination, non-exact totals, count mismatch and hit limit, plus declared,
returned and configured maximum counts. No payload, credentials or HTTP headers
are copied into diagnostics. Existing all-or-nothing acceptance and mirror retry
behavior is unchanged; pagination is not introduced by this presentation fix.

The reported batch URL returned HTTP 404 during this investigation. Therefore the
original M33 count composition and CENA acquisition cause were not verified.
Regression tests use explicit synthetic excluded/unresolved/missing records;
they do not assert that the missing batch contained those exact records.
Historical generic AQ failures cannot retrospectively acquire detailed causes.

## Bounded AQ full-response expansion

A clean response truncated exactly at the initial 100-hit request limit now
triggers one full refetch using the exact declared total, up to 10,000 records
per Member by default. The initial response is discarded. The replacement must
pass all completeness and Member identity checks and retain the same total;
timeouts, failed shards, changed totals and further truncation remain failures.
No partial responses or different mirrors are merged. Duplicate source records
remain available to the existing ambiguity binder, without silent deduplication.

Query provenance records both request sizes and the final response hash. This
changes acquisition only, not scientific comparison formulas. Existing saved
reports require a new assessment to obtain newly retrieved evidence.

Live verification for `uid://A001/X2de/X186` completed through the existing
mirror client with `request_sizes=(100, 101)` and `total_hits=101`. The first
mirror also exhibited failed shards during verification; that incomplete
response was correctly rejected before successful mirror fallback.
