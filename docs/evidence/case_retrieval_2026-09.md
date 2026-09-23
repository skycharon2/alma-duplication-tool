# CASE retrieval evidence: September 2026

Historical measurements and assumptions preserved from PR #76. The final old
paragraph contains then-pending grouping language; it does not override the
current confirmed coherent-context unit. CASE1/2 remain retrieval references,
not reviewed duplicate/non-duplicate scientific labels. The confirmation does
not create labels or assert every CASE grouping acceptance test is complete.

### Recorded CASE inputs

Transcribed from original internship task section 4, printed page 2; operators
and units preserved. These belong to case search conditions, not exact proposed
observation values. The frequency is a source-specified point query; no matching
tolerance or frame is supplied.

User-facing case search inputs:

| Case | RA (HMS) | Dec (DMS) | Frequency | Angular filter | Spectral filter | RMS filter |
| --- | --- | --- | --- | --- | --- | --- |
| CASE1 | 18:33:39.920 | -21:03:39.900 | 290.420 GHz | < 0.5 arcsec | < 1500 kHz | < 0.02 mJy/beam |
| CASE2 | 00:47:33.064 | -25:17:18.280 | 690.0 GHz | < 1 arcsec | < 4000 kHz | < 1 mJy/beam |

Developer reference results, not query requirements or user request fields:

| Case | Reported project | Source-stated entries | Reported Member UID(s) | Formal verdict |
| --- | --- | --- | --- | --- |
| CASE1 | 2021.A.00028.S | 1 | `uid://A001/X2df9/X1b` | Unverified |
| CASE2 | 2018.1.00294.S | 2 | `uid://A001/X133d/X9c3`, `uid://A001/X133d/X9c5` | Unverified |

### Executed retrieval evidence (2026-09-10 run)

[tests/live/test_case_retrieval.py](../../tests/live/test_case_retrieval.py) was
run with `--run-live` against the live Archive TAP service (developer
environment; endpoint/date not independently re-verified by this document
beyond the test run itself). Both cases PASSED: every reported Member UID
above was present among the retrieved Archive rows within the test's 10
arcsec engineering search radius. This confirms retrieval recall only, not a
duplication verdict, grouping, or count -- see the test's module docstring
for that boundary.

| Case | Retrieved rows | Disposition split | Matched Member UID row(s) | Local spatial-adapter reason on matched rows |
| --- | ---: | --- | --- | --- |
| CASE1 | 336 | 200 RETAINED_UNEVALUATED / 136 EXCLUDED / 0 MATCHED_FILTERS | 4 SPW rows for `uid://A001/X2df9/X1b` | `TP_OR_UNRECOGNIZED_ARRAY_UNSUPPORTED` (REGION strategy; local array-type recognition failed, server-reported scope retained as unevaluated, not excluded) |
| CASE2 | 871 | 323 RETAINED_UNEVALUATED / 548 EXCLUDED / 0 MATCHED_FILTERS | 9+ SPW rows spanning both `uid://A001/X133d/X9c3` and `uid://A001/X133d/X9c5` | `MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED` (REGION strategy; candidate appears to be a mosaic, so local region intersection is not attempted) |

Both cases' matched rows also passed the local `angular_resolution` filter
(`MATCH` against the recorded `< 0.5`/`< 1 arcsec` case filters); the
`spectral_resolution`/`sensitivity` predicates stayed `SKIPPED` as designed
(not implemented by this service yet). No `MATCHED_FILTERS` disposition
occurred for either case's matched rows -- this is expected under the
current spatial/frequency evaluation gaps, not a defect.

A companion measurement,
[tests/live/test_case_beam_strategy_applicability.py](../../tests/live/test_case_beam_strategy_applicability.py),
found that in the real Archive rows near both cases, the formula
primary-beam strategy's exact `12-m`/`7-m` `antenna_arrays` label match
resolved a diameter for **0 of 336** CASE1 rows and **0 of 851** CASE2 rows
-- every observed label was a detailed pad:antenna listing or an ACA/TP
array listing instead. This was originally a small, local-neighborhood
sample pending Archive-wide confirmation via
[scripts/beam_array_label_census.py](../../scripts/beam_array_label_census.py).

**That census has now been run (2026-09-10) against the full live Archive**:
across all 443,998 `science_observation = 'T'` rows (13,058 distinct
`(antenna_arrays, is_mosaic)` groups, no query-cap overflow), **0%** matched
the exact string `12-m` or `7-m` -- every single row, mosaic and
non-mosaic alike, classified as `OTHER_DETAILED_OR_MIXED` (a detailed
pad:antenna listing or an ACA/TP-only listing). The full report, including
sample raw label values per bucket, is written to
`docs/evidence/primary_beam_array_label_census_2026-09-10.md`. This
upgrades the CASE1/CASE2 finding above from "a concrete zero in two local
neighborhoods" to a **confirmed Archive-wide zero**: the current exact-label
heuristic in `primary_beam.py` does not resolve a diameter for the Archive
side of the formula primary-beam strategy on *any* row in the present
Archive population, not merely a low or unlucky share of it. This made a
real `classify_array_type()` parser a prerequisite --not merely a
strengthening consideration-- for relying on the Archive side of this
strategy beyond hand-checked cases with a manually supplied diameter. That
parser now exists; see [search/spatial](../search_plan_spatial.md#spatial-evidence).

### Entry-count reproduction (2026-09-11)

With the opt-in Archive Query-equivalent filters (frequency point in SPW,
angular and spectral resolution, AGGREGATE `cont_sensitivity_bandwidth`) and
(Member OUS, target) grouping, the live rows reduce to exactly the reported
entries: CASE1 one entry, `uid://A001/X2df9/X1b` / PKS1830-211, matched by all
filters; CASE2 two entries, `uid://A001/X133d/X9c3` and `X9c5` / NGC253, retained
because their mosaic geometry is not evaluated. The ALMA Archive Query service
keys its observation entries the same way (`<member_ous_uid>.source.<target>`;
2021.A.00028.S has four entries, one science target). This was reproduced from
live rows outside the test runner; `test_case_entry_count_with_aq_equivalent_filters`
pins it and must be run with `--run-live`. It supports, but does not close, Q7:
the grouping still needs the supervisor's confirmation, and the entries remain
retrieval references, not duplicate labels.

Report evidence register (page references recorded in the project review):

| Source | Location | Recorded evidence | Verification boundary |
| --- | --- | --- | --- |
| `Weekly_Progress_Report.pdf` | Page 5 | Candidate Member UIDs listed above | Report contents checked in the project review; independent retrieval reproduction pending |
| `Weekly_Progress_Report.pdf` | Pages 6–7 | Display grouping and continuum RMS interpretation for CASE1/CASE2 | Case-specific report interpretation; executable grouping and candidate-field mapping still need fixtures |
| `Weekly_Progress_Report.pdf` | Page 14 | Sky/rest handling and reference-frame limitations | Recorded method discussion, not blanket approval of reference-frame conversion or RMS comparison |

The continuum RMS interpretation applies to these two case filters. It does
not establish that the original internship task labels the basis, or that every
user sensitivity is continuum RMS. Reported answers and working assumptions
are evidence records, not approved calculation methods or formal duplication
labels. Never use expected project IDs or Member UIDs as search constraints to
make a positive retrieval test pass.

A pinned retrieval acceptance test now exists
([tests/live/test_case_retrieval.py](../../tests/live/test_case_retrieval.py)),
asserting only that each reported Member UID is retrieved (weak recall), with
the exact case search parameters transcribed above and the engineering search
radius documented in that file. It has been executed against the live
service and PASSED for both cases; see "Executed retrieval evidence" above
for the retrieved-row counts, dispositions and matched-row reasons. A pinned
grouping/count fixture and executable grouping/count assertions remain
pending until Q7 (CASE grouping/Member UID recall confirmation) closes.
Preserve the report's display grouping; do not silently reinterpret its entry
count as raw TAP rows or unique Members. Coordinate/frequency reference,
search radius/tolerance and the candidate-field mapping for the RMS filter
still need explicit implementation evidence. Formal duplicate/non-duplicate
labels remain unverified. Known report records are retained independently of
these outstanding checks.
