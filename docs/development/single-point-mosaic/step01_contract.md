# Single Pointing → Archive Mosaic: Step 01 contract and baseline

Status: development contract; the new discovery and formal position path are
not implemented by this step. No production behavior changes.

## Scientific decision

The project supervisor's instruction, relayed by the user, adopts Archive
`s_region` as the other observation's half-power coverage. This extends the
project interpretation documented in [Mosaic region position](../../mosaic_s_region_position.md)
to a proposed fixed ICRS Single Pointing. It is not a claim that Archive metadata
universally proves an exact reconstructed half-power footprint.

The user-supplied Appendix A distinguishes the proposed geometry: a single-field
proposal uses point containment; a Mosaic proposal uses the strict >50% rule.
A Mosaic candidate does not turn a Single Pointing proposal into a Mosaic.
Position satisfaction alone is not duplication: existing angular resolution and
LINE/CONTINUUM conditions still apply. Solar exclusions and unsupported scientific
scopes remain in force.

## Target position contract (future step)

- Apply only to identified Archive Mosaic candidates and fixed Single Pointing
  proposals. Preserve ordinary Archive single-field and Queue CSV behavior.
- Use the candidate context's own `s_region`, never a central-beam approximation
  or a footprint borrowed from another Member, target or spectral context.
- INSIDE or BOUNDARY maps to SATISFIED; OUTSIDE to NOT_SATISFIED;
  missing, invalid or unsupported region maps to unknown.
- Reuse spherical geometry from the existing region module, not the Mosaic
  strict-majority aggregate. Its BOUNDARY classification uses a numerical
  tolerance (default 0.001 arcsec), so inclusive treatment includes that tolerance
  band. Record it in evidence; it is not an astrometric uncertainty estimate.
- Circles and supported bounded polygons include RA-wrap and polar handling.
  Compound/union regions currently remain unknown in their entirety; do not
  silently keep only the first component. Supporting them requires separate tests.
- Preserve raw region, candidate identity, region hash, classification, tolerance
  and a distinct versioned method/decision reference in formal output.

## Discovery and reporting contract (future steps)

Add coverage-based discovery alongside existing Single Pointing retrieval. A
Mosaic center outside the existing cone must not hide a region containing the
proposal. Preserve Member/target/component identity when combining results:
project identity alone is not a deduplication key. Do not merge independent
candidate footprints to obtain a positive result.

A failed, truncated or incomplete supplementary query must remain visible in
search completeness. A candidate-specific negative result is not a search-wide
absence claim. Boundary retrieval must be checked against TAP predicate behavior;
local inclusive geometry cannot recover a candidate omitted by server discovery.

LINE and CONTINUUM must share this position evidence. Reports and Explore must
identify the Mosaic coverage source and render the corresponding region, without
presenting a central circular beam as its formal footprint. Queue adaptation,
Mosaic proposal aggregation and numerical spectral criteria are outside scope.

## Step 01 evidence

[Fixed cases](../../../tests/fixtures/single_point_archive_mosaic/position_cases.json)
are explicitly synthetic engineering fixtures, not live Archive captures.
They include inside/outside/boundary, a polygon crossing RA zero with a distant
metadata center, polar geometry, missing/invalid coverage and unsupported union.
`future_position_outcome` records target expectations, not passing implementation
acceptance. The distant-center case is a discovery acceptance input, not proof
that discovery currently retrieves it.

[Baseline tests](../../../tests/integration/test_single_point_archive_mosaic_baseline.py)
exercise the existing spherical classifications and pin the current formal
Mosaic rejection for every case. They do not assert future outcomes against a
new evaluator, use skipped tests, or certify an end-to-end query.

When Step 03 implements the new position method, replace these legacy rejection
assertions with formal outcome assertions using the same cases. Keep unknown
geometry distinct from identified Mosaic. Add candidate isolation, LINE/CONTINUUM,
ordinary Archive single-field and Queue regressions. Step 02 separately needs a
recorded-query discovery test with distant-center coverage and failure/truncation.

Run offline:

```sh
python -m pytest -q tests/integration/test_single_point_archive_mosaic_baseline.py
```
