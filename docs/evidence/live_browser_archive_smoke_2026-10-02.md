# Live browser Archive smoke — 2026-10-02

## Purpose

This record documents a point-in-time engineering smoke of the browser's
explicit live Archive source path after PR #119.

It verifies the browser-to-shared-entry-to-production-Archive-client wiring
against the live ALMA TAP service. It does not establish a scientific
duplication verdict, reviewed real-proposal acceptance, stable future service
availability, or live Archive Query (AQ) integration.

## Baseline and configuration

The browser smoke ran from merged `main` at
`e991ade59fac2105c0671e9f158955bb54d1ed3f` (PR #120), which includes the
LIVE-SOURCE implementation merged in PR #119.

Browser source configuration:

```text
ALMA_UI_LIVE_ARCHIVE=1
ALMA_UI_ARCHIVE_REPLAY unset
ALMA_UI_ARCHIVE_ARRAY_EVIDENCE unset
```

The configured Archive TAP endpoint was:

```text
https://almascience.eso.org/tap
```

No Queue source was selected for the browser run.

## Production Archive client preflight

Immediately before the browser run, the existing opt-in production live smoke
was executed:

```bash
python -m pytest -q -s \
  --run-live \
  tests/live/test_archive_tap_smoke.py
```

Observed result:

```text
3 passed

status=COMPLETE
expected_count=212
retrieved_count=212
count_status=OK
retrieval_status=OK
field_metadata=30

pipeline:
retrieved_rows=212
prepared_rows=212
linked_rows=212
unlinked_rows=0
associations=212
```

These counts belong to that smoke test's query. They are not expected to match
the separate browser query below.

## Browser request

The browser used a fixed, single-point engineering request centered on NGC6240:

```text
target_kind=FIXED
geometry=SINGLE_POINTING
target_name=NGC6240 live browser smoke

ra=253.24541666666667 deg
dec=2.4010972222222224 deg
frame=ICRS

intent=CONTINUUM
angular_resolution=500 mas
representative_frequency=338.5 GHz SKY

continuum_setup_declaration=
  AT_LEAST_TWO_USABLE_WINDOWS_GT_1_8_GHZ

search_radius=30 arcsec
sources=ARCHIVE
result_limit=1
```

The request contained no detailed spectral windows and no sensitivity rows.
It was an engineering source-execution smoke, not a reviewed scientific
duplication case.

## Browser execution result

Run assessment completed and produced report v4.

Observed report-level values:

```text
report_version=4
assessment=NOT_AGGREGATED
generated_at=2026-10-02T11:20:12.657129+00:00
```

Observed Archive source values:

```text
input_mode=CLIENT
status=COMPLETED
query_binding.status=MATCHED

processed_rows=144
retained_rows=144
excluded_rows=0

evaluation_scope.total_retained=144
evaluation_scope.evaluated_contexts=144
evaluation_scope.shown_candidates=1
evaluation_scope.display_truncated=true
```

The result limit affected display only. It did not truncate retained or
evaluated contexts.

## Live TAP provenance

The report preserved live Archive query provenance:

```text
endpoint=https://almascience.eso.org/tap

expected_count=144
retrieved_count=144
count_query_status_raw=OK
retrieval_query_status_raw=OK

query_run_id=c71b3b86-bf36-4110-8715-1b0b957baccc
query_hash=4b14e33593ef1eac929529e7a55f1233c3e194a50532cb3a0fb5de2103eda0df

started_at=2026-10-02T11:20:11.221423+00:00
finished_at=2026-10-02T11:20:12.447022+00:00

missing_columns=[]
```

The TAP projection returned all 30 selected core/optional fields for this run.

## Filter completeness

The Archive source completed successfully, while:

```text
requested_filters_fully_evaluated=false
```

This is not a retrieval failure.

The source recorded:

```text
ARCHIVE_REGION_COVERAGE_NOT_UNIVERSAL
```

and the local spatial audit was:

```text
spatial MATCH=96
spatial NOT_EVALUATED=48
excluded_rows=0
```

Therefore all 144 returned rows were retained, while 48 retained rows still had
an unevaluated spatial condition. This is consistent with the existing
candidate-search completeness contract and does not establish a negative
search-wide duplication conclusion.

## Replay and AQ boundary

The browser run was configured without Archive replay and without captured AQ
array evidence.

A recursive inspection of the serialized Archive source report found no keys
whose names contained:

```text
replay
array_evidence
aq
```

This observation establishes that no replay/AQ provenance was serialized for
this run. It is not, by itself, a network trace proving which HTTP endpoints
were or were not contacted.

The separate LIVE-SOURCE implementation and regression contract establishes
that live TAP does not implicitly perform a live AQ lookup and does not fall
back to replay. This smoke does not add automatic live AQ acquisition.

## Interpretation and limits

This smoke establishes a point-in-time engineering observation that:

- the browser accepted an explicit live Archive configuration;
- the browser assessment reached the production Archive client;
- the production client successfully queried live ALMA TAP;
- the browser retained and rendered the resulting report v4;
- live TAP query provenance was preserved;
- no replay or captured-AQ provenance appeared in the resulting Archive report.

It does not establish:

- a reviewed real-proposal duplication result;
- a search-wide duplicate/non-duplicate verdict;
- universal evaluation of all returned candidate conditions;
- future ALMA TAP availability or schema stability;
- automatic or supported live AQ acquisition;
- broader TP CONTINUUM/LINE applicability;
- Mosaic or moving-target support.

The browser report's top-level `NOT_AGGREGATED` assessment remains intentional.
