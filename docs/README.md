# Documentation guide

This guide separates executable contracts, conceptual design and dated evidence.
The current Python implementation and its tests establish implementation status;
project plans guide architecture and delivery order. Older plan statements that
the request API or comparison model are unimplemented are historical.

## Reading paths

For candidate-search service development:

1. [Request API](proposed_observation_api.md): accepted wire fields, units and validation.
2. [Search plans and spatial evidence](search_plan_spatial.md): offline planning, query binding and limited individual selectors.
3. [Comparison contexts](comparison_contexts.md): source/row/component identity and evidence states.
4. [Archive client](archive_client_contract.md) and [Queue CSV contract](queue_csv_contract.md): source access, completeness, units and ingestion gates.
5. [Queue snapshot storage](queue_snapshot_store.md): source acquisition, historical summaries and explicit reparse.

For formal-rule development:

1. [Rule inputs](duplication_rule_inputs.md): required evidence, open Q1–Q7 decisions and acceptance coverage.
2. [Data model](data_model.md): current object index, associations and invariants; the ERDs are explicitly conceptual.
3. [Archive dictionary](archive_data_dictionary.md) and [Queue contract](queue_csv_contract.md): source-field semantics and limitations.
4. Return to the rule-input decision register and acceptance cases before implementing an affected policy method.

[Live Archive smoke instructions](live_archive_smoke.md) describe opt-in source
verification. The [form design](proposed_observation_form.md) is future interface
design; the request API owns the accepted backend format. Historical statistics
and conceptual diagrams still live in their original documents pending structural
cleanup; they are not current population counts or Python class definitions.

## Current capabilities and status meanings

Implemented: independent Archive/Queue ingestion and reconstruction, local Queue
source/parse-summary storage, request validation, offline comparison contexts,
offline search planning, Archive query binding, limited spatial adaptation and
individual spatial/angular predicate checks. End-to-end candidate-search
orchestration, formal duplication assessment and the browser form are not implemented.

| Axis / value | Current meaning | Does not establish |
| --- | --- | --- |
| Request `is_valid=True` | No ERROR issues; partial scientific evidence is allowed | Search readiness or candidate comparability; there is no VALID/INVALID enum |
| Request `SearchReadiness.READY` | Valid fixed single-pointing ICRS position, explicit valid radius and selected source(s) | Query execution, executable filters or rule readiness |
| Context source `COMPLETE` | Construction succeeded for the supplied complete query/file | Agreement with the current plan, all-sky completeness or complete Queue policy coverage |
| Query binding `MATCHED` | Recorded Archive query agrees with the current builder's plan | Successful/complete remote retrieval; a matching overflow remains incomplete |
| Spatial evidence `AVAILABLE` | The relevant supported evidence is available in `SpatialStatus` | A selection result, general STC-S support or approved beam coverage |
| Spatial selection `INSIDE` | One supported planned selection condition holds | Formal position criterion or duplication |
| Individual selection `NOT_EVALUATED` | Evidence, interpretation or method does not permit a definite check | OUTSIDE/NO_MATCH; it cannot justify silent exclusion |
| Plan `NOT_EXECUTED` | No complete search has been orchestrated | Absence of individual predicate results |
| Assessment `NOT_EVALUATED` | Formal assessment has not been performed | A negative duplication verdict |

The individual `OUTSIDE` or angular `NO_MATCH` result only concerns its explicit
predicate. Missing/unresolved checks and source completeness must remain visible.
The full supported grammar, interpretation requirements and numerical boundary
behavior belong to the [search/spatial contract](search_plan_spatial.md).

## Next delivery

Connect the existing `SearchPlan`, Archive client execution, comparison contexts
and Queue local selection in a candidate-search service. Reuse the current model.
The service must:

- report Archive and Queue execution/completeness independently and verify Archive query binding;
- retain unevaluated rows, or explicitly report any omitted scope rather than silently treating them as non-matches;
- record applied, skipped and unevaluated predicates, result limits, truncation and source scope;
- retain source provenance, including separately held Queue store records until explicit store-record binding exists.

Supervisor CASE1/CASE2 retrieval verification requires confirmed grouping and
pinned evidence; those cases are not confirmed duplicate labels. Formal rule
assessment is a separate delivery gated by the affected scientific decisions,
not a reason to redesign or delay the existing request/context building blocks.

ALMA requires checking both Archive and queued observations; the
[official duplication guidance](https://almascience.eso.org/proposing/duplications)
provides the source entry points and policy references. A candidate is evidence
for review, not an automatic formal duplication conclusion. Versioned policy
citations and Q1–Q7 interpretations remain in the rule-input contract.
