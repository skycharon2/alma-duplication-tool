# Documentation guide

For one-shot official Queue CSV acquisition (without activation), see
[Queue auto-update CLI](queue_auto_update.md).

This guide separates executable contracts, conceptual design and dated evidence.
The current Python implementation and its tests establish implementation status;
project plans guide architecture and delivery order. Older plan statements that
the request API or comparison model are unimplemented are historical.

Read the short [runtime architecture overview](architecture.md) for module
boundaries and the current evaluation boundary.

## Start here

- What works and what remains limited: [current status](status.md).
- What to do next: [active roadmap](roadmap.md).
- Run the browser and configure sources: [browser assessment](ui_offline_assessment.md).
- Enter a proposal: [current form](ui_proposed_form.md).
- Read results and explore them: [report browser](ui_report_browser.md) and
  [single-pointing explorer](ui_report_browser.md#single-pointing-report-explorer).
- Earlier delivery notes and test counts: [history](history/delivery_notes.md).
- LINE input migration, stage contracts and acceptance: [LINE scope development](development/line-scope/README.md).

## Reading paths

For candidate-search use and development:

Start with the [candidate-search service](candidate_search.md) for execution,
retention, filtering and completeness; the following contracts define its inputs.

1. [Request API](proposed_observation_api.md): accepted wire fields, units and validation.
   [REST/SKY preparation](proposed_frequency.md) defines the shared LINE/CONTINUUM frequency input method.
   [Automatic retrieval](automatic_retrieval.md) defines the browser default and explicit-radius compatibility.
2. [Search plans and spatial evidence](search_plan_spatial.md): offline planning, query binding and limited individual selectors.
3. [Comparison contexts](comparison_contexts.md): source/row/component identity and evidence states.
4. [Archive client](archive_client_contract.md) and [Queue CSV contract](queue_csv_contract.md): source access, completeness, units and ingestion gates.
   The independent [AQ acquisition client](archive_aq_client.md) fetches official
   source array records; [live AQ assessment](live_aq_assessment.md) defines its
   optional post-TAP integration and failure/provenance contract.
5. [Queue snapshot storage](queue_snapshot_store.md): source acquisition, historical summaries and explicit reparse.
6. [Queue mode census](queue_mode_census.md): conditional configuration matching, full-snapshot counts and unresolved source binding.

The opt-in [formula beam strategy](primary_beam_search.md) replaces region
preselection with center-coordinate retrieval and explicit local beam checks.

For formal-rule development:

1. [Rule inputs](duplication_rule_inputs.md): current confirmed scope, separately labelled historical Q1–Q8 discussions and acceptance coverage.
2. [Rules](rules.md): criterion results, implemented criteria and the explicit post-search evaluation entry point.
3. [Data model](data_model.md): current object index, associations and invariants; links lead separately to conceptual ERDs and historical evidence.
4. [Archive dictionary](archive_data_dictionary.md) and [Queue contract](queue_csv_contract.md): source-field semantics and limitations.
5. Use [line pairing](line_pairing_design.md) and the [remaining PR plan](roadmap.md) for implementation; confirmed decisions are inputs, not a new approval gate.

For Archive antenna diameter, read the [array evidence boundary](archive_array_evidence.md)
and its five-case real-data review before interpreting mixed antenna names.

[Live Archive smoke instructions](live_archive_smoke.md) describe opt-in source
verification. The [live browser TAP and AQ smoke](evidence/live_browser_aq_smoke_2026-10-05.md)
records a successful public-target run and export checks after PR #125.
The [LINE follow-up](evidence/live_browser_line_aq_smoke_2026-10-05.md) verifies
live source binding, SPW pairing, criteria and browser downloads for one LINE input.
The [four-workflow browser verification](evidence/browser_single_point_acceptance_2026-10-12.md)
records live Archive and snapshot Queue CONTINUUM/LINE self-retrieval, numerical
checks, consecutive runs, pagination and unchanged downloads after PR #132.
The [post-PR #134 browser regression](evidence/browser_regression_pr134_2026-10-12.md)
repeats all four workflows after the performance changes and records outcome
parity, retrieval-first provenance, saved-view timings and retained file sizes.
The [post-PR #139 browser-to-explorer acceptance](evidence/browser_explorer_acceptance_2026-10-13.md)
checks four newly generated reports, plot operands, linked selection, saved
downloads and sequential runs, and records the remaining presentation finding.
The [form sketch](proposed_observation_form.md) is a historical design reference;
the [implemented form](ui_proposed_form.md) owns current input mapping, and the
request API owns the accepted backend format. Historical statistics now live in the [snapshot register](evidence/exploration_snapshots.md);
original ERDs and conceptual entities live in the [design document](design/conceptual_data_model.md).
They are not current population counts or Python class definitions.

## Archive Mosaic

**Current Archive-only backend:** [OT pointing import](ot_pointings_backend.md),
[candidate discovery](mosaic_candidate_discovery.md),
[s_region position contract](mosaic_s_region_position.md), and
[assessment entry](assessment_entry.md). The default method evaluates each
candidate context's region with the shared non-position rules. Mosaic is not yet
available through the browser or Queue; see [status](status.md) and
[roadmap](roadmap.md).

**Verification:** [captured live/REPLAY acceptance](../tests/fixtures/archive/s_region_acceptance_2026_10_26/README.md)
contains reproducible engineering evidence, not independently reviewed proposal
labels.

**Retained research:** earlier listobs/auxiliary-product reconstruction is opt-in,
not a prerequisite. Use the [Mosaic research and evidence index](research/mosaic/README.md)
for its tools, dated experiments, acceptance records and decision history.

## UI reading order

For running the browser end to end, start with
[browser assessment sources](ui_offline_assessment.md).
Use [assessment performance measurements](assessment_performance.md) to time
source access, scientific evaluation and report storage separately, and to analyze
report field sizes. The [2026-10-12 measurements](evidence/assessment_stage_size_2026-10-12.md)
locate the current Queue LINE and live Archive bottlenecks.
The [TAP retrieval-first comparison](evidence/tap_retrieval_first_2026-10-12.md)
records the subsequent live CASE1 optimization and completeness checks.
For optional SPWs and explicit researcher confirmation, see the
[continuum setup declaration](continuum_setup_declaration.md).
The [scientific workflow map](ui_scientific_workflow.md) connects the handwritten
design to researcher inputs, candidate conversions and readable report steps.

Read [status](status.md), [thin-interface contract](thin_interface_contract.md),
[shared assessment entry](assessment_entry.md), [request API](proposed_observation_api.md),
[report contract](evaluation_cli.md), then [inspection](report_inspection.md) and
[acceptance](acceptance_cases.md). The [roadmap](roadmap.md) owns delivery order.
Project plans define design goals; current API/report contracts and tests define
field names, branch enums and behavior. In particular, coarse resolution can
fail compatibility while blocking dependent RMS; it is not a blanket unknown.
Historical evidence/reference files retain their original bytes and versions;
the catalog's SHA-256 pins must not be changed by a current-document sync.

## Document classes

| Class | Responsibility | Entry |
| --- | --- | --- |
| CURRENT STATUS | What exists, with supported scope | [Status](status.md) |
| ACTIVE ROADMAP | Remaining order and exit gates | [Roadmap](roadmap.md) |
| CURRENT CONTRACT | Inputs, results, units and source associations | API, rules and source contracts below |
| EXPERIMENT | Conditional assumptions and limitations, not formal rules | [Processor experiment](experiments/queue_processor_consensus.md) |
| DATED EVIDENCE | What was measured/confirmed on a specified sample/date | [Processor measurement](evidence/queue_processor_consensus_2026-09-23.md), evidence records |
| HISTORY | Preserved deliveries and superseded discussions | [Continuum delivery](history/confirmed_continuum.md), [old questions](history/rule_questions_through_2026-09-15.md) |
| DESIGN | Future interface or conceptual design | Form sketch and design directory |

The line-pairing document is an implemented contract despite its historical filename.

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
| What remains to develop, and in which order? | [PR plan](roadmap.md) |
| What is the JSON/report contract? | [CLI/report](evaluation_cli.md) |
| Where are original conceptual entities and ERDs? | [Conceptual design](design/conceptual_data_model.md) |
| What was measured, when, on which sample and with what limitations? | [Snapshot evidence](evidence/exploration_snapshots.md) |

## Current capabilities and status meanings

The [capability matrix](status.md) is the single current implementation summary.
The table below defines result meanings, not an additional task list.

| Axis / value | Current meaning | Does not establish |
| --- | --- | --- |
| Request `is_valid=True` | No ERROR issues; partial scientific evidence is allowed | Search readiness or candidate comparability; there is no VALID/INVALID enum |
| Request `SearchReadiness.READY` | Valid fixed single-pointing ICRS position, a valid explicit radius or resolved AUTO scope, and selected source(s) | Query execution, executable filters or rule readiness |
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

## Queue development reading path

1. [Queue CSV contract](queue_csv_contract.md) and [snapshot storage](queue_snapshot_store.md).
2. [Single-point rule mapping](queue_single_point_mapping.md): source semantics, associations, gaps and tests.
3. Current formal contracts: [Queue common](queue_common.md), [continuum](queue_continuum.md) and [LINE](queue_line_pairing.md).
4. [Mode evidence adapter](queue_mode_adapter.md): scoped row/SPW evidence used by Queue LINE.
5. Read [census v1](queue_mode_census.md) and the [processor experiment](experiments/queue_processor_consensus.md) as needed for diagnostic assumptions and limitations.
6. [Roadmap](roadmap.md): the single owner of engineering order.

<a id="next-delivery"></a>

## Delivery status and remaining work

[Status](status.md) is the single current capability register;
[roadmap](roadmap.md) owns the remaining delivery order. The project has engineering
acceptance for supported single-pointing workflows and selected Archive Mosaic
cases, but no independently reviewed real-proposal verdict. Retrieval results and
individual candidates must not be presented as search-wide non-duplication.
See the [official ALMA duplication guidance](https://almascience.eso.org/proposing/duplications)
for the Archive and current-cycle Queue sources.

### Topic references

- **Request and browser:** [request API](proposed_observation_api.md),
  [implemented form](ui_proposed_form.md), [assessment entry](assessment_entry.md),
  [reports and explorer](ui_report_browser.md).
- **Data access and operations:** [Archive client](archive_client_contract.md),
  [Archive mirrors](archive_mirror_failover.md), [Queue contract](queue_csv_contract.md),
  [snapshot activation](queue_active_snapshot.md) and [browser Queue source](queue_managed_ui.md).
- **Policy and results:** [rule inputs](duplication_rule_inputs.md),
  [criterion evaluation](rules.md), [matching reports](matching_report.md),
  [inspection](report_inspection.md) and [acceptance catalog](acceptance_cases.md).
- **Archive Mosaic:** [current s_region method](mosaic_s_region_position.md),
  [discovery](mosaic_candidate_discovery.md), and
  [retained research/evidence index](research/mosaic/README.md).
- **Historical validation:** [delivery notes](history/delivery_notes.md),
  [continuum delivery](history/confirmed_continuum.md),
  [continuum closure](history/continuum_closure.md),
  [dual-source replay](dual_source_replay.md),
  [historical Queue position method](pos_single.md) and
  [provisional Queue beam profile](queue_candidate_beam.md).

These references are navigation, not separate implementation or scientific-policy
specifications. Follow the linked owning contracts for method versions, evidence
limitations and reproducible commands.
