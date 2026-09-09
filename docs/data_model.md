# Current Archive–Queue data model

Document revision: 0.7. This revision reorganizes documentation; it does not
change a runtime schema, parser, adapter or model version.

## Status and scope

This document owns the implemented Python object relationships, identities,
cardinalities and invariants used between ingestion, comparison construction and
search/spatial adaptation. The [documentation guide](README.md) defines reading
paths and the next delivery. Formal evidence requirements and open scientific
decisions belong to the [rule-input contract](duplication_rule_inputs.md).

The [conceptual design](design/conceptual_data_model.md) preserves the original
ERDs and entity descriptions; uppercase entities there are not Python classes.
The [snapshot register](evidence/exploration_snapshots.md) preserves dated
notebook evidence. Neither describes ALMA's internal database schema.

## Current object index

Links identify definition files. Objects listed together share the same layer;
none implies that an approved comparison method or a persistence schema exists.

| Layer | Python objects and definitions | Responsibility |
| --- | --- | --- |
| Archive query | [`ArchiveQuerySpec`](../src/alma_duplicate/clients/archive_queries.py); [`ArchiveQueryResult`, `ArchiveQueryProvenance`, `TapResponse`](../src/alma_duplicate/clients/archive_contract.py) | Explicit query and projection, ordered raw rows/FIELD metadata and run completeness |
| Archive preparation | [`PreparedArchiveRow`, `ArchivePipelineBatch`](../src/alma_duplicate/clients/archive_adapter.py); [`ArchiveComparisonEvidence`](../src/alma_duplicate/domain/archive_evidence.py) | Raw row, normalization, typed quantities, reconstruction inputs and source result |
| Archive reconstruction | [`SourceExecutionKey`, `SourceSpwAssociationKey`, `RowReconstruction`, `ReconstructionBatch`](../src/alma_duplicate/domain/reconstruction.py) | Observed identities and row-level linkage attempts |
| Support evidence | [`RowFrequencySupportEvidence`, `SupportComponentRef`, `SupportMapping`](../src/alma_duplicate/domain/reconstruction.py) | Saved full parse result and row/parser-scoped component mapping |
| Queue ingestion | [`QueueSnapshot`, `QueueRawRowId`, `RawQueueRow`, `QueueRowInput`, `QueueCsvParseResult`](../src/alma_duplicate/domain/queue.py) | File provenance, raw strings, source-line identity and typed source rows |
| Queue reconstruction | [`QueueGroupKey`, `QueueSpatialComponent`, `QueueSpectralSetup`, `QueueRequestContext`, `QueueRowAssociation`, `QueueFactorizationSummary`, `QueueReconstructionBatch`, `QueuePipelineBatch`](../src/alma_duplicate/domain/queue.py) | Factored components connected only through actual source rows |
| Queue persistence | [`StoredQueueSource`, `StoredQueueRun`, `QueueSnapshotStore`](../src/alma_duplicate/storage/queue_snapshots.py) | Exact source bytes/acquisition facts and independent historical parse summaries |
| Request | [`ProposedObservationRequest`, `SearchOptions`, `RequestValidationResult`](../src/alma_duplicate/domain/proposed_observation.py) | Validated proposed evidence, explicit search controls and request readiness |
| Comparison | [`ComparisonContext`, `ArchiveContextEvidence`, `QueueContextEvidence`, `EvidenceReference`, `EvidenceItem`, `ComparisonSourceResult`, `ComparisonPreparation`](../src/alma_duplicate/domain/comparison.py) | Unfiltered source contexts, evidence dimensions and retained source results |
| Planning | [`SearchPlan`, `SourceSearchPlan`, `PlannedPredicate`, `QueryPlanBinding`, `ScalarSelection`](../src/alma_duplicate/domain/search.py) | Offline operations, query binding and individual scalar predicate results |
| Spatial | [`SpatialEvidence`, `SpatialStatus`, `PositionInterpretation`, `SkyPosition`, `CircleFootprint`, `SpatialSelection`](../src/alma_duplicate/domain/spatial.py) | Source-bound center/footprint, explicit interpretation and individual spatial checks |

## Archive identities and associations

### Raw row and source result

`ArchivePipelineBatch` retains its `ArchiveQueryResult`, field/identifier
contracts, prepared rows and `ReconstructionBatch`. Every `PreparedArchiveRow`
retains the raw row, normalized metadata, reconstruction input and typed
comparison evidence. The adapter's raw-row ID is the query-run ID followed by
its zero-based result index formatted with at least eight digits. Equal rows
remain separate; the identifier is scoped to a query run, not a physical file.

`proposal_id`, `obs_publisher_did`, Member and ASDM identifiers retain their
source semantics. No public Archive field is a universal row primary key.
The publisher DID is project evidence, not row/product identity. Member OUS is
an outer grouping scope; it cannot authorize combining observations.

Raw rows are copied into read-only mappings by the client. Incomplete query
results cannot enter the normal reconstruction pipeline. Exact scalar types,
FIELD metadata, projection/version behavior, unit gates and zero-row handling
are owned by the [Archive client contract](archive_client_contract.md).
The [dictionary](archive_data_dictionary.md#production-projection-v1-schema-3-client-7)
owns selected fields and their representation; the historical full catalogue
is not a claim that every field is retrieved.

### Reconstruction keys

| Key / result | Identity or cardinality | Meaning |
| --- | --- | --- |
| `SourceExecutionKey` | `(member_ous_uid, asdm_uid, source_name)` | Parsed source within one Member/execution; no physical-target alias resolution |
| `SourceSpwAssociationKey` | `context` plus `spw_token`, `spw_index` | One observed source/execution/SPW association |
| `RowReconstruction` | One result per input raw row | A linked association or an explicit unsafe/missing/mismatch result |
| `ReconstructionBatch.associations` | Unique observed keys, variable length | May be sparse; no source × SPW grid is generated |
| Rows supporting an association | Multiple allowed | Neither deduplication nor proof of distinct physical products |

Unsafe `obs_id`, missing required identity or parsed Member mismatch leaves a
row unlinked with reasons. Identifier grammar, live VOTable width conformance
and the historical truncation boundary are separate evidence dimensions; see
[identifier behavior](archive_client_contract.md) and
[status values](archive_data_dictionary.md#implemented-status-values).
Source/execution metadata remains reachable through its originating row;
there is no automatic collapse into one representative footprint or RMS.

### Spectral mapping boundary

Each `RowFrequencySupportEvidence` stores the complete parse result independently
of identifier linkage. Reconstruction reuses that result for mapping. A
`SupportComponentRef` consists of `(raw_row_id, parser_version, component_index)`;
it is not a globally meaningful SPW identifier.

The current `_map_support` in [reconstruction.py](../src/alma_duplicate/reconstruction.py)
requires the whole parse result to be valid. A failed component can therefore
block row mapping without proving that every independent row quantity is invalid.
Ambiguous candidates remain in `candidate_refs`; only an assigned, unique
reference selects a component. `resolve()` rejects another row or parser version.
Several SPWs may map to one support component; component order is not an official
SPW number. Independent frequency/RMS evaluability is a future comparison-method
requirement, not a change to this implemented validity gate.

## Queue row associations

A complete `QueueCsvParseResult` supplies `QueueRowInput` records to reconstruction.
`QueuePipelineBatch` retains that parse result and its `QueueReconstructionBatch`.
An incomplete parse cannot enter normal reconstruction; raw diagnostics remain
in the source result. Parser/layout/unit requirements belong to the
[Queue contract](queue_csv_contract.md).

`QueueRawRowId` preserves snapshot and source-line identity. Equal content on
different lines remains distinct, while duplicate raw-row IDs are rejected at
the reconstruction entry point. The group key `(Project Code, Target Name, Band)`
is an internal analytical scope, not an official Science Goal, Scheduling Block
or candidate identity.

| Object | Owned relationship/evidence |
| --- | --- |
| `QueueSnapshot` | Source provenance, dictionary/header metadata and versions; not persisted source bytes |
| `RawQueueRow` | Raw operational strings, physical line range, ordinal and content fingerprint |
| `QueueRowInput` | Typed spatial, spectral and request evidence tied to its raw row |
| `QueueSpatialComponent` | Group-scoped spatial signature, evidence and contributing raw-row IDs |
| `QueueSpectralSetup` | Group-scoped spectral signature, evidence and contributing raw-row IDs |
| `QueueRequestContext` | Group-scoped requested resolution/LAS/array/polarization evidence and source rows |
| `QueueRowAssociation` | Raw-row ID, group key and exactly one ID for each of the three component types |
| `QueueFactorizationSummary` | Observed/potential pair counts and repeated associations; creates no missing pair |

Every accepted input row yields exactly one association. Component factorization
must preserve this membership, including exported duplicate rows. Scientific
comparison starts with an association, not independent component inventories.
The [sparse-group evidence](evidence/exploration_snapshots.md#queue-sparse-associations)
explains why a Cartesian product is unsafe.

`QueueSpectralSetup.evidence` is `RegularSpwEvidence | SpectralScanEvidence`.
Regular windows retain source slot numbers and independent nominal/usable
coverage evidence. SPS is not expanded into invented windows. The
[regular/SPS parsing rules](queue_csv_contract.md#regular-spw-representation) and
[frequency derivation contract](queue_csv_contract.md#frequency-and-velocity-normalization)
own the formulas, tolerances and units; this object index does not redefine them.

### Component signatures

Component signatures are internal, deterministic, versioned identifiers. They
are not ALMA identifiers.

A spatial signature includes its group scope and exact raw spatial values. A
spectral signature includes its group scope, velocity context, sky/rest flag,
the complete regular-SPW collection or SPS record, and the requested
sensitivity triple. A request-context signature includes requested angular
resolution, requested LAS, array flags, and polarization.

Raw strings are used for identity signatures. Normalized floating-point values
are used for scientific calculations but must not become identity merely after
rounding. Each signature records its algorithm version.

Input row order may not change the set of reconstructed component signatures
or the multiset of logical associations. Raw-row IDs still reflect physical
line provenance and therefore remain row-specific.

### Persistence boundary

`StoredQueueSource` and `StoredQueueRun` are separate from the in-memory
`QueueSnapshot` and full parse result. Source records preserve bytes/acquisition
facts; run records preserve historical summaries. Reading a run does not restore
historical Python evidence objects. Explicit reparse returns current evidence
and creates a new run. The [storage contract](queue_snapshot_store.md) owns
publication, integrity, versions and runnable examples.

## Comparison references and evidence

`ComparisonPreparation` retains request validation and separate Archive/Queue
source results. Each `ComparisonSourceResult` retains the original source
record plus its contexts/status. Payloads reference source-specific objects
rather than copying them into a second scalar schema:

- `ArchiveContextEvidence`: prepared row, reconstruction result, support mapping,
  full support evidence and optional selected component.
- `QueueContextEvidence`: typed source row and its real association.

Archive rows with the same association remain alternative contexts. Per-window
RMS is not borrowed from another window or inferred from a colocated row scalar;
Queue reference RMS is not copied into every SPW. The
[comparison contract](comparison_contexts.md) owns exact builder behavior,
evidence dimensions, provenance and independent source-failure handling.

`EvidenceReference.source_record_id` is an Archive query-run ID or Queue checksum.
It is not a Queue acquisition identity. Acquisition and parse-run IDs currently
remain `None`; callers keep storage records separately until explicit binding
exists. These are in-memory views, not a historical deserialization format.

## Search and spatial use of contexts

`SearchPlan` holds the validation and source-specific operations, including
skipped predicates and a retained result limit. `QueryPlanBinding` checks an
Archive query record against the plan; it does not replace source completeness.
`SpatialEvidence` references the original context and source result, with
separate center and footprint states. `PositionInterpretation` binds explicit
frame/target interpretation to one context and a decision reference.

The [search/spatial contract](search_plan_spatial.md) owns limited `CIRCLE ICRS`
parsing, supported center units, Queue interpretation, unsupported geometry,
individual angular/spatial predicates and numerical boundary handling. Planning
and individual checks do not orchestrate a complete search or implement a
primary-beam policy. Status meanings and the next service delivery are centralized
in the [documentation guide](README.md#current-capabilities-and-status-meanings).

## Invariants across layers

1. Preserve raw source values, unit declarations, missing states, diagnostics and
   provenance; normalization never overwrites evidence.
2. Keep query/file completeness separate from request validity, query binding,
   selection and formal evaluability. Technical failure is not non-duplication.
3. Use observed row/component associations only. Do not synthesize missing pairs,
   combine unrelated source/execution/SPW evidence or choose favorable alternatives.
4. Keep row identities distinct from analytical grouping, exported content
   fingerprints, source acquisitions and physical downloadable products.
5. Keep independent frequency roles, nominal/usable coverage, spacing/resolution/
   noise bandwidth and RMS scope separate. Unit conversion alone does not prove
   cross-source reference or sensitivity compatibility.
6. Preserve `s_resolution` separately from `spatial_resolution`; neither is a
   measured FITS restoring beam. Archive sensitivity summaries are estimated
   metadata, not achieved QA2 image RMS.
7. Keep project classification, science-row role, QA2 state and correlator mode
   separate. No mode follows from `type`, `em_xel`, bandwidth or resolution alone;
   no single mode is assigned to every Member SPW. QA2 is not an implicit gate.
8. Preserve raw geometry and unsupported states. A polygon does not prove mosaic
   membership, a mosaic need not have one geometry family, and a valid region
   does not establish individual pointing identities or an approved beam method.
9. Keep derivation/signature versions with evidence. Determinism concerns logical
   associations; raw row identity retains query/source-line provenance.
10. Never turn missing, ambiguous, unsupported or unevaluated evidence into silent
    candidate exclusion or a negative formal conclusion.

Numeric conversions, sentinel handling and projection details are owned by the
[Archive client/dictionary](archive_data_dictionary.md#cross-field-constraints)
and [Queue contract](queue_csv_contract.md). Formal thresholds remain in the
[rule design](duplication_rule_inputs.md), outside ingestion/reconstruction.

## Design, evidence and deferred work

- [Conceptual ERDs and entity descriptions](design/conceptual_data_model.md): original design scopes and rationale.
- [Historical exploration evidence](evidence/exploration_snapshots.md): capture dates, sample populations, counterexamples and limits.
- [Rule-input decision register](duplication_rule_inputs.md#7-scientific-decision-register): unresolved formal scientific methods.
- [Next delivery](README.md#next-delivery): candidate service integration using these existing objects.

General STC-S/pointing reconstruction, physical-target alias resolution,
configuration-backed mode evidence, brace token-2 discrimination, physical-file
identity and durable Archive evidence serialization remain outside this runtime
model. New grammars or cardinality counterexamples can motivate targeted source
work; historical structure exploration is not a prerequisite to redoing this model.

## Previous section links

Existing deep links remain available below. Each points to the single current
owner or the moved design/evidence section; the old body is not duplicated.

| Previous section | Current location |
| --- | --- |
| <a id="search-and-spatial-objects"></a>Search and spatial objects | [Read section](#search-and-spatial-use-of-contexts) |
| <a id="archive-implementation-scope"></a>Archive implementation scope | [Read section](#archive-identities-and-associations) |
| <a id="historical-exploration-evidence-summary"></a>Historical exploration evidence summary | [Read section](evidence/exploration_snapshots.md#archive-exploration-summary) |
| <a id="modeling-principles"></a>Modeling principles | [Read section](#invariants-across-layers) |
| <a id="entity-relationship-model"></a>Entity-relationship model | [Read section](design/conceptual_data_model.md#entity-relationship-model) |
| <a id="complete-relationship-overview"></a>Complete relationship overview | [Read section](design/conceptual_data_model.md#complete-relationship-overview) |
| <a id="project-dataset-and-raw-query-provenance"></a>Project, dataset, and raw-query provenance | [Read section](design/conceptual_data_model.md#project-dataset-and-raw-query-provenance) |
| <a id="source-execution-alias-and-footprint-context"></a>Source, execution, alias, and footprint context | [Read section](design/conceptual_data_model.md#source-execution-alias-and-footprint-context) |
| <a id="spectral-structure-support-parsing-and-row-reconstruction"></a>Spectral structure, support parsing, and row reconstruction | [Read section](design/conceptual_data_model.md#spectral-structure-support-parsing-and-row-reconstruction) |
| <a id="conceptual-entity-definitions-and-implementation-notes"></a>Conceptual entity definitions and implementation notes | [Read section](design/conceptual_data_model.md#conceptual-entity-definitions-and-implementation-notes) |
| <a id="project"></a>`PROJECT` | [Read section](design/conceptual_data_model.md#project) |
| <a id="group_ous"></a>`GROUP_OUS` | [Read section](design/conceptual_data_model.md#group_ous) |
| <a id="member_ous"></a>`MEMBER_OUS` | [Read section](design/conceptual_data_model.md#member_ous) |
| <a id="asdm_execution"></a>`ASDM_EXECUTION` | [Read section](design/conceptual_data_model.md#asdm_execution) |
| <a id="source_context-and-source_alias"></a>`SOURCE_CONTEXT` and `SOURCE_ALIAS` | [Read section](design/conceptual_data_model.md#source_context-and-source_alias) |
| <a id="source_exec_context"></a>`SOURCE_EXEC_CONTEXT` | [Read section](design/conceptual_data_model.md#source_exec_context) |
| <a id="spatial_footprint"></a>`SPATIAL_FOOTPRINT` | [Read section](design/conceptual_data_model.md#spatial_footprint) |
| <a id="logical_spw"></a>`LOGICAL_SPW` | [Read section](design/conceptual_data_model.md#logical_spw) |
| <a id="source_spw_association"></a>`SOURCE_SPW_ASSOCIATION` | [Read section](design/conceptual_data_model.md#source_spw_association) |
| <a id="frequency_support_signature"></a>`FREQUENCY_SUPPORT_SIGNATURE` | [Read section](design/conceptual_data_model.md#frequency_support_signature) |
| <a id="frequency_support_component"></a>`FREQUENCY_SUPPORT_COMPONENT` | [Read section](design/conceptual_data_model.md#frequency_support_component) |
| <a id="spw_support_map"></a>`SPW_SUPPORT_MAP` | [Read section](design/conceptual_data_model.md#spw_support_map) |
| <a id="observation_mode_evidence"></a>`OBSERVATION_MODE_EVIDENCE` | [Read section](design/conceptual_data_model.md#observation_mode_evidence) |
| <a id="archive_query_run"></a>`ARCHIVE_QUERY_RUN` | [Read section](design/conceptual_data_model.md#archive_query_run) |
| <a id="raw_archive_row"></a>`RAW_ARCHIVE_ROW` | [Read section](design/conceptual_data_model.md#raw_archive_row) |
| <a id="row_product_metadata"></a>`ROW_PRODUCT_METADATA` | [Read section](design/conceptual_data_model.md#row_product_metadata) |
| <a id="row_reconstruction"></a>`ROW_RECONSTRUCTION` | [Read section](design/conceptual_data_model.md#row_reconstruction) |
| <a id="physical_target"></a>`PHYSICAL_TARGET` | [Read section](design/conceptual_data_model.md#physical_target) |
| <a id="key-and-cardinality-rules"></a>Key and cardinality rules | [Read section](#invariants-across-layers) |
| <a id="enforced-application-rules"></a>Enforced application rules | [Read section](#invariants-across-layers) |
| <a id="forbidden-assumptions"></a>Forbidden assumptions | [Read section](#invariants-across-layers) |
| <a id="field-projection-representation-and-conceptual-ownership"></a>Field projection, representation and conceptual ownership | [Read section](archive_data_dictionary.md#field-projection-representation-and-conceptual-ownership) |
| <a id="numerical-and-normalization-rules"></a>Numerical and normalization rules | [Read section](archive_data_dictionary.md#cross-field-constraints) |
| <a id="evidence-levels"></a>Evidence levels | [Read section](evidence/exploration_snapshots.md#evidence-labels) |
| <a id="archive-production-implementation-contract"></a>Archive production implementation contract | [Read section](#archive-identities-and-associations) |
| <a id="queue-reconstruction-extension-v1"></a>Queue reconstruction extension v1 | [Read section](#queue-row-associations) |
| <a id="explicitly-deferred-work"></a>Explicitly deferred work | [Read section](#design-evidence-and-deferred-work) |
| <a id="semantic-source-references"></a>Semantic-source references | [Read section](archive_data_dictionary.md#semantic-source-references) |
