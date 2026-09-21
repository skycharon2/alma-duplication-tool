# Confirmed Archive continuum increment

Baseline: `6b48b3b95f99d0333128b2e0c9f6cd06a9c51fce`.

The [confirmation record](evidence/supervisor_confirmation_2026-09-17.md) owns
approval scope. Request `intents` selects branches. CONT-SETUP executes once only
when CONTINUUM is selected; checking that intent does not satisfy the width test.
Each retained Archive candidate receives ANGULAR, POS-SINGLE, CONT-FREQ and
CONT-RMS. Its branch combines those four with the request-level CONT-SETUP.

## Offline CLI acceptance

From the repository root, after `python -m pip install -e .`:

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/confirmed_continuum/request.json \
  --archive-replay examples/confirmed_continuum/archive/manifest.json \
  --output reports/confirmed-continuum.json
```

Expected branch statuses in row order:

| Row | Difference from guide A | Continuum status |
| --- | --- | --- |
| 0 | Guide A values | CRITERIA_MET |
| 1 | Candidate aggregate RMS 0.21 mJy/beam | CRITERIA_NOT_MET |
| 2 | Candidate aggregate RMS missing | INDETERMINATE |
| 3 | Candidate centre outside candidate half-power beam | CRITERIA_NOT_MET |

The fixture has a deliberately broad synthetic footprint, so the outside-beam
candidate survives retrieval and receives a formal negative position result.
`result_limit=1` limits presentation only: all four retained contexts are assessed.
The exact request, response bytes, units, ADQL and response SHA-256 values are
versioned. Fixture identity is `SYNTHETIC_NUMERIC_ACCEPTANCE`, not a live capture.

Run the existing real-source replay independently:

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/dual_source/request.json \
  --archive-replay tests/fixtures/archive/ngc6240/manifest.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --queue-candidate-beam \
  --output reports/ngc6240-confirmed-rules.json
```

That request deliberately has no aggregate RMS; no positive continuum branch is
expected. Its real Archive positions/frequencies now exercise the new mappings.
This command is offline and does not verify current TAP availability.

## Report contract

JSON `report_version=2`, `evaluation_version=3` add
`context_evaluations[].branches`. Each branch contains its scope, required
criterion IDs, three-valued truth, status, reasons, version and confirmation ref.
The request-level setup result is referenced by criterion ID and not recomputed
for every row. Individual criteria preserve input values, units and semantics.
The continuum RMS diagnostic is candidate/proposed, not symmetric.

- An approved false conjunct makes the supported continuum branch false even
  with another unknown criterion. Provisional outcomes enter as UNKNOWN.
- Conflicting alternatives and unlinked Archive associations block a formal
  branch verdict; no most-favourable row is selected.
- Unsupported sources/geometries/ambiguous diameters remain INDETERMINATE.
- LINE intent currently yields `NOT_IMPLEMENTED`/UNKNOWN. Both intents give
  separate branch records. There is no mixed-branch verdict.
- Top-level `assessment=NOT_AGGREGATED` intentionally remains a search-wide
  boundary. A branch false never means the whole observation is non-duplicated.

Source metadata, failed/incomplete source states, query binding, retrieval radius,
filter exclusions and hidden candidate IDs remain visible. Excluded rows stay
in the source audit; they are not represented as evaluated criterion negatives.
Footprint query completeness applies only to the supplied footprint query. This
increment does not assert every candidate-side primary beam is contained in its
published footprint, nor reinterpret request-frequency formula retrieval as
complete coverage for the new candidate-frequency rule. Use the ordinary
footprint strategy for this acceptance and inspect the report's search scope.

## Validation commands

```bash
python -m pytest -q tests/integration/test_confirmed_continuum.py
python -m pytest -q
```

Regression coverage includes the guide positive, 1.3 and 2 inclusive thresholds,
strict setup-width legacy tests, distinct representative frequency versus SPW
mean, missing/incompatible units, ambiguous array majority, mosaic, RA wrap,
position boundary, conflicting evidence, source failures, display limits, exact
replay matching, and cross-SPW pairing reference rejection.
