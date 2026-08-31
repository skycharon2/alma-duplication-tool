# Archive TAP Client Completeness and Field-Metadata Contract

## Purpose

The Archive client retrieves candidate evidence from the ALMA Science Archive
without applying duplication-policy decisions. It converts one spatial search
into a traceable COUNT-and-retrieval run, verifies that the response is usable,
and permits normalization and reconstruction only when completeness is proven.

An incomplete or technically invalid Archive response must never support a
negative duplication conclusion.

## Scope

The client is responsible for:

- validating spatial query parameters;
- constructing COUNT and retrieval ADQL from one shared predicate;
- executing TAP queries with explicit MAXREC values;
- preserving declared columns, ordered VOTable field descriptors, raw scalar
  values, masks, and warnings;
- inspecting TAP `QUERY_STATUS`;
- reconciling expected and retrieved row counts;
- validating the versioned required-column contract;
- recording query provenance; and
- gating normalization and reconstruction on completeness.

The client does not:

- query or normalize the current-cycle CSV;
- classify candidates as duplicates;
- implement Appendix A thresholds;
- resolve physical target aliases;
- reconstruct individual mosaic pointings; or
- infer missing observations from incomplete results.

## Query sequence

One `ArchiveClient.search()` call performs:

1. local validation of `ArchiveQuerySpec`;
2. construction of COUNT and retrieval ADQL using the same WHERE clause;
3. COUNT execution with `MAXREC=1`;
4. COUNT response and `total_matches` validation;
5. retrieval with the configured explicit MAXREC;
6. ordered retrieval field-metadata capture and declared-schema validation;
7. retrieval `QUERY_STATUS` validation;
8. COUNT/retrieval reconciliation; and
9. construction of one immutable `ArchiveQueryResult` containing the
   retrieval field metadata.

The retrieval query uses an explicit projection. It does not use `SELECT *` or
Notebook-style exploratory `TOP` limits.

## Final statuses

| Status | Meaning | May enter reconstruction? |
|---|---|---:|
| `COMPLETE` | `QUERY_STATUS=OK` and expected count equals retrieved count | Yes |
| `OVERFLOW` | TAP explicitly reported a truncated retrieval | No |
| `COUNT_MISMATCH` | TAP reported OK but COUNT and retrieval differ | No |
| `ERROR` | Service, query, response, count, schema, or status validation failed | No |

A valid empty result is:

```text
expected_count = 0
retrieved_count = 0
QUERY_STATUS = OK
declared schema = complete
status = COMPLETE
```

Zero rows alone are not proof of a complete negative result.

## Structured error kinds

`ERROR` results include one `ArchiveQueryErrorKind`:

| Error kind | Meaning |
|---|---|
| `SERVICE_ERROR` | Network, HTTP, availability, or other service-access failure |
| `QUERY_ERROR` | TAP rejected or could not execute the submitted query |
| `RESPONSE_FORMAT_ERROR` | A returned VOTable/table could not be converted safely |
| `INVALID_COUNT` | COUNT was missing, negative, non-integral, multi-row, or otherwise unusable |
| `SCHEMA_DRIFT` | One or more versioned required columns were absent |
| `UNKNOWN_QUERY_STATUS` | `QUERY_STATUS` was missing or not recognized |

Partial rows may be retained for diagnostics, but `can_reconstruct` remains
false for every non-complete result.

## Schema contract

`ARCHIVE_SCHEMA_VERSION` versions the retrieval projection and required-column
set. Schema validation uses `TapResponse.declared_columns`, not keys from the
first data row. This permits a zero-row table to prove that it still satisfies
the expected schema.

The current projection contains the Project, Member, execution, identifier,
spatial, spectral, normalization, and observation-role fields required by the
v0.4 adapter and reconstruction model. Raw Archive field names, including
`lastModified`, are preserved at ingestion.

Each `TapResponse` also contains one ordered `TapFieldMetadata` descriptor per
declared column. The descriptor preserves the source-reported `name`,
`datatype`, `arraysize`, `unit`, `ucd`, `utype`, `xtype`, and `description` as
exposed by PyVO. Optional attributes remain `None` when absent. Descriptor
names must exactly match `declared_columns` in response order; a mismatch is a
`RESPONSE_FORMAT_ERROR` rather than silently associating metadata with the
wrong value column.

Field descriptors come from the VOTable `FIELD` definitions and therefore
remain available for a valid zero-row response. `ArchiveQueryResult` preserves
the retrieval descriptors for `COMPLETE`, `OVERFLOW`, `COUNT_MISMATCH`, and
errors that received a retrieval response. Failures before retrieval have an
empty metadata tuple. COUNT response metadata remains available at the
executor boundary but is not substituted for retrieval metadata.

Missing fields produce:

```text
status = ERROR
error_kind = SCHEMA_DRIFT
missing_columns = (...)
```

They must not be allowed to fail later as an unstructured Pandas or mapping
`KeyError`.

## Query provenance

Every success and failure path records:

- query-run identifier;
- endpoint;
- COUNT ADQL;
- retrieval ADQL;
- normalized parameters;
- configured MAXREC;
- start and finish timestamps;
- expected and retrieved counts when available;
- raw COUNT and retrieval query statuses;
- warnings;
- query hash;
- client version; and
- schema version.

The query hash identifies the endpoint and exact COUNT/retrieval text. It is
technical provenance, not an Archive entity identifier.

## TAP boundary

`PyvoTapExecutor` is the only production component that depends on PyVO result
and exception classes. It converts PyVO rows and `fielddescs` into
source-neutral `TapResponse` objects and converts recognized DAL failures into
structured `TapExecutionError` values. Metadata text is not passed through
Archive row normalization or parser logic.

`ArchiveClient` depends on the `TapExecutor` protocol. This permits the live
executor to be replaced with `FakeTapExecutor` in local and CI tests.

## Adapter and reconstruction gate

`run_archive_pipeline()` accepts only a query result for which:

```python
result.can_reconstruct is True
```

For each accepted raw row it:

1. assigns an internal row ID scoped to query run and result index;
2. preserves the complete raw mapping;
3. creates `ArchiveMetadataInput` and normalization results;
4. creates the minimal `ArchiveRowInput` projection; and
5. invokes deterministic reconstruction.

The raw mapping is not overwritten by normalized or parsed values. Input row
order is preserved in `prepared_rows`; reconstruction remains canonical under
shuffled reconstruction inputs.

## Test boundary

Ordinary unit and integration tests are offline:

- query-builder tests are pure;
- PyVO adapter tests inject a fake service;
- client tests use scripted `TapResponse` objects;
- the pipeline integration test loads a small local ECSV fixture; and
- incomplete-result gates are tested without a live network.

The opt-in live ALMA TAP smoke tests are marked `live`, skipped by default, and
run only in the manual workflow. They exercise the current service through
reconstruction without blocking ordinary pull-request checks, because service
availability and Archive contents can change.
