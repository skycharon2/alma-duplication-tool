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

The fixed numerical method is `primary_beam_1`:

- FWHM in radians = `1.13 * 299792458 / (frequency_GHz * 1e9 * diameter_m)`.
- Half-power radius = FWHM / 2. The helper returns full width in degrees.
- The frequency is ONLY the validated request's independent representative SKY
  frequency. No window-center averaging, RMS-frequency fallback or rest-frequency
  conversion is performed. A missing/REST value leaves selection unevaluated.
- This is an explicit user-frequency approximation for candidate selection. A
  SKY value with unknown frequency frame is allowed under this convention; it
  does not establish cross-source reference compatibility or policy approval.
- Archive supports exact `12-m` and `7-m` array labels on explicitly non-mosaic
  rows. Detailed/mixed labels and TP are unresolved/unsupported.
- Queue requires `PositionInterpretation.antenna_diameter_m` explicitly set to
  7 or 12, with the interpretation's evidence reference. `use_7m` is not taken to
  identify a unique array. Offsets, mosaics, TP and SPS retain existing limits.

Both sources require context-specific ICRS/FIXED position evidence. Missing
interpretations remain visible; a successful beam calculation alone is not an
available position check. Archive diameter comes from its exact array label;
the optional interpretation diameter applies only to Queue.

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
