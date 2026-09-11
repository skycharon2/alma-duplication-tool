# Coordinate retrieval and formula primary-beam selection

## Implemented opt-in strategy

Pass a nonempty `beam_decision_ref` to `build_search_plan` or `search_candidates`.
This selects the new formula strategy; omitting it retains the existing region
strategy and its query provenance. The reference identifies the caller's chosen
convention, not proof of supervisor approval. No formal duplication verdict is
produced. Plan version is 2 for this strategy; existing plans remain version 1.

Archive COUNT and retrieval use the same center-coordinate CONTAINS/POINT query.
`s_region` is still retrieved and preserved, but is not used for preselection or
local formula inclusion/exclusion. An invalid/missing/disagreeing region cannot
veto otherwise usable center evidence. The underlying query assumes the Archive
coordinate columns are ICRS degrees; local typed center checks still require FIELD
metadata and an explicit fixed/ICRS interpretation. An arbitrary TAP service with
other coordinate-column semantics is not supported by this query convention.

## Frequency, diameter and scope

The fixed numerical method is `primary_beam_2` (`primary_beam_1` plus the
`array_family_1` Archive diameter lookup; the beam formula is unchanged):

- FWHM in radians = `1.13 * 299792458 / (frequency_GHz * 1e9 * diameter_m)`.
- Half-power radius = FWHM / 2. The helper returns full width in degrees.
- The frequency is ONLY the validated request's independent representative SKY
  frequency. No window-center averaging, RMS-frequency fallback or rest-frequency
  conversion is performed. A missing/REST value leaves selection unevaluated.
- This is an explicit user-frequency approximation for candidate selection. A
  SKY value with unknown frequency frame is allowed under this convention; it
  does not establish cross-source reference compatibility or policy approval.
- Archive diameter comes from `classify_array_type()` (see
  [search/spatial](search_plan_spatial.md#spatial-evidence)) on explicitly
  non-mosaic rows: 12 m for a dominant main-array family, 7 m for a dominant
  ACA family. Total Power, MIXED, missing and unrecognized values stay
  unresolved/unsupported.
- Queue requires `PositionInterpretation.antenna_diameter_m` explicitly set to
  7 or 12, with the interpretation's evidence reference. `use_7m` is not taken to
  identify a unique array. Offsets, mosaics, TP and SPS retain existing limits.

Both sources require context-specific ICRS/FIXED position evidence. Missing
interpretations remain visible; a successful beam calculation alone is not an
available position check. Archive diameter comes from its classified array
family; the optional interpretation diameter applies only to Queue.

The retrieval radius is the larger of the user's radius and the 7-m half-power
radius at the selected frequency (plus the existing numerical boundary band),
capped at 180 degrees. This is a conservative upper bound ONLY for this common
frequency convention and supported 7/12-m single fields. It is not a bound for
mosaics, unknown geometries, other diameters or other frequency choices. Without
usable frequency, the user radius is retained and no automatic bound is claimed.
The original SearchOptions radius is never overwritten.

Queue is loaded in full and each available supported center is checked against
its computed beam. Thus supported rows outside the beam can be excluded and
unknown geometries remain auditable. Archive rows outside the actual retrieval
cone cannot be recovered by local retention. Source limitations explicitly say
this; TAP completeness and all-sky scientific completeness are separate.

## Audit and safety

Archive `retrieval_scope` is the server-reported center-cone predicate. `spatial`
is the separate local formula check. A local center outside the bound query's
scope is retained as unevaluated with a discrepancy reason. A center within the
query cone but outside its smaller beam is an ordinary local NO_MATCH, not a
server/region disagreement. The radius is not added to the beam radius during
local target-in-beam evaluation.

SpatialSelection retains separation, threshold, frequency, diameter, full width,
method version and decision reference. Raw source/context references and the
position interpretation remain in the existing evidence object. A boundary band
of 1e-10 degree yields NOT_EVALUATED rather than silently choosing equality.
Assessment stays NOT_EVALUATED; MATCHED_FILTERS is not a duplicate verdict.
Strict source ingestion, independent failures, skipped science filters and
post-processing display limits are unchanged.

## Usage

```python
plan = build_search_plan(validation, beam_decision_ref="your-documented-convention")
result = search_candidates(
    validation,
    archive_result=archive_result,  # must have been retrieved with this plan
    queue_result=queue_result,
    interpretations=position_interpretations,
    beam_decision_ref="your-documented-convention",
)
```

For a newly acquired Archive run, obtain the result using
`client.search(plan.for_source("ARCHIVE").archive_query)`, construct contexts with
`build_archive_contexts`, attach justified context-scoped position interpretations,
then pass that same result to the service. This does not repeat the network query.
Direct client injection also works, but without corresponding interpretations it
will deliberately retain rows as unevaluated. Do not fabricate frame/target
interpretations to turn an example green.

The offline example exposes the strategy:

```bash
python examples/search_candidates.py --beam-decision-ref user-frequency-review
```

It supplies no fabricated interpretations; unevaluated spatial results are
expected. `--live-archive` is a separate opt-in network operation. Synthetic
integration tests prove formula inclusion/exclusion and query binding without
claiming live CASE verification.

## Real-data applicability measurement

Two questions about this strategy's real-data applicability were previously
unmeasured (see `claude/next_rule_engineering_tasks_2026-09-10.md`): how
often the exact Archive `12-m`/`7-m` label resolves at all, and what that
looks like for the two recorded internship-task cases specifically.

[tests/live/test_case_beam_strategy_applicability.py](../tests/live/test_case_beam_strategy_applicability.py)
runs the formula strategy (no fabricated interpretations) against the real
Archive rows near CASE1/CASE2 and reports, per row, which reasons
accompanied the expected `FIXED_TARGET_AND_ICRS_INTERPRETATION_REQUIRED`
result -- in particular whether the diameter itself resolved. It is a small,
concrete sample, not a population estimate.

**Result of the 2026-09-10 run**: 0 of 336 CASE1 rows and 0 of 851 CASE2
rows (both within 10 arcsec of the reported position) resolved a diameter.
Every observed `antenna_arrays` value in both neighborhoods was either a
detailed pad:antenna listing (e.g. `A001:DA59 A002:DA49 ...`) or an ACA/TP
array listing (`J5xx:CMxx`, `T7xx:PMxx`) -- none was the exact string
`12-m` or `7-m`. `CENTER_UNAVAILABLE` also appeared on every row, which is
expected: without a supplied `PositionInterpretation`, the local adapter
correctly declines to treat `s_ra`/`s_dec` as a trusted fixed-ICRS center
(see "Audit and safety" above). The diameter-resolution result is
independent of that and is the one to read for this question. This is
evidence from two local neighborhoods, not a population estimate, but it is
a concrete zero, not merely "low" -- it is a strong signal to prioritize a
real `classify_array_type()` parser (pad-prefix based, per
`claude/next_rule_engineering_tasks_2026-09-10.md`) before this strategy is
relied on beyond hand-checked cases. Full output (retrieved-row counts, the
complete `antenna_arrays` label distribution, and the reason-count tables)
is recorded in `docs/duplication_rule_inputs.md` section 8 and in the raw
`pytest -s` transcript kept with the project's delivery notes.

[scripts/beam_array_label_census.py](../scripts/beam_array_label_census.py)
separately measures the Archive-wide share of `science_observation = 'T'`
rows whose `antenna_arrays` value is exactly `12-m`/`7-m` versus a detailed
or mixed label, split by `is_mosaic`. It writes a dated report under
`docs/evidence/`.

**Result of the 2026-09-10 census run**: across the full Archive population
of 443,998 `science_observation = 'T'` rows (13,058 distinct
`(antenna_arrays, is_mosaic)` groups; the query did not hit its row cap, so
this is a complete grouped count, not a truncated sample), **0%** of rows --
mosaic and non-mosaic alike -- had an `antenna_arrays` value exactly equal
to `12-m` or `7-m`; every row classified as `OTHER_DETAILED_OR_MIXED`
(a detailed pad:antenna listing or an ACA/TP-only listing). This confirms
the CASE1/CASE2 local-neighborhood finding above (0 of 336, 0 of 851)
generalizes Archive-wide: it is not an artifact of those two coordinates.
The full report, including sample raw label values per classification
bucket, is at `docs/evidence/primary_beam_array_label_census_2026-09-10.md`.
Neither script approves or changes this strategy; both produce measurement
evidence for a human decision, consistent with the `application-derived`
label already used for `antenna_arrays` classification. Given a confirmed
0% Archive-wide match, a real `classify_array_type()` parser was a
prerequisite for the Archive side of this strategy to resolve a diameter on
real rows at all. That parser now exists (`array_family_1`, 2026-09-11); the
measurements above describe the earlier exact-label lookup.
