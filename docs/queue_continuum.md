# Queue continuum contract

Opt in with `--queue-continuum`; it implies `--queue-common`. Only selected
CONTINUUM intent receives the new branch. Archive methods and Queue LINE are
unchanged. The [decision](evidence/queue_row_continuum_decision_2026-09-24.md) owns
approval and source-interpretation boundaries.

Five conditions are combined within one retained coherent context: POS-SINGLE,
ANGULAR, request CONT-SETUP, CONT-FREQ and CONT-RMS. Common scope is checked before
aggregation: unsupported geometry or invalid standalone evidence cannot
become a negative branch merely because a numerical condition fails.
Within supported scope, false AND unknown is false; no false and an unknown
is unknown. All five approved conditions must pass for CRITERIA_MET.

## Evidence and arithmetic

CONT-FREQ uses only a positive Ref.Frequency and declared representative SKY
frequency, with max/min <= 1.3. The position-only SPW fallback is not used here.

CONT-RMS uses one row's reference sensitivity and width, and every regular SPW
in its setup. The existing nominal-to-usable mapping is reused with its exact
version. Intervals are constructed from canonical sky centre and usable width,
merged using rational arithmetic, and summed in MHz. Unknown widths prevent a
partial aggregate calculation. Overlapping, identical and touching windows
retain their identities but contribute only their union to total bandwidth.

    sigma_aggregate = sigma_reference * sqrt(B_reference / B_union)
    sigma_aggregate <= 2 * sigma_proposal

The comparison uses sigma_reference^2 * B_reference / B_union <=
4 * sigma_proposal^2; display rounding never decides equality.

The existing report v4 structure is retained:

- `candidate` is the original requested RMS in mJy, at reference width.
- `derived` includes reference/aggregate bandwidth in MHz and aggregate RMS in mJy.
- `details` includes source row/setup/snapshot, raw reference quantities,
  `spw_evidence_json` with all contributing SPWs and frequency/width derivations,
  exact merged intervals, exact squared RMS and approximation limitations.
- Proposal direct aggregate declarations may list valid contributing window IDs.
- Missing quantities yield explicit issues, never substituted measurements.

`spw_evidence_json` and `merged_intervals_ghz_exact_json` are JSON strings inside
the established string-valued details contract. Read these with a second JSON
parse when a structured evidence display is needed.

## Offline numerical acceptance

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/queue_continuum/request.json \
  --queue-csv examples/queue_continuum/queue.csv \
  --queue-continuum --output reports/queue-continuum-synthetic.json
python -m pytest tests/integration/test_queue_continuum.py -q
```

Four synthetic contexts, one displayed: 2 met, 1 not met, 1 indeterminate.
This tests numbers and scope, not independently reviewed real-proposal labels.
The NGC6240 diagnostic request adds an assumed proposed RMS to the existing
retrieval example; see the [example](../examples/queue_continuum/README.md).
Source failures and search completeness remain in the original report.
Top-level NOT_AGGREGATED never means no duplication was found in a complete search.

Auxiliary Use 7-m?/Use TP? flags do not exclude row-level continuum. Position
uses the recorded Portal diameter interpretation; all other candidate quantities
come from that same coherent row/setup.
