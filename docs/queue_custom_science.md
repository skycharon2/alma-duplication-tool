# Custom CSV complete science branches

The offline Custom backend now composes POS-MOSAIC, ANGULAR, continuum criteria
and spectral-line pair criteria independently for each inferred array. It reuses
existing Queue numerical rules and three-valued AND/OR. OT exports are development
fixtures, not runtime inputs. The browser/shared assessment entry is unchanged.

## Run

```sh
python -m alma_duplicate.cli.queue_custom_check \
  --queue-csv examples/queue-mosaic-ot/custom-engineering.csv \
  --proposed examples/queue-custom-check/proposed.json \
  --request examples/queue-custom-check/request.json \
  --output /path/to/new-report.json
```

The example is a synthetic numerical exercise, not an observing recommendation
or a validated science proposal. It produces separate 7-m and 12-m continuum matches under the selected
CSV shared-centre coverage model. The proposed single test
centre is supplied as a one-point Mosaic list. The scientific request uses the
existing validated request envelope with `geometry: MOSAIC` and CONTINUUM and/or
LINE intents. `--nominal-conversion PORTAL_SCRIPT_V1` retains the existing explicit
nominal-to-usable bandwidth choice if needed. No implicit choice is added.

Without `--request`, the existing position-only path remains unchanged. With it,
the proposed pointing JSON must include `source_name` and `setup_id` matching the
validated scientific request. It must also retain confirmed fixed ICRS and list
completeness. `sensitivity_basis: PER_POINTING` declares that the supplied proposed
RMS values apply per pointing. Missing or combined-image basis leaves RMS criteria
unresolved while independent frequency, resolution and position evidence remains.
This is spatial sensitivity meaning, separate from the request's spectral
AGGREGATE/SMOOTHED basis. Nonuniform per-pointing sensitivities are not supported.

Existing output is never overwritten. Exit 0 means a report was generated;
UNKNOWN and negative candidate branches are normal results. Search options are
validated as part of the input contract but no sky query or search prefilter runs.

## Branch composition

For CONTINUUM, AND POS-MOSAIC, ANGULAR, CONT-SETUP, CONT-FREQ and CONT-RMS within
one candidate/array. For LINE, AND POS-MOSAIC, ANGULAR, LINE-FDM, LINE-COVERAGE,
LINE-RESOLUTION-COMPATIBILITY and LINE-RMS within one proposed-window/candidate-SPW
pair; OR complete pairs according to existing Queue LINE semantics. Incomplete
window/SPW enumeration retains an unknown alternative. No condition crosses SPWs.

Then OR the complete array branch results separately for each intent:

- TRUE in either array wins even if the other array is UNKNOWN.
- FALSE in every array gives FALSE for that candidate/intent.
- Otherwise the result is UNKNOWN.

A known failing frequency or RMS criterion can make a branch FALSE even if its
position is UNKNOWN. The same named rule uses the same three-valued logic as
Single Pointing. Criteria from different arrays cannot be combined into a pass.
Both branches remain in the report, with `matching_arrays_by_intent` showing which
complete branches passed. CONTINUUM and LINE are not merged into an invented
cross-intent verdict. Array inference failure emits an indeterminate intent result.

## Model scope

This increment implements the project workflow requested on 2026-11-02: reuse
Single Pointing scientific calculations for Custom and OR complete array paths.
It retains `QUEUE_CUSTOM_EXPLICIT_CSV_2` and reports `model_status: PROVISIONAL`.
No new supervisor sign-off or independently measured array ownership is claimed.

The shared criterion schema uses APPROVED to enable the selected calculation
inside this explicitly adopted model, with this document as its scope reference.
This does not change the provisional status of the CSV geometry/association
conventions. Consumers must display the model scope alongside CRITERIA_MET; it
means all model criteria passed, not an authoritative duplicate determination.
Legacy Single Pointing method identities, numerical formulas and gates are kept.
The new Custom method pair is accepted only by explicit `mosaic=True` calls.

The strict CSV grouping is re-used. All source rows in a candidate must have
identical typed spectral and requested-performance operands. One representative
physical row supplies those operands; its original row ID, snapshot and SPW IDs
remain attached to line pairs. The group retains all original pointing rows.
No averaging, cross-setup union or combining duplicate rows into additional depth
occurs. Array scalar metadata follows the existing row-hypothesis model, not an
assertion of independent array-specific measured sensitivity or resolution.

Custom candidate sensitivity is interpreted as the requested per-pointing RMS.
The same Queue continuum bandwidth conversion and line spectral/angular scaling
are reused; no spatial Mosaic-overlap gain is introduced. The OT Custom sensitivity
meaning is described in the [official Mosaic guidance](https://help.almascience.org/kb/articles/how-do-i-set-up-a-mosaic-in-the-ot).
Rectangle combined-image sensitivity remains outside this Custom-only adapter.

Velocity, convention, sky/rest flags, spectral intervals, usable bandwidth and
mode classification come unchanged from the shared Queue parser/normalization
and rules. No second Doppler conversion or new reference-frame transformation
is performed. Existing frame evidence and limitations remain in the report;
Mosaic integration does not certify previously unverified frame alignment.

Under the user-selected v2 CSV approximation, mixed-array branches share the
CSV centres and independently compute the 7-m and 12-m beam radii. No external
grid is required. A point may be inside the larger 7-m beam while outside the
known 12-m coverage; a complete passing 7-m branch then returns a 7-m match.
Only arrays present in the existing inference are constructed. Unobserved
candidate coverage cannot establish a negative position result; other definitively
failing scientific conditions can still establish a negative branch. There is no
search-wide absence claim. Rectangle, moving sources, spectral-scan expansion and
reserved LINE input contracts are outside this increment.

## Validation

Integration tests cover both-array matches and a passing 7-m branch with unknown
12-m coverage, definite
science failure with unknown geometry, sensitivity-basis ambiguity, no duplicate
RMS gain, target/setup binding, source-context checks, complete-array OR, same-SPW
line aggregation, velocity convention reuse without double shifts, unchanged
legacy scope, enumeration uncertainty, resource limits and CLI JSON/overwrite
behavior. The CLI engineering example exercises the complete pipeline without OT.

The science report schema is `queue_custom_csv_science_2`; the numerical
science formulas and complete-branch OR are unchanged by the v2 point mapping.
