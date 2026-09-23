> Historical delivery record. Its versions, measurements and next-step wording describe that delivery.
> Current behavior: [status](../status.md); current tasks: [roadmap](../roadmap.md).

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

## Delivery validation record

Delivered in `61813bd`, merged by PR #71 as `c1785b2`. Default suite: 962 passed,
10 skipped; Ruff F passed. The guide replay evaluated all four contexts despite
showing one. The real replay evaluated 144 Archive and 13 Queue contexts.
Live TAP and the full external Queue snapshot were not rerun in this delivery.

Regression owner: [closure tests](../../tests/integration/test_continuum_closure.py).
Commands and synthetic expected results: [confirmed continuum](../confirmed_continuum.md).
Real capture and current expected output: [dual-source replay](../dual_source_replay.md).
Current request schema: [API](../proposed_observation_api.md); current report schema:
[CLI/report](../evaluation_cli.md). Version numbers above describe this historical
delivery and do not override later contract versions.

Remaining tasks are maintained only in the [PR plan](../pr_plan_2026-09-21.md).
