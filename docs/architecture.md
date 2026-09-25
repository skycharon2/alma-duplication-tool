# Runtime architecture



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
Other dependency work is explicitly deferred: move scalar execution out of
planning, extract common spherical helpers from spatial/beam code, and isolate
the source-scoped bandwidth mapping currently imported from Queue normalization.
Do not claim those refactors are completed, or broaden a mapping's applicability
merely because its function is moved into a shared module.

Project plans and historical measurement records describe their dated baseline.
Current implementation status belongs to executable contracts and tests; a plan's
older statement about missing request/search functionality does not override them.
