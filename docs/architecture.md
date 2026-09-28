# Runtime architecture

Reviewed runtime baseline: `f28e24f` (PR #92, 2026-09-28).

This is a navigation map of implemented boundaries, not another field schema.
The [object index](data_model.md) links definitions and the
[documentation guide](README.md) assigns contract ownership.

| Stage | Current implementation and boundary |
| --- | --- |
| Input | Request validation returns typed proposed evidence and separate search controls; valid partial science input is allowed. |
| Plan | Search planning defines source operations, query binding and intended predicates. A plan does not establish execution. |
| Source access | Archive querying retains query/run metadata and completeness; Queue ingestion retains file provenance and strict parse status. |
| Association | Reconstruction and comparison construction retain row/component or real Queue associations, including alternatives. Member grouping does not authorize mixing them. |
| Search execution | Candidate search orchestrates source calls, binding, local selectors and independent execution reports; failed or incomplete sources remain visible. |
| Presentation | Grouping organizes candidate rows for display while retaining their contexts and filter records. |
| Criteria | Archive continuum/LINE and the supported Queue common/continuum/LINE methods feed source-bound per-context branch aggregation. Queue LINE keeps same-row/same-SPW evidence; no branch aggregation crosses candidate contexts or sources. |
| Report and inspection | Report v4 serializes complete retained-context results; inspection v3 reads that report without recomputing criteria and locates pair-specific gaps. |

The [evaluation entry point](../src/alma_duplicate/rules/evaluation.py) takes the
original plan request and selects branches by intents. For CONTINUUM it evaluates
CONT-SETUP once and four candidate conditions for every retained context, including
candidates hidden by the display limit. It keeps the search
result and candidate objects intact. The [rule contract](rules.md) specifies
computation, outcome, applicability, approval and multi-side diagnostics.
A successful search, a display group and an approved criterion remain different
objects with different completeness requirements. Continuum and LINE context aggregation are implemented for the supported Archive and Queue paths; search-wide and cross-source conclusions are not.
Valid SUN requests exit through a typed request-level exemption before search;
no source clients or replay loaders are invoked.

## Dependencies and focused follow-up

Python and the declared dependencies remain in [pyproject.toml](../pyproject.toml).
PyVO supplies TAP access; source adapters and typed domain objects preserve the
project's stronger provenance and evidence contracts. Notebook/plotting tooling
supports exploration. The present dependency lists do not establish a tested
minimum/maximum compatibility matrix; changing bounds needs separate validation.
No Web framework is selected by this change.

ANGULAR and CONT-SETUP share exact canonical-scalar arithmetic. POS-SINGLE
uses spherical floating-point geometry: Archive has an inclusive <= boundary;
the supported Queue workflow uses the versioned row-beam method documented in
[Queue common](queue_common.md), while legacy Queue method versions retain their
historical meaning.
The shared LINE preparation preserves exact decision operands, with floating-point
values reserved for display; see the [precision contract](line_precision.md).
Inspection v3 preserves pair references and report-local locations; see the
[inspection contract](report_inspection.md). These fixes are implemented, unlike
the extraction work below.

### Dependency responsibilities and current exceptions

| Layer | Allowed responsibility/dependency direction |
| --- | --- |
| CLI and future UI | Call application orchestration; own arguments/forms, file handling and presentation, not scientific formulas. |
| Application orchestration | Validate, handle Solar exemption, configure sources, search, evaluate and serialize. Today this coordination lives in the CLI; no shared application entry has been extracted yet. |
| Source and association adapters | Parse source-specific evidence into domain objects and preserve provenance; do not depend on UI rendering or branch verdicts. |
| Scientific rules and aggregation | Consume coherent request/context/pair evidence and numerical helpers; retain source-specific mappings and combine whole criteria/pairs. |
| Reports and inspection | Consume evaluation output; do not call source clients or recompute scientific conditions. |
| Proposed pure helpers | Geometry and numeric transformations may depend on math, Astropy and required value types; they must not import strategy dispatch, source clients or rules. |

These are maintenance boundaries, not a claim that every current import already
follows the target direction. Current exceptions are explicit:

- Archive/Queue LINE duplicate display, unit conversion and criterion-to-truth
  helpers. Their source-specific result construction and RMS evidence remain
  intentionally separate.
- `spatial` dispatches to `primary_beam` and `queue_position`; those modules
  import separation and/or adaptation back from `spatial`, including lazy imports.
  Extracting geometry alone will not remove the adaptation dependency.
- The formal `queue_mode_adapter` imports configurations and calls experimental
  `queue_processor_mode.evaluate()` for mapping output. Reference configuration
  and mapping responsibilities should be separated without changing their scope.
- Validation, Solar handling and method selection currently live in CLI
  orchestration. Extract a shared entry with the first actual UI caller.

The [roadmap](roadmap.md#bounded-maintenance-increments) owns their order and
acceptance gates. Compatibility exports, explicit legacy/provisional paths,
experiment CLIs, pinned captures and exploratory notebooks are not deletion
candidates merely because they are outside the default formal path. Preserve
scientific versions when code only moves, and fix discovered behavior defects
in separate changes. No general rule engine or directory redesign is required.

Project plans and historical measurement records describe their dated baseline.
Current implementation status belongs to executable contracts and tests; a plan's
older statement about missing request/search functionality does not override them.
