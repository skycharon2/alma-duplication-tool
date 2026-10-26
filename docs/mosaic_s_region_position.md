# Mosaic position assessment using Archive s_region

## Project decision and scope

On 2026-10-26 the project supervisor confirmed using each Archive candidate's
`s_region` as the other observation's half-power coverage for Mosaic position
assessment. This is the adopted project policy, not a claim that the footprint
has been proven identical to a reconstructed primary-beam union for all data.

The standalone `assess_region_position` function accepts the existing imported
proposal dictionary, one region string and a candidate/context identity. It does
not perform discovery, downloads, array acquisition or listobs reconstruction.
It does not combine regions from different candidates. Upstream metadata identity
binding remains the caller's responsibility. Other duplication criteria are not
evaluated by this function. The main assessment entry now uses this policy by default.

## Supported geometry

- `Circle ICRS ra dec radius`, with all angles in degrees and radius in (0,90).
- `Polygon ICRS ra1 dec1 ...`, with 3–512 distinct vertices contained within a
  10-degree cap around their vector mean. One repeated closing vertex is allowed.
- The polygon convention is explicitly the bounded small interior independent of
  vertex order. This supports the captured ALMA footprints; it is not a complete
  STC-S interpreter for oriented complements, large regions or compound operators.
- Edges follow minor great-circle arcs. A gnomonic projection preserves those
  edges for containment; boundary distance is evaluated on the sphere. The
  representation handles RA wrap and polar regions without a planar RA/Dec test.
- Self-intersections, touching nonadjacent edges, overlapping edges, degenerate
  polygons, nonfinite coordinates and unsupported syntax produce UNKNOWN.

Compound regions, holes, explicit reference-position tokens, non-ICRS frames and
larger polygons are not implemented. They are never silently reduced to one part.
The STC-S spelling is case-insensitive. Longitude 360 is accepted as equivalent to 0.

The great-circle edge convention is described in the IVOA geometry documentation:
https://ivoa.net/documents/ADQL/20230418/PR-ADQL-2.1-20230418.html

## Decision and evidence

Each proposed pointing receives INSIDE, OUTSIDE, BOUNDARY or UNKNOWN. The default
numerical boundary tolerance is 0.001 arcsec, explicitly recorded; this is not an
estimate of Archive astrometric accuracy. It can be set within (0,1] arcsec.

Let N be the supplied point count, L the definite inside count and U the sum of
inside, boundary and unknown counts. For a confirmed complete fixed ICRS proposal:

- 2L > N: SATISFIED.
- 2U <= N: NOT_SATISFIED.
- Otherwise: UNKNOWN.

Thus exactly half inside, with the remainder definitely outside, is NOT_SATISFIED.
Boundary uncertainty matters only if it could change the strict-majority result.
A missing/invalid region makes all point classifications UNKNOWN. Incomplete or
unconfirmed-frame proposals cannot yield a definitive outcome. Proposal IDs must
be unique; repeated coordinates with distinct IDs are retained as imported entries.
Input is limited to 10,000 proposed points and 100,000 region characters.

An effective candidate region suffices for a negative position result under this
policy; Archive execution completeness is no longer a prerequisite for this module.
The report preserves candidate identity, raw region, region hash, per-point results,
counts, fraction bounds, tolerance and the adopted policy identifier.

## Reproduce

```sh
python -m pytest -q tests/unit/test_mosaic_region_position.py
```

A direct call with already imported OT points:

```python
from alma_duplicate.mosaic_region_position import assess_region_position

result = assess_region_position(
    proposed,
    archive_row['s_region'],
    candidate_id=context_id,
)
```

Tests cover captured CASE2 polygons and the actual OT export, captured LMC/RX
vertices, circles, concavity, RA wrap, polar polygons, invalid regions, candidate
isolation, proposal validation and strict-majority bounds. Astropy directional
coordinates independently exercise circle boundaries and a high-latitude
minor-great-circle edge. No live data or local download cache is required.

## Main backend integration

`assess_observation` routes fixed Archive-only Mosaic requests through
`run_mosaic_backend`, whose default coverage model is `S_REGION`:

1. Discover candidate member/target pairs using the imported proposal pointings.
2. Fetch normal Archive metadata for each pair and check response identity.
3. Build the existing comparison contexts. Evaluate each context using its own
   raw `s_region`; never borrow or merge a different context's region.
4. Combine POS-MOSAIC with the existing angular-resolution, continuum or spectral
   line rules. Those rules continue to use Archive metadata.

No auxiliary package, listobs, reconstructed execution, antenna diameter or
execution-completeness readiness is required for this position path. A satisfied
position criterion alone is not a joint duplication verdict. Missing or unsupported
regions remain unknown. Source failures and incomplete metadata remain explicit.

Reports use `archive_mosaic_backend_2`, `coverage_source=ARCHIVE_S_REGION` and
`preparation.status=NOT_REQUIRED`. They retain the source metadata, per-context
region hash, point classifications and shared criterion/branch decisions.
`COMPLETED` describes processing, not a search-wide claim of non-duplication.
Discovery limits and recall uncertainty still apply; the existing discovery plan
retains its historical recall-status identifier for saved-plan compatibility.

The CLI no longer requires `--mosaic-cache`. If supplied, it is unused.
`--mosaic-resume-preparation` reuses only a matching saved `discovery.json`; it
still fetches metadata and does not inspect or prepare packages. Historical
package resource options do not limit the new metadata-only path.

Historical reconstruction is retained through the explicit Python input
`coverage_model="RECONSTRUCTED"` for research replay and regression tests. It is
not an automatic fallback when an Archive region is missing. Low-level context
callers must pass `use_s_region=True` to select the new policy; the main backend
already does so.

## Integration validation

```sh
python -m pytest -q tests/unit/test_mosaic_region_position.py tests/integration/test_s_region_backend.py
```

The integration tests use captured CASE2 metadata and actual OT pointings through
`assess_observation`, for both continuum and line requests. They check positive
coverage, exactly half coverage, missing/unsupported regions, single-pointing
candidates, response identity mismatch, isolated candidate regions, and angular
or frequency failures despite positive position coverage. Package preparation and
readiness loaders are replaced with functions that fail if called. These are
reproducible offline tests, not a new live Archive acceptance run.
