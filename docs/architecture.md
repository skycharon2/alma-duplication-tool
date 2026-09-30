# Runtime architecture

The reviewed implementation baseline and verification conditions are owned by
[status](status.md). The bounded extractions and shared application entry below
are implemented; browser integration remains the next product delivery.

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
The browser presentation layer uses Flask and Jinja; it consumes backend
contracts without reimplementing scientific rules.

ANGULAR and CONT-SETUP share exact canonical-scalar arithmetic. POS-SINGLE
uses spherical floating-point geometry: Archive has an inclusive <= boundary;
the supported Queue workflow uses the versioned row-beam method documented in
[Queue common](queue_common.md), while legacy Queue method versions retain their
historical meaning.
The shared LINE preparation preserves exact decision operands, with floating-point
values reserved for display; see the [precision contract](line_precision.md).
Inspection v3 preserves pair references and report-local locations; see the
[inspection contract](report_inspection.md). These fixes and the bounded extractions below are implemented.

### Dependency responsibilities and delivered extractions

| Layer | Allowed responsibility/dependency direction |
| --- | --- |
| CLI and future UI | Call application orchestration; own arguments/forms, file handling and presentation, not scientific formulas. |
| Application orchestration | Validate, handle Solar exemption, configure sources, search, evaluate and serialize. The shared `assessment.assess_observation()` entry owns this coordination, including configuration preflight before source access; see [application contract](assessment_entry.md). |
| Source and association adapters | Parse source-specific evidence into domain objects and preserve provenance; do not depend on UI rendering or branch verdicts. |
| Scientific rules and aggregation | Consume coherent request/context/pair evidence and numerical helpers; retain source-specific mappings and combine whole criteria/pairs. |
| Reports and inspection | Consume evaluation output; do not call source clients or recompute scientific conditions. |
| Pure helpers | Geometry and numeric transformations may depend on math, Astropy and required value types; they must not import strategy dispatch, source clients or rules. |

These are maintenance boundaries, not a claim that every current import already
follows the target direction. The LINE helper, pure geometry and spatial evidence extractions are complete;
their preserved boundaries are explicit:

- Archive/Queue LINE now share `rules.numeric.rational_to_display()` and
  `explicit_unit_quantity()`, plus `rules.aggregation.criterion_truth()`.
  These were identical implementations before extraction; display overflow,
  underflow, square-root handling, unit scales and formal eligibility gates are
  preserved. Source-specific result construction, evidence and RMS formulas
  remain separate. Scientific method and report versions are unchanged.
- `geometry` owns `angular_separation_deg()` and `primary_beam_fwhm_deg()`.
  Its runtime imports are standard-library only; the coordinate annotation is
  type-checking-only. It interprets neither source evidence nor frame/beam scope.
  Formula bodies and operation order are unchanged. `spatial._separation` and
  `primary_beam.primary_beam_fwhm_deg` remain compatibility exports of the same
  functions. Legacy `at_boundary()` and `covers()` stay in `primary_beam`;
  formal inclusive position comparisons remain in the source rules.
- `spatial_evidence` now owns `adapt_spatial()` and its four parsing helpers.
  It depends on source/domain contracts, array classification and geometry, not
  strategy dispatch, search planning or scientific rules. `spatial` retains
  `evaluate_spatial()` and compatibility exports for the moved functions.
  `queue_position`, `candidate_search` and the Archive position rule import the
  adapter directly from its owner. Thus Queue strategy no longer imports
  `spatial` back. Independent-process tests cover this dependency boundary and
  import order. This closes the targeted spatial adaptation/dispatch cycle,
  not an audit or elimination of every possible repository import cycle.
- `queue_mode_reference` owns the supported configuration catalog, matching,
  representation tolerances and typed conditional TP counterpart mapping. Both
  the formal `queue_mode_adapter` and the experimental `queue_processor_mode`
  consume this layer; the formal adapter never reads an experiment report.
  The experiment retains compatibility exports and its provisional report
  contract. The older census retains its distinct BLC catalog. Mapping remains
  conditional, enumeration incomplete, and N16 scope unchanged.
- `assessment.assess_observation()` owns validation, Solar handling, method
  selection, search/evaluation and report assembly. CLI retains JSON/file
  handling, lazy provider construction, overwrite guards and exit codes.
  [Application contract](assessment_entry.md) documents the callable boundary;
  browser form/rendering integration remains the next delivery.

The [roadmap](roadmap.md#bounded-maintenance-increments) owns their order and
acceptance gates. Compatibility exports, explicit legacy/provisional paths,
experiment CLIs, pinned captures and exploratory notebooks are not deletion
candidates merely because they are outside the default formal path. Preserve
scientific versions when code only moves, and fix discovered behavior defects
in separate changes. No general rule engine or directory redesign is required.

Project plans and historical measurement records describe their dated baseline.
Current implementation status belongs to executable contracts and tests; a plan's
older statement about missing request/search functionality does not override them.

## Read-only browser reports

Flask/Jinja consumes startup-bound backend report artifacts through `ui/reports.py`.
It calls the existing inspection v3 consumer; it does not call search or rule
evaluators. The original bytes are retained for download, while a paginated view
uses the parsed document. UI paths select opaque in-process IDs, not filesystem
paths. The proposed-input form validates requests but does not invoke the assessment entry.

## Proposed form boundary

`ui/proposed.py` maps submitted strings into the existing request wire schema.
`/proposed` calls `validate_proposed_observation()` directly and displays its
diagnostics/readiness. It does not invoke assessment, providers or source clients.
Window row tokens survive editing; window IDs bind each LINE sensitivity.
Request JSON downloads revalidate the current form and contain no report verdict.
