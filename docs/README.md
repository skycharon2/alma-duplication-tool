# Documentation guide

This guide separates executable contracts, conceptual design and dated evidence.
The current Python implementation and its tests establish implementation status;
project plans guide architecture and delivery order. Older plan statements that
the request API or comparison model are unimplemented are historical.

## Reading paths

For candidate-search use and development:

Start with the [candidate-search service](candidate_search.md) for execution,
retention, filtering and completeness; the following contracts define its inputs.

1. [Request API](proposed_observation_api.md): accepted wire fields, units and validation.
2. [Search plans and spatial evidence](search_plan_spatial.md): offline planning, query binding and limited individual selectors.
3. [Comparison contexts](comparison_contexts.md): source/row/component identity and evidence states.
4. [Archive client](archive_client_contract.md) and [Queue CSV contract](queue_csv_contract.md): source access, completeness, units and ingestion gates.
5. [Queue snapshot storage](queue_snapshot_store.md): source acquisition, historical summaries and explicit reparse.

The opt-in [formula beam strategy](primary_beam_search.md) replaces region
preselection with center-coordinate retrieval and explicit local beam checks.

For formal-rule development:

1. [Rule inputs](duplication_rule_inputs.md): required evidence, open Q1–Q7 decisions and acceptance coverage.
2. [Data model](data_model.md): current object index, associations and invariants; links lead separately to conceptual ERDs and historical evidence.
3. [Archive dictionary](archive_data_dictionary.md) and [Queue contract](queue_csv_contract.md): source-field semantics and limitations.
4. Return to the rule-input decision register and acceptance cases before implementing an affected policy method.

[Live Archive smoke instructions](live_archive_smoke.md) describe opt-in source
verification. The [form design](proposed_observation_form.md) is future interface
design; the request API owns the accepted backend format. Historical statistics now live in the [snapshot register](evidence/exploration_snapshots.md);
original ERDs and conceptual entities live in the [design document](design/conceptual_data_model.md).
They are not current population counts or Python class definitions.

## Document responsibilities

Each contract owns its complete specification; other documents link to it rather
than redefining fields, formulas or behavior. Read historical evidence only when
its justification or sample limits are needed.

| Question | Authoritative project document |
| --- | --- |
| Which request fields/units are accepted and how are they validated? | [Request API](proposed_observation_api.md) |
| Which current objects/keys/associations must be preserved? | [Data model](data_model.md) |
| How are source contexts built and their evidence/provenance exposed? | [Comparison contexts](comparison_contexts.md) |
| How are requests executed and candidate/unevaluated rows retained? | [Candidate search](candidate_search.md) |
| How are plans bound and supported individual predicates evaluated? | [Search/spatial](search_plan_spatial.md) |
| How does TAP querying, projection and completeness behave? | [Archive client](archive_client_contract.md) |
| What do Archive fields/statuses mean and which are selected? | [Archive dictionary](archive_data_dictionary.md) |
| How are CSV layout, units, nominal/usable frequencies and failures handled? | [Queue contract](queue_csv_contract.md) |
| How are exact Queue sources and historical summaries stored? | [Queue storage](queue_snapshot_store.md) |
| What evidence/scientific decisions/acceptance cases do formal rules need? | [Rule inputs](duplication_rule_inputs.md) |
| Where are original conceptual entities and ERDs? | [Conceptual design](design/conceptual_data_model.md) |
| What was measured, when, on which sample and with what limitations? | [Snapshot evidence](evidence/exploration_snapshots.md) |

## Current capabilities and status meanings

Implemented: independent Archive/Queue ingestion and reconstruction, local Queue
source/parse-summary storage, request validation, offline comparison contexts,
offline search planning, Archive query binding, limited spatial adaptation and
individual spatial/angular predicate checks, and candidate-search orchestration.
Formal duplication assessment and the browser form are not implemented.

| Axis / value | Current meaning | Does not establish |
| --- | --- | --- |
| Request `is_valid=True` | No ERROR issues; partial scientific evidence is allowed | Search readiness or candidate comparability; there is no VALID/INVALID enum |
| Request `SearchReadiness.READY` | Valid fixed single-pointing ICRS position, explicit valid radius and selected source(s) | Query execution, executable filters or rule readiness |
| Context source `COMPLETE` | Construction succeeded for the supplied complete query/file | Agreement with the current plan, all-sky completeness or complete Queue policy coverage |
| Query binding `MATCHED` | Recorded Archive query agrees with the current builder's plan | Successful/complete remote retrieval; a matching overflow remains incomplete |
| Spatial evidence `AVAILABLE` | The relevant supported evidence is available in `SpatialStatus` | A selection result, general STC-S support or approved beam coverage |
| Spatial selection `INSIDE` | One supported planned selection condition holds | Formal position criterion or duplication |
| Individual selection `NOT_EVALUATED` | Evidence, interpretation or method does not permit a definite check | OUTSIDE/NO_MATCH; it cannot justify silent exclusion |
| Plan `NOT_EXECUTED` | Declarative plan marker; execution is recorded separately by the service | Whether a service run has finished |
| Service `FINISHED` | Orchestration ended; inspect each source and filter outcome | All sources succeeded, all filters ran or a duplication verdict |
| Assessment `NOT_EVALUATED` | Formal assessment has not been performed | A negative duplication verdict |

The individual `OUTSIDE` or angular `NO_MATCH` result only concerns its explicit
predicate. Missing/unresolved checks and source completeness must remain visible.
The full supported grammar, interpretation requirements and numerical boundary
behavior belong to the [search/spatial contract](search_plan_spatial.md).

## Next delivery

The [candidate-search service](candidate_search.md) now connects the existing
plan, Archive execution/binding, comparison contexts and Queue local selection.
It preserves per-source failures, row/filter records, skipped conditions and
display-limit omissions. Current geometry and scientific-method limits remain
explicit; persistent Queue acquisition/run binding remains the caller's task.

Review the [reported scientific feedback](evidence/scientific_feedback.md) and its
remaining closure requirements; reported oral answers do not enable formal rules.
Next, independently reproduce CASE1/CASE2 retrieval and pin source evidence,
effective filters and display grouping/count semantics. Extend supported
spatial and scientific evidence only with focused acceptance tests.

Supervisor CASE1/CASE2 retrieval verification requires confirmed grouping and
pinned evidence; those cases are not confirmed duplicate labels. Formal rule
assessment is a separate delivery gated by the affected scientific decisions,
not a reason to redesign or delay the existing request/context building blocks.

ALMA requires checking both Archive and queued observations; the
[official duplication guidance](https://almascience.eso.org/proposing/duplications)
provides the source entry points and policy references. A candidate is evidence
for review, not an automatic formal duplication conclusion. Versioned policy
citations and Q1–Q7 interpretations remain in the rule-input contract.
