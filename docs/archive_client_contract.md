# Archive TAP Client Completeness and Field-Metadata Contract

## Purpose

The Archive client retrieves candidate evidence from the ALMA Science Archive
without applying duplication-policy decisions. It converts one spatial search
into a traceable COUNT-and-retrieval run, verifies that the response is usable,
and permits normalization and reconstruction only when completeness is proven.

An incomplete or technically invalid Archive response must never support a
negative duplication conclusion. A complete response whose scientific units
cannot be validated may still support structural reconstruction, but its
affected values cannot enter scientific comparison.

## Scope

The client is responsible for:

- validating spatial and optional broad spectral/resolution query parameters;
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
2. when numeric bounds were requested, a prefilter-specific `TAP_SCHEMA`
   unit probe for frequency/bandwidth and/or angular resolution;
3. construction of COUNT and retrieval ADQL using the same effective WHERE
   clause;
4. COUNT execution with `MAXREC=1`;
5. COUNT response and `total_matches` validation;
6. retrieval with the configured explicit MAXREC;
7. ordered retrieval field-metadata capture and declared-schema validation;
8. retrieval `QUERY_STATUS` validation;
9. COUNT/retrieval reconciliation; and
10. construction of one immutable `ArchiveQueryResult` containing the
   retrieval field metadata.

The retrieval query uses an explicit projection. It does not use `SELECT *` or
Notebook-style exploratory `TOP` limits.

## Broad candidate prefilters

Every search has an ICRS spatial predicate. A caller may also supply a
frequency interval in GHz and/or an angular-resolution interval in arcsec.
Before constructing either data query, the client reads only the arithmetic
field descriptors required by that request from `TAP_SCHEMA.columns`.

The frequency predicate is enabled only when the service reports exactly
`frequency=double/GHz` and `bandwidth=double/Hz`. COUNT and retrieval then use
the same strict overlap predicate:

```text
frequency - bandwidth / 2 < requested maximum
frequency + bandwidth / 2 > requested minimum
```

The ADQL converts Archive `bandwidth` from Hz to GHz before applying this
predicate. Rows with NULL `frequency` or `bandwidth` are retained so missing
comparison evidence can become `NOT_EVALUABLE` locally rather than a false
candidate absence.

The angular-resolution predicate is enabled only when the service reports
exactly `spatial_resolution=double/arcsec`. Rows with missing
`spatial_resolution` are retained by that prefilter.

If the metadata query fails, is incomplete, or reports different units, each
requested numeric prefilter is disabled independently and the reason is
recorded. For example, verified frequency units may still permit frequency
filtering when the angular unit mismatches. If neither numeric prefilter is
safe, the effective query is spatial-only. Compatible conversion of values
after retrieval never authorizes unsafe server-side arithmetic.

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
adapter and reconstruction model. It explicitly includes the public
`em_xel` spectral-axis element count. Raw Archive field names, including
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

### Comparison-field unit contract

Six fields have an additional runtime contract. The current VOTable datatype
for each is `double`:

| Field | Expected live unit | Canonical unit |
|---|---|---|
| `frequency` | GHz | GHz |
| `bandwidth` | Hz | GHz |
| `spectral_resolution` | kHz | kHz |
| `spatial_resolution` | arcsec | arcsec |
| `sensitivity_10kms` | mJy/beam | mJy/beam |
| `cont_sensitivity_bandwidth` | mJy/beam | mJy/beam |

Compatible unit changes are converted through Astropy and reported as
`COMPATIBLE_CONVERSION`. Missing metadata, datatype drift, missing units, and
dimensionally incompatible units fail closed for the affected quantity. The
adapter never treats a bare float as GHz, Hz, kHz, arcsec, or mJy/beam merely
because of its column name.

All six physical quantities must also be finite and strictly greater than
zero. Frequency coverage is exposed only when its converted bounds satisfy
`0 < lower_ghz < upper_ghz`; otherwise the quantities and an explicit invalid-
interval issue are retained, but the interval is unavailable.

### Correlator-mode evidence boundary

TAP does not expose a direct, policy-grade FDM/TDM field. The selected
`em_xel` column is preserved in each raw Archive row, but the production
adapter does not classify it as `CONTINUUM`/`LINE` and does not map it to
TDM/FDM. Channel count alone is not a reliable correlator-mode discriminator
across polarization, online averaging, processor, and historical setup
variants.

Consequently, `PreparedArchiveRow` and `ArchivePipelineBatch` expose no
channel-count-derived mode evidence. Until a separately validated configuration
source is implemented and reliably associated with a candidate SPW, formal
correlator mode remains unavailable to the policy layer. Unavailable mode must
not satisfy an FDM requirement and must not exclude a candidate. Production
code does not call the undocumented Archive Elasticsearch endpoint.

## Query provenance

Every success and failure path records:

- query-run identifier;
- endpoint;
- COUNT ADQL;
- retrieval ADQL;
- normalized parameters;
- configured MAXREC;
- separate frequency and angular-resolution unit-gate statuses and the
  relevant `TAP_SCHEMA` descriptors;
- start and finish timestamps;
- expected and retrieved counts when available;
- raw COUNT and retrieval query statuses;
- warnings;
- query hash;
- client version; and
- schema version.

The query hash identifies the endpoint, exact COUNT/retrieval text, both
unit-gate statuses, and captured arithmetic-field descriptors. It is technical
provenance, not an Archive entity identifier.

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

1. interprets the response VOTable `obs_id` datatype and `arraysize` once,
   preserving bounded, fixed, unbounded, missing, invalid, and incompatible
   metadata states;
2. assigns an internal row ID scoped to query run and result index;
3. preserves the complete raw mapping;
4. creates `ArchiveMetadataInput` and normalization results;
5. validates the live comparison-field unit contract once per result;
6. preserves `em_xel` only inside the complete raw row without interpreting
   it as an Archive UI type or correlator mode;
7. creates typed Archive comparison evidence for each row;
8. creates the minimal `ArchiveRowInput` projection using the typed
   frequency's canonical GHz value;
9. invokes deterministic reconstruction with the same per-result `obs_id`
   width contract.

The current response FIELD descriptor and the historically observed
64-character truncation boundary are separate evidence. For VOTable character
fields, `N*` supplies a reported maximum and `*` is unbounded. Missing or
invalid live metadata is never silently replaced by 64. Complete identifiers
above a reported maximum retain schema-drift diagnostics but may proceed to
Member/source/SPW cross-checks; identifiers exactly at the historical boundary
remain unsafe even if the current response reports a larger maximum.

Direct calls to `reconstruct_archive_rows()` have no live FIELD descriptor.
They therefore receive an explicit `DIRECT_RECONSTRUCTION_FALLBACK` contract
with non-evaluable live width while retaining the independent historical
boundary. Both the width-contract version and reconstruction version are
stored in the returned batch for replay and audit.

The typed projection keeps the raw value, source unit, canonical value/unit,
field/query provenance, and an availability status. It distinguishes Archive
line sensitivity at 10 km/s from aggregate-bandwidth continuum sensitivity;
both are labelled QA0-EB-metadata calculator estimates, not achieved FITS RMS.

Reconstruction never reads the raw `frequency` float directly. If TAP returns
a compatible changed unit such as MHz, typed evidence converts the value to
GHz before frequency-support mapping. If the source unit is missing or
incompatible, the reconstruction frequency is unavailable rather than guessed
from the column name.

The Archive manual calls `frequency` a sky frequency but does not identify a
public comparison-ready reference frame for the TAP value. Typed frequency
coverage therefore carries `SKY_FREQUENCY_FRAME_UNSPECIFIED`, and cross-source
frequency readiness remains false until an approved Archive--Queue frame
mapping exists.

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
reconstruction and separately verify both numeric-prefilter unit gates without
blocking ordinary pull-request checks, because service availability and Archive
contents can change.

## Official references

- [ALMA query by frequency notebook](https://almascience.eso.org/alma-data/archive/archive-notebooks/nb6_ALMA_Query_by_frequency.html)
- [ALMA query by sensitivity notebook](https://almascience.eso.org/alma-data/archive/archive-notebooks/nb7_ALMA_Query_by_sensitivity.html)
- [Cycle 13 Science Archive Manual](https://almascience.eso.org/documents-and-tools/cycle13/science-archive-manual)
