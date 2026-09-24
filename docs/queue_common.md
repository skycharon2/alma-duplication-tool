# Queue common rules: single-array increment

Opt-in `--queue-common` (Python: `evaluate_candidate_search(..., queue_common=True)`)
selects project-adopted `queue_pos_single_3` and `queue_angular_factor_4` for Queue
contexts. [Decision and source hashes](evidence/queue_common_decision_2026-09-24.md#common-rules)
define authority and limitations. Archive behavior and default legacy Queue
behavior remain unchanged. Existing report v4/evaluation v5 structures suffice;
the per-criterion method versions identify which path actually ran.

## Supported scope

- Proposed fixed celestial, single-point request with a position.
- Coherent Queue row with SINGLE_FIELD geometry and regular SPWs.
- Explicit negative auxiliary flags resolve main 12 m; row-bound declarations can resolve exclusive 7 m (D=7 m) or exclusive TP (D=12 m).
- Supported Portal equatorial/offset interpretation and available candidate centre.

The opt-in is a declared fixed-celestial workflow, not source-native target-kind
telemetry. Zero-coordinate placeholders remain unresolved. Unknown/conflicting
interpretations, unsupported frames, non-single geometry and scans produce no
condition outcome, never definite false. Both auxiliary flags true are mixed and
remain unsupported. A single positive flag does not prove the main array absent.

### Explicit array declarations, without a sidecar

Use repeatable `--queue-array ROW_ID=7M_ONLY` or `ROW_ID=TP_ONLY`, together with
`--queue-array-decision-ref REF`. ROW_ID is the full snapshot-qualified
`source_row_id` from criterion details. REF must identify the owner's review or
source establishing exclusive array membership. Never invent it from the flags.
The declaration is an explicit interpretation, not a recovered CSV field.

7M_ONLY requires (Use 7-m?, Use TP?)=(True, False); TP_ONLY requires (False, True).
Mixed (True, True) is always blocked, including when a declaration is supplied.
Absent declarations for either single-positive combination remain unresolved.
Invalid/duplicate/non-retained row IDs fail the run rather than being ignored.
Declarations only affect common evaluation, not candidate retrieval or mode.

Python callers pass `queue_array_declarations=(QueueArrayDeclaration(row_id,
"7M_ONLY", decision_ref),)` to `evaluate_candidate_search(..., queue_common=True)`.
The type lives in `alma_duplicate.rules.queue_common`. Reports preserve scope,
diameter, row/snapshot identity and the declaration reference in both conditions.


## Conditions

POS-SINGLE uses the candidate beam, not request frequency or request beam. Full
FWHM=1.13*c/(candidate_frequency*D), with radius equal to half the FWHM. Positive Queue
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
