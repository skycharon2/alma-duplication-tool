# Archive continuum input and report closure

Base: `82ffb013cc54698e042d9f9547d0dcfefc96e1b0` (PR #70 merged).
Scope: close the three post-`4122f81` contract regressions; retain confirmed
scientific formulas and the existing Archive/Queue separation.

## Delivered behavior

- **CONT-RMS:** direct setup aggregate declarations accept absent, empty, subset
  or complete contributing `window_ids`. Present references must be unique and
  resolve within the proposed setup. Validation rejects invalid input; the rule
  also guards references on directly constructed typed requests. IDs are retained
  in normalized input and result `details`. No per-window RMS averaging or
  bandwidth conversion is introduced. Method is `archive_cont_rms_2`.
- **Solar:** valid SUN requests produce a typed request-level exemption before
  search readiness is required. No source files, replay manifests or clients are
  opened. Invalid supplied quantities and references still fail. Search controls
  may be absent. The report records NOT_APPLICABLE, SOLAR_EXEMPT and NOT_QUERIED;
  it does not represent a completed search with zero matches.
- **Diagnostics:** validation version 4 retains ERROR, MISSING and CAPABILITY,
  and adds EVIDENCE for raw frequency-reference and unselected-branch notes.
  Unselected notes have no active `rule_id`. A SKY representative frequency with
  UNKNOWN frame remains raw provenance; it does not falsely block the confirmed
  continuum frequency method. REST/UNKNOWN representative kind still produces
  a selected CONT-FREQ missing-input diagnostic. BOUNDS interval width counts as
  available setup evidence. The obsolete unconditional width-method warning is
  removed. Selecting LINE explicitly reports its unimplemented evaluator.
- **Reports:** version 3 adds `report_kind` and `search_execution`; consumers must
  distinguish CANDIDATE_EVALUATION from SOLAR_EXEMPTION before using plan/query
  fields. Candidate assessment stays NOT_AGGREGATED; continuum context branches
  remain authoritative. Evaluation version 3 and criterion schema 2 are unchanged.
  Historical JSON is never rewritten.

For Solar with `--archive-replay`, `--overwrite` is rejected: response paths
cannot be checked without opening the manifest. Choose a new output and omit
`--overwrite`. This preserves both no-source-access and source-file protection.

## Acceptance

```bash
python -m pytest -q
python -m ruff check --select F src tests
python -m alma_duplicate.cli.evaluate \
  --request examples/confirmed_continuum/request.json \
  --archive-replay examples/confirmed_continuum/archive/manifest.json \
  --output reports/closure-continuum.json
python -m alma_duplicate.cli.evaluate \
  --request examples/solar_exemption.json \
  --output reports/closure-solar.json
```

The continuum fixture now includes all four contribution references. All four
contexts are evaluated despite display limit 1. Status order stays CRITERIA_MET,
CRITERIA_NOT_MET, INDETERMINATE, CRITERIA_NOT_MET. The new CLI regressions cover
subsets, invalid references, Solar source-access traps, invalid Solar input,
selected-branch diagnostics and BOUNDS evidence.

Real replay remains separate:

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/dual_source/request.json \
  --archive-replay tests/fixtures/archive/ngc6240/manifest.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --queue-candidate-beam --output reports/closure-ngc6240.json
```

Expected: 144 Archive + 13 Queue contexts; Archive continuum 91 not met and 53
indeterminate; Queue 13 indeterminate. The request lacks aggregate RMS, so no
RMS pass is implied. Offline replay does not establish current TAP availability.

## Subsequent increments

1. **M3b evidence and pairing:** reuse `LinePairingReference`, add typed source
   redshift and planned per-window resolution/RMS semantics, version `em_xel`
   mode derivation, and build explicit proposed-window/Archive-component pairs.
   Resolve mode, interval, resolution and sensitivity through the same association.
   Missing/conflicting mode and unresolved association remain unknown.
2. **M3b rules and report:** execute FDM and exact coverage, planned-resolution
   compatibility, confirmed 10 km/s RMS scaling and angular correction per pair;
   retain derived values, units, reasons and method versions. A coarser Archive
   resolution blocks RMS computation. Keep continuum and line branches separate.
3. **Acceptance then interface:** guide B is numeric acceptance; captured Archive
   data validates mapping. Cross-SPW mismatch, missing evidence, source failures
   and display truncation are required regressions. Only then attach a thin input,
   candidate, evidence and export interface. Queue mappings remain source-specific.

The existing confirmation is the scientific input for these tasks. No new Q1–Q8
approval round is required. Mosaic is outside these increments.
