# Queue common rules: first main-array increment

Opt-in `--queue-common` (Python: `evaluate_candidate_search(..., queue_common=True)`)
selects project-adopted `queue_pos_single_4` and `queue_angular_factor_5` for Queue
contexts. [Decision and source hashes](evidence/queue_common_decision_2026-09-24.md#source-evidence-only-correction)
define authority and limitations. Archive behavior and default legacy Queue
behavior remain unchanged. Existing report v4/evaluation v5 structures suffice;
the per-criterion method versions identify which path actually ran.

## Supported scope

- Proposed fixed celestial, single-point request with a position.
- Coherent Queue row with SINGLE_FIELD geometry and regular SPWs.
- Explicit negative Use 7-m?/Use TP? flags, resolving 12 m in this adopted profile.
- Supported Portal equatorial/offset interpretation and available candidate centre.

The opt-in is a declared fixed-celestial workflow, not source-native target-kind
telemetry. Zero-coordinate placeholders remain unresolved. Unknown/conflicting
interpretations, unsupported frames, non-single geometry, scans, TP and mixed/
ambiguous array requirements produce no condition outcome, never definite false.
Uniquely source-bound 7-m interpretation is a later extension, not inferred from
Use 7-m?=True. No new interpretation sidecar is introduced in this small step.

## Conditions

POS-SINGLE uses the candidate beam, not request frequency or request beam. Full
FWHM=1.13*c/(candidate_frequency*12m), with half that radius. Positive Queue
Ref.Frequency is preferred; existing zero-sentinel sky-SPW weighted frequency is
reused only for this geometry. Existing spherical offset transport is reused.
The computed float64 separation <= computed radius is inclusive; there is no
new equality tolerance. Inverse coordinate construction can introduce rounding,
so boundary tests isolate the comparison and separately verify real spherical
inside/outside cases. Historical queue_pos_single_1 keeps its unknown boundary
band and remains provisional.

ANGULAR compares requested Queue and proposal arcsec with the existing exact
canonical symmetric max/min <=2 method. Missing/invalid units or values remain
unresolved. Candidate beam frequency is not an ANGULAR dependency; missing
proposal angular resolution does not erase a valid position condition. Both
methods share scope gates so unsupported candidates cannot acquire a formal
common-rule failure from an otherwise computable scalar ratio.

## Report and search boundaries

Both criteria retain physical row ID, snapshot hash, project decision reference,
frame/target interpretation and array scope. Position additionally exposes both
centres, spherical separation, beam frequency and source, diameter and source,
full FWHM, radius and boundary numeric method. Angular retains raw-field role,
QUEUE_REQUESTED semantics and exact factor details.

The new option does not change candidate search, filters or retention. Without
--queue-candidate-beam, default unresolved Queue spatial selection conservatively
retains rows: even a position-failing candidate can then have a reported condition.
This can yield many retained rows from a full snapshot. It is not proof of search
completeness. With the separate old --queue-candidate-beam retrieval profile,
excluded rows remain in the source/filter audit rather than context evaluations.
Display limits still do not truncate retained-context evaluation.

Continuum/LINE branches remain INDETERMINATE because their Queue source-specific
conditions/aggregation are not yet implemented. A failed common condition is
visible, but this increment does not enable a full Queue branch verdict or a
search-wide no-duplicate assertion. Source failures remain explicit.

## Reproduce

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/single_point/request.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --queue-common --output reports/queue-common-fixture.json
```

Use a new output filename. The fixture has 13 retained/evaluated contexts and a
one-row display limit. It verifies ingestion/mapping, not a reviewed scientific
positive proposal. Independent synthetic tests verify the beam and angular
numbers, boundaries, scope and cross-context rejection.

```bash
python -m pytest tests/integration/test_queue_common.py \
  tests/integration/test_position_single.py \
  tests/integration/test_queue_candidate_beam.py -q
```

The existing mode evidence adapter remains independent of geometry and these
rule scopes. Queue continuum does not need mode inference; [roadmap](roadmap.md)
retains the main development order.

## Source evidence only correction

The former CLI array-declaration flags and Python QueueArrayDeclaration API have
been removed. Neither a row ID plus a reference string nor an externally supplied
diameter proves standalone ACA membership. Old invocation options fail explicitly;
no supplied declaration is silently ignored.

Current diagnostics:

| Source flags | Position diameter | Common-rule scope diagnostic |
| --- | --- | --- |
| Use 7-m? False, Use TP? False | 12 m | Supported normal profile, subject to other evidence |
| Use 7-m? True, Use TP? False | Unresolved | STANDALONE_ACA_EVIDENCE_UNAVAILABLE |
| Use TP? True, either 7-m flag | None in this method | TP_GEOMETRY_UNSUPPORTED |
| Missing/non-boolean array flags | Unresolved | QUEUE_ARRAY_FLAGS_UNRESOLVED |

The physical TP dish diameter is 12 m, but this does not make a TP component
eligible for the current interferometry method. Both common conditions retain
scope gates; this increment does not recover per-component resolution or RMS.

A future supported source adapter may recover authoritative standalone ACA
information. Until then, a positive Use 7-m? flag does not select 7 m. No sidecar
or manual per-row declaration is required. Queue continuum can proceed for the
supported scope independently of that provenance investigation.

Historical reports with queue_pos_single_3 / queue_angular_factor_4 retain their
original meanings; do not relabel them. Generate a new report with the current
methods. Reports generated without declarations have the same numerical scope,
with corrected diagnostics and new method references.
