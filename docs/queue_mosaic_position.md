# Queue Mosaic position backend: explicit array coverage

This second increment adds `assess_queue_mosaic_position` and an offline CLI.
It consumes the [reconstruction report](queue_mosaic_reconstruction.md), a fixed
ICRS proposed pointing list, and explicit per-array coverage bindings. It is not
yet connected to the shared evaluator or browser. It does not emit a complete
duplication verdict.

## Run

```sh
python -m alma_duplicate.cli.queue_mosaic_position \
  --reconstruction reconstruction.json \
  --candidate-id 'queue-mosaic:REPLACE_WITH_REPORT_ID' \
  --proposed proposed.json \
  --coverage coverage.json \
  --output new-position.json
```

`proposed.json` is the output of `cli.proposed_mosaic` import. Fixed ICRS must be
confirmed. Without confirmed proposed completeness, the outcome is UNKNOWN.
The supplied proposed list is evaluated geometrically against each candidate
array; its array label is retained, but this interface does not authorize
cross-array scientific comparison or derive another proposed array's grid.

`coverage.json` is an array of objects with this shape (replace placeholders):

```json
[{
  "candidate_id": "queue-mosaic:REPLACE_WITH_REPORT_ID",
  "snapshot_sha256": "REPLACE_WITH_SNAPSHOT_HASH",
  "source_row_ids": ["REPLACE_WITH_EACH_CANDIDATE_SOURCE_ROW_ID"],
  "diameter_m": 12,
  "frequency_ghz": 100,
  "frequency_evidence_ref": "path/to/verified-frequency-evidence",
  "points": [{"id": "p1", "frame": "ICRS", "ra_deg": 10, "dec_deg": 0}],
  "geometry_evidence_ref": "path/to/verified-array-pointing-evidence",
  "association_confirmed": true,
  "complete": true
}]
```

This is an interface example, not verified coverage for an actual observation.
Supply one binding per known inferred array. Each binding must identify exactly
all source rows of the selected candidate and the same snapshot. A binding may
contain only part of its coverage (`complete: false`). The two booleans are
caller assertions recorded as evidence, not independent authentication. Evidence
references are recorded, not fetched or verified. Confirming association means
the supplied points belong to this candidate, setup and diameter; completeness
means the supplied list exhausts that array's candidate coverage.

The existing array inference remains authoritative. Unsupported diameters,
duplicate array bindings, invalid coordinates/frequencies and foreign source
identities are rejected. Empty coverage input `[]` gives UNKNOWN per inferred
array. TP is ignored as in reconstruction. Existing output files are protected;
exit 0 means a report was produced, not a positive duplication finding.

## Calculation and uncertainty

Each array uses its own supplied centres and frequency. Circular beam radius is
half of `1.13 * c / (frequency * diameter)` in angular units. Separation uses
spherical great-circle distance, including RA wrap and poles. No screen-axis
interpretation enters this calculation.

For every proposed point, the report records each candidate centre's separation,
signed distance from the beam boundary, and relation. Membership is the union of
that array's disks; overlapping disks never count a proposed point twice.
The fixed default numerical boundary tolerance is 0.001 arcsec. It is not a
model of astrometric uncertainty.

A strict majority (>50%) of proposed pointings must be covered. The report gives
lower and upper covered counts and fractions, with outcomes SATISFIED,
NOT_SATISFIED or UNKNOWN. Boundary points may or may not be covered. With partial
candidate coverage, known inside points can establish a positive result, while
unmatched points remain unknown. Unconfirmed association makes every membership
unknown. Unconfirmed proposed completeness always makes the outcome UNKNOWN.

7-m and 12-m results remain separate. The module does not pool their coverage or
OR their position outcomes into a duplication verdict. Complete scientific
branches still require spectral, resolution, sensitivity and other applicable
criteria before aggregation. Computation is capped at one million point pairs.

## Remaining integration

Diagnostic CSV centres are not automatically promoted to verified coverage.
Custom point ownership and OT offset parity require supporting evidence;
Rectangle grid anchoring, PA sign and sampling, and the independently generated
ACA grid remain unresolved. Verified absolute OT exports can supply bindings
for either geometry without guessing those grids. The [Custom OT binding adapter](queue_mosaic_binding.md) now produces these
bindings from CSV and a source-bound absolute OT export. One controlled seven-point offset case has passed native OT coordinate parity.
Broader geometry validation and complete scientific branch integration remain pending.

Tests use synthetic bindings over the reduced Queue fixture. They establish
engineering behavior, not OT geometry parity or scientific acceptance of an
actual Queue target.
