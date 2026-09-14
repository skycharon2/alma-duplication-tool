# Runtime architecture and next connection

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
| Criteria | ANGULAR and CONT-SETUP are separately callable provisional functions. An explicit evaluation entry point runs them after search; they do not produce an aggregate verdict. |

The [evaluation entry point](../src/alma_duplicate/rules/evaluation.py) takes the
original plan request, evaluates CONT-SETUP once and ANGULAR for each retained
context, including candidates hidden by the display limit. It keeps the search
result and candidate objects intact. The [rule contract](rules.md) specifies
computation, outcome, applicability, approval and multi-side diagnostics.
A successful search, a display group and an approved criterion remain different
objects with different completeness requirements. Formal aggregation is pending.

## Dependencies and focused follow-up

Python and the declared dependencies remain in [pyproject.toml](../pyproject.toml).
PyVO supplies TAP access; source adapters and typed domain objects preserve the
project's stronger provenance and evidence contracts. Notebook/plotting tooling
supports exploration. The present dependency lists do not establish a tested
minimum/maximum compatibility matrix; changing bounds needs separate validation.
No Web framework is selected by this change.

This patch shares exact canonical-scalar arithmetic between the two rules.
Other dependency work is explicitly deferred: move scalar execution out of
planning, extract common spherical helpers from spatial/beam code, and isolate
the source-scoped bandwidth mapping currently imported from Queue normalization.
Do not claim those refactors are completed, or broaden a mapping's applicability
merely because its function is moved into a shared module.

Project plans and historical measurement records describe their dated baseline.
Current implementation status belongs to executable contracts and tests; a plan's
older statement about missing request/search functionality does not override them.
