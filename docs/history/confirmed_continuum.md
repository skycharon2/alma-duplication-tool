> Historical delivery record. Its versions, measurements and next-step wording describe that delivery.
> Current behavior: [status](../status.md); current tasks: [roadmap](../roadmap.md).

# Confirmed Archive continuum increment

Baseline: `6b48b3b95f99d0333128b2e0c9f6cd06a9c51fce`.

The [confirmation record](../evidence/supervisor_confirmation_2026-09-17.md) owns
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

The [dual-source replay](../dual_source_replay.md) owns the separate real-capture
command, expected counts and mapping limitations.

## Contract ownership

This is the numeric acceptance record for the initial `4122f81` / PR #70 delivery.
The [CLI/report contract](../evaluation_cli.md) owns current report schema and
migration details; [rules](../rules.md) owns criteria and aggregation semantics.
[Contract closure](../continuum_closure.md) records the subsequent `61813bd` fixes.
The [PR plan](../pr_plan_2026-09-21.md) is the sole remaining-work list.
