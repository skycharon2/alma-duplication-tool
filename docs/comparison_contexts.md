# Comparison context construction

Version 1 implements offline context construction over existing ingestion
outputs. It binds a validated request to **unfiltered source contexts**. It does
not retrieve candidates, execute SearchOptions predicates or assess duplication.

## Entry points

`alma_duplicate.comparison` provides:

- `build_archive_contexts(ArchivePipelineBatch | ArchiveQueryResult | None)`
- `build_queue_contexts(QueuePipelineBatch | QueueCsvParseResult | None)`
- `prepare_comparison(validation, *, archive=None, queue=None)`

The combined entry requires a valid
[request validation result](proposed_observation_api.md) with a request object.
A valid partial request is allowed even if its search readiness is not READY:
construction does not execute a search. Existing pipeline batches are reused;
complete query/parse results are passed through the existing ingestion adapters.
No network call, database, acquisition ID or parse-run ID is required.

Source results retain the original query result or Queue parse result, including
diagnostics, metadata and provenance. Inputs are trusted in-process pipeline
objects, not a deserialization format; builders additionally reject duplicate,
missing or inconsistent row/component references. They do not repeat every
ingestion numeric validation for arbitrarily hand-constructed domain objects.

## Context identity and association

An Archive context represents one raw row with its prepared evidence, row
reconstruction, support mapping and complete support parse result. Only a unique
assigned reference from a valid support result selects a component. Candidate
references for ambiguous mappings and all parser diagnostics remain accessible.
The existing whole-support validity gate is preserved.

Rows with the same source–execution–SPW association remain separate contexts.
Each lists the other context IDs as alternatives. This conservatively flags
multiple records (including identical records); it does not select the first,
average values or claim to have resolved a conflict. Unlinked rows retain their
evidence and diagnostics without an invented association. Member OUS may be used
for display grouping; it is not a license to combine values across contexts.

A Queue context represents exactly one real `QueueRowAssociation` and its typed
source row. The builder verifies spatial, spectral and request component
membership against that row. It never takes a Cartesian product of factored
components. Equal content on different source lines remains distinct. Queue
evidence represents planned observations, not proof of execution.

## Evidence and states

The [model](../src/alma_duplicate/domain/comparison.py) retains source objects
instead of making a second scalar projection. `EvidenceItem.path` identifies
evidence inside the context payload; list indices are zero-based. Archive
`component_index` retains the parser's original index unchanged.

Each item separately reports:

| Dimension | Meaning in this implementation |
| --- | --- |
| numeric | Presence/validity inherited from typed ingestion; UNKNOWN when no safe numeric conclusion is available |
| unit | Existing canonical unit validation, or UNKNOWN for raw/component units not adapted here |
| association | Evidence belongs to the row/component, or its matched-SPW association is unverified |
| reference | UNKNOWN until reference compatibility is evaluated against another operand |
| method | NOT_IMPLEMENTED for formal comparison methods |

PRESENT is not a criterion pass or a cross-source compatibility result.
A row scalar `sensitivity_10kms` retains its own availability but has UNKNOWN
SPW association. It is never substituted for selected-component RMS.
Component RMS retains its original basis and units. Queue reference RMS remains
row/setup evidence with UNKNOWN per-SPW association; no value is copied to every
window. Unknown usable bandwidth remains MISSING without discarding nominal
coverage or the row. Missing RMS never becomes a frequency mismatch.

Within context construction, Archive spatial fields remain raw evidence and
Queue geometry is retained as supplied. The independent [spatial adapter and
individual selectors](search_plan_spatial.md#spatial-evidence) normalize supported
centers and parse limited `CIRCLE ICRS` footprints without changing this payload.
Formal comparison geometry methods and SPS expansion are not implemented.
No single `comparison_ready` Boolean is exposed.

## Provenance

Archive references include query-run ID, raw-row ID, spectral parser version,
reconstruction/adapter versions and selected component index when available.
The retained prepared evidence also carries normalization and unit provenance.

Queue references include checksum, portable raw-row ID and parser,
reconstruction and adapter versions. The source result retains snapshot dates,
source URL, schema metadata and diagnostics. Existing SPW derivations retain
their versions and inputs in the original row object.

Persistent acquisition and parse-run IDs remain None in this first API, including
when a caller obtained the parse result through a snapshot store. Store-record
binding is not implemented: the caller must retain those records separately.
A checksum is a content identity, never an invented acquisition identity.
These objects are in-memory views, not a historical serialization format.

## Source failure and completeness

Each source independently reports COMPLETE, INCOMPLETE, FAILED or NOT_PROVIDED.

- Archive overflow/count mismatch: INCOMPLETE, no contexts.
- Archive error: FAILED, original result retained.
- Queue parse failure: FAILED, no partial reconstruction; original diagnostics
  and all retained raw rows remain available.
- Invalid pipeline associations: FAILED with construction reasons.
- One source failure does not discard the other source's contexts.

COMPLETE only means context construction succeeded for the supplied complete
query/file. It says nothing about sky coverage, Queue grade/date coverage or
whether that input query corresponds to the bound request. Query ADQL,
prefilter/projection decisions and Queue source dates remain in source records.
No predicates are executed or inferred from SearchOptions, including its sources
selection. The caller supplies the sources to prepare.

`search_execution = NOT_EXECUTED` and `assessment = NOT_EVALUATED` remain explicit,
including for zero contexts. This API never emits a negative duplication verdict.

## Offline acceptance and next boundary

[Connection tests](../tests/integration/test_comparison_contexts.py) verify
selected-window RMS, conservative unsafe mapping, alternative Archive rows,
Queue observed combinations, missing RMS, broken associations, incomplete
sources and invalid requests using existing local fixtures. These are structural
tests, not CASE1/CASE2 retrieval verification or approved policy calculations.

Offline search planning and limited spatial adaptation are implemented; see the
[search-plan and spatial-evidence contract](search_plan_spatial.md). The
[next delivery](README.md#next-delivery) connects Archive execution and Queue
local selection to an explicit execution and completeness report. CASE retrieval
verification and formal duplication assessment remain separate work.
