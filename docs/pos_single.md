# Queue POS-SINGLE, method queue_pos_single_1

This provisional method evaluates whether a proposed fixed single pointing lies
within the candidate's half-power beam. It does not evaluate duplication as a
whole. It consumes the typed `QUEUE_PORTAL_CANDIDATE_1` spatial evidence produced
when `--queue-candidate-beam` is selected; it does not parse CSV or query services.

## Contract

- Radius: one half of `1.13 c / (candidate frequency × candidate diameter)`.
  Only the candidate radius is used; proposed frequency cannot alter it.
- Scope: the existing Queue profile's supported single-field geometry and main
  array evidence. Archive, unsupported geometry, unresolved array, missing
  center and unselected profile produce an insufficient-information result.
- Frequency: positive `Ref.Frequency`, otherwise the existing zero-reference
  regular sky-SPW bandwidth-weighted fallback. This choice applies to beam
  geometry only; it does not select a CONT-FREQ comparison frequency.
- Coordinates: preserve the portal equatorial-frame convention and spherical
  east/north offset interpretation, including their limitations and source
  reasons. This is not a claim that J2000 equals measured ICRS.
- Let d be separation and r the candidate radius, both in degrees. When
  `abs(d-r) <= 1e-10`, return no outcome with `SPATIAL_BOUNDARY_TOLERANCE`.
  Otherwise d < r is SATISFIED, d > r is NOT_SATISFIED. The tolerance is a
  numerical guard, not an angular uncertainty estimate or policy approval.
- `candidate_coverage` supplies numeric evidence and blockers to both search
  and criterion. The criterion never reads INSIDE/OUTSIDE or row disposition.
- `CriterionResult` includes separation, radius, candidate frequency, diameter,
  tolerance, profile, field provenance, reasons and source references. Approval
  stays PROVISIONAL and formal aggregation eligibility stays false.

## Execution and audit

Evaluation version 2 runs CONT-SETUP once per request, then ANGULAR and
POS-SINGLE for every retained context, including those hidden by result_limit.
Excluded rows remain in `sources.*.rows`; they do not receive context criteria.
With the same Queue method used for filtering, known outside rows are excluded
before rule orchestration. Direct rule tests therefore cover negative outcomes.

`sources.*.filter_summary` is derived at serialization time from existing rows
and filters. It reports processed, retained and excluded row counts plus outcome
counts per predicate/stage. Predicate failure counts overlap and must not be
summed as excluded rows. The scope excludes rows never returned by the server.
Empty/failed/unprovided sources retain their source status: a zero count does
not imply a complete search. Report version 1 gains additive fields; the changed
criterion set is identified by evaluation_version 2.

## Offline replay

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/single_point/request.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --queue-candidate-beam --output reports/queue-pos-single-local.json
```

NGC6240's fixed real Queue row is used with the existing hypothetical complete
request. Expected first POS-SINGLE: SATISFIED, separation approximately zero,
radius approximately 8.60110728557 arcsec. All 13 retained contexts are evaluated
while one is displayed. Unsupported retained contexts remain unresolved.
The fixture hash and source snapshot remain in the report. This is an offline
criterion replay, not live dual-source retrieval or a confirmed duplicate label.
Historical candidate-beam evidence reports remain historical evaluation v1 files.
CASE1/CASE2 retrieval acceptance is unchanged and separate from this exercise.

## Narrow scientific confirmation still open

Review only this method's candidate-side convention, frame/offset interpretation,
frequency fallback scope and boundary guard. A reply can inform a future
versioned method; no approval is inferred here. ANGULAR field semantics and Q3
frequency choice are not closed by this change. No private correspondence is
included in the repository.

Sources: [captured profile and source checksums](evidence/official_sources.md#queue-position-profile),
[ALMA duplication portal](https://almascience.eso.org/proposing/duplications).
The portal explicitly calls the script user-contributed, provided as-is and not
supported by the ARCs; source availability is not formal scientific approval.
