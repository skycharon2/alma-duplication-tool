# Documentation guide

This guide separates executable contracts, conceptual design and dated evidence.
The current Python implementation and its tests establish implementation status;
project plans guide architecture and delivery order. Older plan statements that
the request API or comparison model are unimplemented are historical.

Read the short [runtime architecture overview](architecture.md) for module
boundaries and the current evaluation boundary.

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

1. [Rule inputs](duplication_rule_inputs.md): current confirmed scope, separately labelled historical Q1–Q8 discussions and acceptance coverage.
2. [Rules](rules.md): criterion results, implemented criteria and the explicit post-search evaluation entry point.
3. [Data model](data_model.md): current object index, associations and invariants; links lead separately to conceptual ERDs and historical evidence.
4. [Archive dictionary](archive_data_dictionary.md) and [Queue contract](queue_csv_contract.md): source-field semantics and limitations.
5. Use [line pairing](line_pairing_design.md) and the [remaining PR plan](pr_plan_2026-09-21.md) for implementation; confirmed decisions are inputs, not a new approval gate.

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
| What remains to develop, and in which order? | [PR plan](pr_plan_2026-09-21.md) |
| What is the JSON/report contract? | [CLI/report](evaluation_cli.md) |
| Where are original conceptual entities and ERDs? | [Conceptual design](design/conceptual_data_model.md) |
| What was measured, when, on which sample and with what limitations? | [Snapshot evidence](evidence/exploration_snapshots.md) |

## Current capabilities and status meanings

Implemented: independent Archive/Queue ingestion and reconstruction, local Queue
source/parse-summary storage, request validation, offline comparison contexts,
offline search planning, Archive query binding, limited spatial adaptation and
individual spatial/angular predicate checks, and candidate-search orchestration.
Archive continuum has five approved conditions and per-context three-valued branch aggregation. Queue methods retain their provisional status.
An explicit post-search entry point evaluates them for every retained context,
including rows hidden by the presentation limit. Same-request Archive+Queue replay
is also available. Archive line computation and pair/context assessments are implemented. The browser form is not implemented; search-wide absence claims are intentionally not provided.

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
| Search assessment `NOT_EVALUATED` | Candidate-search stage made no formal assessment | A negative duplication verdict |
| Evaluation assessment `NOT_AGGREGATED` | No search-wide verdict; inspect context branches for independent continuum/LINE results | Formal duplication or non-duplication |

The individual `OUTSIDE` or angular `NO_MATCH` result only concerns its explicit
predicate. Missing/unresolved checks and source completeness must remain visible.
The full supported grammar, interpretation requirements and numerical boundary
behavior belong to the [search/spatial contract](search_plan_spatial.md).

## Next delivery

The [remaining PR plan](pr_plan_2026-09-21.md) owns implementation order and gates.
Continuum delivery records are [initial acceptance](confirmed_continuum.md) and
[contract closure](continuum_closure.md); neither is another active task list.

ALMA requires checking both Archive and queued observations; the
[official duplication guidance](https://almascience.eso.org/proposing/duplications)
provides the source entry points and policy references. A candidate is evidence
for review, not an automatic formal duplication conclusion. Versioned policy
citations and Q1–Q8 interpretations remain in the rule-input contract.

- [Queue candidate-beam profile](queue_candidate_beam.md)
- [Verified ALMA source evidence](evidence/official_sources.md)

- [Real dual-source replay](dual_source_replay.md): fixed NGC6240 request, raw Archive capture and Queue subset.
- [Queue POS-SINGLE](pos_single.md): provisional candidate coverage criterion,
  retained-context scope, derived filter summaries and offline replay.
