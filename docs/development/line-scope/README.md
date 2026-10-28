# LINE scope development records

These records describe the input-contract migration, its implementation stages
and acceptance boundaries. Read the [request API](../../proposed_observation_api.md)
for the shared entry contract, [current status](../../status.md) for supported
workflows and [roadmap](../../roadmap.md) for delivery priorities.

## Merged stages

| Stage | Record | Boundary recorded by this stage |
| --- | --- | --- |
| 01 / 01b | [Legacy baseline](line_scope_transition_baseline.md) | Characterizes legacy LINE aggregation for Single Pointing, reconstructed Mosaic and default `s_region` Mosaic. |
| 02 | [Versioned scope gate](line_scope_step02_contract.md) | Reserves the submitted-requirements scope and rejects its execution; omitted scope retains legacy behavior. |
| 03 | [Browser required LINE fields](line_scope_step03_browser_required_line.md) | Adds Run-only validation to the legacy browser form; records its shared-row limitation. |
| 03b-A | [Separated input contract](step03ba_separated_contract.md) | Defines independent LINE requirements, physical SPW evidence and explicit links; new-format assessment remains blocked. |
| 03b-B | [Separated browser editor](step03bb_separated_browser_editor.md) | Edits and exports the new structure through `/proposed/separated`; does not run assessment. |
| 03b-C | [Cross-scope acceptance](step03bc_cross_scope_acceptance.md) | Verifies export, typed operands, identities and execution guards across geometries and purposes. |

The stage records retain their original statements and commands. References to
later work describe the boundary at that stage, not a separate current roadmap.
In particular, 03b-C verifies the blocked execution boundary; it does not enable
new-format LINE or Continuum assessment. Step 04 remains separate work.

## Current versioned LINE implementation

- [04A: submitted LINE context OR](step04a_submitted_line_aggregation.md): pure V2 aggregation.
- [04B: reference-bound context evaluation](step04b_reference_bound_line_evaluation.md):
  internal six-criterion V2 evaluator.
- [04C: explicitly scoped Archive backend assessment](step04c_v2_archive_assessment.md):
  candidate reports, not search-wide absence conclusions.
- [05A: opt-in V2 Single Pointing browser](step05a_v2_browser_single.md):
  new editor run and JSON export with standalone transient results.

These links document separate, versioned execution paths. The default legacy
assessment and its reports are unchanged; Continuum and Mosaic V2 browser runs
are not enabled by 05A.

## Reading order

- Input structure and identities: start with **03b-A**.
- Browser editing and export: continue with **03b-B**.
- Reproducible acceptance and limits: use **03b-C** and the **01/01b** baseline.
- Legacy compatibility and the reserved evaluation scope: read **02**.

Run the commands in these records from the repository root. Original scientific
evidence remains under [evidence](../../evidence/) and
[Mosaic research](../../research/mosaic/README.md); it has not been relocated.

## Backend acceptance

- [Default region and bounded-source regression](submitted_v2_backend_acceptance.md).
- [Mosaic discovery integration](submitted_v2_mosaic_search.md).
- [CASE2 fixed and online end-to-end acceptance](case2_v2_end_to_end.md).
- [Normal-form Mosaic LINE integration](mosaic_v2_normal_form.md).
