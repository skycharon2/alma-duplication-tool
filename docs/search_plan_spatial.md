# Search plans and minimal spatial adaptation

## Strategy selection

An explicit `beam_decision_ref` enables [coordinate retrieval and formula beam
selection](primary_beam_search.md). Without it, the existing region strategy
remains compatible. Region-specific descriptions below apply to that legacy
strategy; formula search uses centers and separate local beam checks.


Version 1 adds offline planning, source-bound spatial evidence and individual
predicate checks. It does not orchestrate a candidate search, call TAP, impose
result limits or evaluate duplication. Existing
[comparison contexts](comparison_contexts.md) remain unfiltered inputs.

## Search plan

`build_search_plan(validation, archive_science_only=False)` requires a valid
request with spatial search readiness, canonical ICRS position, explicit degree
radius and selected sources. It retains the validation result and SearchOptions.

| Input / operation | Archive | Queue |
| --- | --- | --- |
| Spatial scope | Planned server-side `s_region` intersection with an ICRS search circle | Planned local fixed-point cone selection, conditional on spatial evidence |
| Science-only restriction | Disabled by default; explicit planner argument adds it and records it | Not applicable |
| Explicit angular-resolution predicate | Planned local scalar check of `spatial_resolution` | Planned local scalar check of `Req. Ang. Res.` |
| Frequency predicate | Retained as SKIPPED with unresolved reference/matching semantics | Same |
| Spectral-resolution predicate | Retained as SKIPPED pending SPW association semantics | Same |
| Sensitivity predicate | Retained as SKIPPED pending RMS basis/association implementation | Same |
| Result limit | Retained for a future service; not converted to MAXREC | Retained, not applied |

The original single-sided operator is preserved. No synthetic lower/upper bound
is inserted into `ArchiveQuerySpec`. The generated Archive query is spatial-only
apart from the explicit science-only option. Requested observing parameters never
become implicit filters. In particular, continuum is not forced through narrow
frequency-overlap retrieval. Skipped filters mean a future result is broader than
the requested filters; they must be visible in its execution report.

`evaluate_angular_filter(plan, context, predicate_index)` evaluates one listed
local predicate, including the exact supplied operator. Indices address the
source plan's predicate tuple (including the spatial predicate at index 0).
It returns MATCH, NO_MATCH or NOT_EVALUATED. Missing/invalid values cannot cause
NO_MATCH. This compares a candidate scalar, not an approved angular-resolution
duplication condition; Archive estimated and Queue requested semantics remain
separate in source evidence. It does not validate retrieval completeness or
replace query binding.

## Binding existing queries to a plan

`bind_archive_query(plan, result)` checks current-builder normalized parameters,
COUNT ADQL and retrieval ADQL with its recorded projection. An extra hidden
project filter, changed cone or additional prefilter yields MISMATCH. A source
not selected by the plan yields SOURCE_NOT_SELECTED.

This is exact current-builder provenance matching, not arbitrary ADQL parsing
or a proof about a remote server's behavior. Legacy/external equivalent SQL may
be rejected. MATCHED does not mean COMPLETE: a matching overflow result remains
incomplete. The future service must check both binding and source status before
using a result. `evaluate_spatial` enforces Archive binding before a local check.

A Queue file is not a request-specific query. Its checksum, dates, source URL,
parser and raw-row identities remain attached to spatial evidence. The future
service must apply the planned local operation and report file/policy scope;
successful parsing does not prove all planned observations were covered.

## Spatial evidence

`adapt_spatial(context, source_record, interpretation=None)` retains the context
and original source result. They must refer to the same in-process source
objects; this is not a serialized-object reconstruction interface.
Center and footprint have separate states and neither overwrites the other.

Archive center normalization requires a finite scalar, live numeric FIELD
datatype and a supported declared angle unit (deg, rad or arcsec). Both original
and canonical ranges are checked; invalid coordinates retain their raw evidence.
Units missing from s_ra/s_dec are not borrowed from s_region. The center's frame
remains UNKNOWN without an explicit interpretation.

The footprint parser supports only `CIRCLE ICRS ra dec radius`, with degree
coordinates and a finite positive radius up to 180 degrees. Keywords are compared
case-insensitively because the live ALMA TAP service emits `Circle ICRS ...`
(verified 2026-09-11); the raw text is not rewritten. It is a deliberately
limited grammar, not a general STC-S parser. Other syntax, invalid data and missing
data have different statuses. Raw region text remains accessible through context.

Archive local circle-intersection checks are enabled only for explicitly
non-mosaic rows whose `antenna_arrays` value classifies as a dominant 12-m main
array or 7-m ACA family. `classify_array_type()` (method `array_family_1`) reads
the Pad:Antenna list: antennas on `T` pads are Total Power, `CM` antennas are
7-m, `DA`/`DV`/`PM` antennas elsewhere are 12-m; the dominant family must hold
at least 90% of all tokens, otherwise the row is MIXED. On 1,192 live rows
around CASE1/CASE2 (2026-09-11) every classified row agreed with the ALMA
Archive Query `array` label. Total Power, MIXED, missing and unrecognized values
remain unsupported and add an `ARRAY_FAMILY_*` reason. The legacy literal labels
`12-m`/`7-m`/`TP` are still read. The classification is attached to
`SpatialEvidence.array_classification` as application-derived evidence; it is
not an authoritative Archive field. A valid footprint can
remain usable even if the separate raw center is unavailable. If explicitly
ICRS centers disagree, both are retained with a reason; the planned region
predicate uses the footprint, not an invented merged center.

For Queue, target RA/Dec are retained independently of mosaic offset coordinates.
`Mos. Coord.` does not establish the target's frame. A source-row-scoped
`PositionInterpretation(context_id, frame, target_kind, decision_ref)` must
explicitly establish ICRS and FIXED before point-cone evaluation. It represents
caller-supplied evidence/interpretation, not automatic scientific approval.
No target type is inferred from zero coordinates or target name; a fixed source
at (0, 0) is valid if explicitly established. Unknown interpretation remains
unresolved and must not exclude the row.

Nonzero offsets outside the existing parser's recorded zero tolerance are not
applied. Tiny offsets inside that tolerance are retained with a reason. Custom
pointings, mosaics, TP and SPS remain unsupported for this first local selector.
Nominal single-field classification alone is insufficient to bypass these checks.
No primary-beam radius or HPBW is inferred from the search radius.

## Individual spatial selection

`evaluate_spatial(plan, evidence)` returns INSIDE, OUTSIDE or NOT_EVALUATED:

- Archive: angular center separation compared with the sum of search-circle and
  supported footprint radii.
- Queue: separation from an explicitly interpreted fixed point compared with
  the search radius.
- Unsupported, missing or unresolved evidence: NOT_EVALUATED, with reasons.

The spherical method uses atan2(cross-product norm, dot product), including RA
wraparound and poles. A 1e-10 degree numerical boundary band returns NOT_EVALUATED
rather than a definite exclusion. This is a numerical safeguard, not a policy
tolerance. Returned separation, threshold and method version are evidence of
that individual check.

The plan still says NOT_EXECUTED because no complete search was orchestrated.
All individual outputs say `assessment=NOT_EVALUATED`; INSIDE does not mean
duplicate and OUTSIDE does not establish absence in either archive as a whole.
The future service must retain unevaluated cases or report their omitted scope,
record predicates actually executed and any truncation, and show both sources
independently. A single global success Boolean is insufficient.

## Offline verification and next step

Run:

```bash
python -m pytest -q tests/integration/test_search_plan_spatial.py
python examples/plan_candidate_search.py
```

Tests cover planning, hidden query constraints, single-sided operators, source
selection, missing units, malformed regions, coordinate boundaries, separate
centers/footprints, Queue interpretation, unsupported geometries, poles and
wraparound. They use synthetic/local fixtures, not independently verified CASE
retrieval or approved duplicate labels.

The [candidate-search service](candidate_search.md) now orchestrates these plans
and individual checks and owns execution/completeness reporting. SearchOptions
predicates remain distinct from formal criteria. The
[next-delivery checklist](README.md#next-delivery) covers CASE retrieval verification.
