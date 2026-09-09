# ALMA Archive Data Dictionary

## Purpose

Reference dictionary for 73 historically surveyed columns in the public ALMA
`ivoa.obscore` TAP view. Production uses the projection below, not all 73
columns. It consolidates
evidence from Notebooks 01 through 04c and records:

- the service type and unit;
- the internal owner or engineering role;
- mandatory normalization and validation behavior; and
- cross-field constraints established by Notebooks 01–04b.

It is not the official internal ALMA database schema. Raw TAP values always
remain authoritative evidence; normalized and derived values are versioned
projections.

## Production projection v1 (schema 3, client 7)

Core fields are always queried and required in response FIELD metadata, even
for zero-row results. Missing core fields trigger a schema error. Required
column presence does not imply non-NULL cells: existing parsers and quantity
validators retain missing/invalid states. Optional fields are queried only
after schema confirmation and are not required for core completeness.
All returned values and FIELD descriptors remain raw evidence alongside the
existing projections below.

| Field | Purpose | Query / required | Existing projection | Scope and limits |
| --- | --- | --- | --- | --- |
| `proposal_id` | Project identity | Core / yes | Metadata normalization | Project grouping; no universal physical-product identity |
| `obs_publisher_did` | Publisher/project cross-check | Core / yes | Metadata normalization | Project grouping; no universal physical-product identity |
| `group_ous_uid` | Group identity | Core / yes | Metadata normalization | Observed reconstruction keys; grouping does not authorize mixing evidence |
| `member_ous_uid` | Member association | Core / yes | Reconstruction text input | Observed reconstruction keys; grouping does not authorize mixing evidence |
| `asdm_uid` | Execution identity | Core / yes | Reconstruction text input | Observed reconstruction keys; grouping does not authorize mixing evidence |
| `obs_id` | Identifier grammar and association | Core / yes | Versioned identifier parser | Observed reconstruction keys; grouping does not authorize mixing evidence |
| `target_name` | Source label | Core / yes | Raw only | Source context, not globally resolved physical target |
| `s_ra` | Position evidence | Core / yes | Raw ingestion; independent unit-checked spatial normalization | Unit-checked center normalization and limited `CIRCLE ICRS` parsing implemented; no general STC-S family parser or formal beam-coverage method |
| `s_dec` | Position evidence | Core / yes | Raw ingestion; independent unit-checked spatial normalization | Unit-checked center normalization and limited `CIRCLE ICRS` parsing implemented; no general STC-S family parser or formal beam-coverage method |
| `s_region` | Footprint and spatial search | Core / yes | Raw ingestion; server predicate; separate limited [spatial parser](search_plan_spatial.md#spatial-evidence) | Unit-checked center normalization and limited `CIRCLE ICRS` parsing implemented; no general STC-S family parser or formal beam-coverage method |
| `frequency` | Frequency centre | Core / yes | Unit-validated quantity | Row/SPW association subject to mapping; not independently verified usable coverage |
| `bandwidth` | Coverage | Core / yes | Unit-validated quantity | Row/SPW association subject to mapping; not independently verified usable coverage |
| `em_xel` | Channel count | Core / yes | Raw; no mode inference | No production classifier; SPW granularity must be established before future classification |
| `frequency_support` | Full spectral description | Core / yes | Complete spectral parse evidence | Includes component intervals, diagnostics and independent RMS entries |
| `spectral_resolution` | Spectral comparison | Core / yes | Unit-validated quantity | Does not substitute for channel spacing or effective noise bandwidth |
| `spatial_resolution` | Angular comparison | Core / yes | Unit-validated quantity | Initial angular-resolution prefilter; not a measured restoring beam |
| `sensitivity_10kms` | Line sensitivity estimate | Core / yes | Unit-validated quantity | Representative-window association must be established before use for a matched SPW; row co-location is insufficient |
| `cont_sensitivity_bandwidth` | Continuum sensitivity estimate | Core / yes | Unit-validated quantity | Preserve aggregate basis; not achieved image RMS |
| `antenna_arrays` | Array description | Core / yes | Raw only | No automatic complete array/geometry interpretation |
| `is_mosaic` | Observation context | Core / yes | Flag normalization | Source declaration; not a reconstructed pointing list |
| `science_observation` | Science context | Core / yes | Flag normalization; server predicate | Query policy is explicit; QA2 is not an implicit filter |
| `qa2_passed` | QA context | Core / yes | Flag normalization | Query policy is explicit; QA2 is not an implicit filter |
| `obs_release_date` | Release provenance | Core / yes | Timestamp normalization | Sentinel/missing handling remains source-specific |
| `lastModified` | Modification provenance | Core / yes | Timestamp normalization | Sentinel/missing handling remains source-specific |
| `s_resolution` | Independent resolution cross-check | Optional / no | Raw; never replaces spatial_resolution | Independent cross-check; never alias to spatial_resolution |
| `s_fov` | Field of view | Optional / no | Raw only | Auxiliary coverage evidence; not a verified beam or footprint |
| `t_min` | Observation start bound | Optional / no | Raw; no date conversion | Auxiliary time evidence; retained within originating row |
| `t_max` | Observation end bound | Optional / no | Raw; no date conversion | Auxiliary time evidence; retained within originating row |
| `band_list` | Band description | Optional / no | Raw only | Auxiliary source metadata, not validated comparison context |
| `pol_states` | Polarization description | Optional / no | Raw; no mode inference | Auxiliary source metadata, not validated comparison context |

Optional absence is recorded as NOT_REQUESTED, NOT_IN_SCHEMA, or
SCHEMA_UNAVAILABLE; selected-but-unreturned is SELECTED with returned=False.
A returned NULL remains an actual cell. No absent column is filled with None.
Projection decisions survive zero-row and incomplete results on provenance.
Unknown returned scalar columns and their descriptors remain unnormalized.
Mutable array cells remain outside the immutable raw-row contract.

## Field projection, representation and conceptual ownership

The single projection inventory above owns selection and representation for all
core/optional fields. It incorporates the former data-model field table.
“Typed” means a dedicated normalized representation exists, not that a value is
present, valid, unambiguously associated or ready for comparison. Unknown returned
scalar fields may remain raw without receiving typed semantics.

| Additional field/value | Current treatment |
| --- | --- |
| `type` | Not selected; historical project classification, not observing mode |
| Source parsed from `obs_id` | Derived source candidate; not a globally resolved physical target |
| Parsed support component | Full parser evidence plus row/parser-scoped reference; only safe unique mapping selects a component |
| `em_min`, `em_max`, `em_resolution`, `velocity_resolution` | Not selected; historical cross-checks do not establish production validation |
| Other axis/access metadata | Not selected by default; conceptual product ownership does not imply routine retrieval or physical-file identity |
| Duplication result | Planned policy-layer output, not a source field or reconstruction result |

Selection is defined by [archive_queries.py](../src/alma_duplicate/clients/archive_queries.py).
Exact quantity conversion and preparation are defined by
[archive_field_contract.py](../src/alma_duplicate/clients/archive_field_contract.py)
and [archive_adapter.py](../src/alma_duplicate/clients/archive_adapter.py).
Archive bandwidth and parsed-support width remain separate. Unlinked/ambiguous
evidence remains available; conceptual ownership never supplies a missing
representative-window relationship.

## Evidence snapshots

The [capture register](evidence/exploration_snapshots.md#archive-capture-register),
[exploration summary](evidence/exploration_snapshots.md#archive-exploration-summary)
and [cross-field experiments](evidence/exploration_snapshots.md#archive-cross-field-experiments)
retain dates, populations, schema checksum, samples and their limits. They are
historical evidence, not a current census. Production preserves raw `em_xel`
without inferring Archive UI classification or correlator mode.

## Implementation boundary

The production Archive client v7/schema v3 (projection v1) preserves row values, selected column names,
query status, warnings, COUNT/retrieval reconciliation, query provenance, and
the ordered retrieval VOTable field descriptors. For every projected field,
the runtime contract retains `name`, `datatype`, `arraysize`, `unit`, `ucd`,
`utype`, `xtype`, and `description`; absent optional attributes remain `None`.
The metadata tuple remains present for valid zero-row results and for
incomplete or erroneous results whenever a retrieval response was received.
It is tied to the same query result and capture time through provenance.

This is runtime evidence preservation, not durable database storage. A future
persistence layer must serialize these descriptors without changing their
column order or applying scientific-value normalization to their text.

## Ingestion contract

1. Store the complete raw row, Astropy mask state, query run, result ordinal,
   and ordered retrieval field metadata before normalization.
2. Give every raw row an internal surrogate `raw_row_id`.
3. Keep raw, normalized, parsed, and derived values separate.
4. Reconcile `COUNT(*)`, retrieved row count, and `QUERY_STATUS`; incomplete
   results cannot support a negative duplication conclusion.
5. Store only observed Source-Execution-SPW associations. Never synthesize a
   Source × SPW Cartesian product.
6. Version identifier, support, geometry, mapping, and normalization logic.
7. Preserve unsupported, ambiguous, masked, truncated, and malformed values
   with explicit statuses; do not silently drop their rows.

## Field catalogue

### Identity, hierarchy, and project classification — 8 fields

| Archive field | TAP type / unit | Internal owner | Required handling |
|---|---|---|---|
| `proposal_id` | `char` / — | `PROJECT` | Preserve raw. Current alternate project identifier with `obs_publisher_did`; not a row key. |
| `obs_publisher_did` | `char` / — | `PROJECT` | Validate `ADS/JAO.ALMA#<proposal_id>`. It is proposal-scoped, not a row, product, Member, ASDM, Source, SPW, or file identifier. |
| `type` | `char` / — | `PROJECT` classification evidence | Preserve raw. In the 2026-08-31 census, `S`, `L`, `T`, `V`, `SV`, `E`, `P`, and `CAL` exactly matched the terminal `proposal_id` suffix across 5,614 distinct pairs. Treat the value set as open, retain unknown values, and never interpret this field as science intent or FDM/TDM mode. |
| `group_ous_uid` | `char` / — | `GROUP_OUS` | Optional. Normalize blank to missing while retaining the raw blank. |
| `member_ous_uid` | `char` / — | `MEMBER_OUS` | Dataset grouping identifier. Do not equate a Member with one execution, observation, product, or row. |
| `asdm_uid` | `char` / — | `ASDM_EXECUTION` | Retain in the Source-Execution context; one Member may associate with multiple ASDMs. |
| `obs_id` | `char` / — | `RAW_ARCHIVE_ROW` + `ROW_RECONSTRUCTION` | Preserve raw text and length. Parse grammar independently from the current response FIELD datatype/`arraysize`. Record live maximum conformance separately from the historical 64-character truncation boundary. Complete grammar above a reported maximum may enter cross-field checks with a schema-drift diagnostic; a value exactly at the historical boundary remains unsafe. Never use as an Archive-wide key. |
| `target_name` | `char` / — | `SOURCE_ALIAS` / display | Preserve spelling and origin. Never use alone as physical-target identity. |

### Source-Execution and spatial context — 13 fields

| Archive field | TAP type / unit | Internal owner | Required handling |
|---|---|---|---|
| `s_ra` | `double` / deg | `SPATIAL_FOOTPRINT` | Representative ICRS RA. Normalize longitude only in a derived field. Coordinate equality is not target identity. |
| `s_dec` | `double` / deg | `SPATIAL_FOOTPRINT` | Representative ICRS Dec. Validate finite values and `[-90, 90]`. |
| `s_fov` | `double` / deg | `SPATIAL_FOOTPRINT` cross-check | Preserve as representative field-of-view evidence; not a footprint replacement. |
| `s_region` | `char` / — | `SPATIAL_FOOTPRINT` | Preserve raw STC-S. Parse current CIRCLE, POLYGON, and UNION families with unknown fallback. Execution-scoped. |
| `is_mosaic` | `char` / — | `SOURCE_EXEC_CONTEXT` | Normalize known `T`/`F`; preserve other values. Geometry family does not determine mosaic state. |
| `s_resolution` | `double` / arcsec | `SOURCE_EXEC_CONTEXT` cross-check | Preserve independently from `spatial_resolution`; no equality constraint. It is ObsCore evidence, not the primary ALMA candidate-query field. |
| `spatial_resolution` | `double` / arcsec | `SOURCE_EXEC_CONTEXT` | Primary Archive angular-resolution evidence for candidate retrieval. The service describes it as the average of maximum and minimum spatial-resolution values across SPWs. Treat it as approximate/derived metadata, not a measured FITS restoring beam, and keep it separate from `s_resolution`. |
| `spatial_scale_max` | `double` / arcsec | `SOURCE_EXEC_CONTEXT` cross-check | Maximum recoverable-scale evidence; optional for spatial policy. |
| `antenna_arrays` | `char` / — | `SOURCE_EXEC_CONTEXT` | Preserve raw pad:antenna pairs. Prefix-based array type is heuristic evidence, not authoritative classification. |
| `band_list` | `char` / — | `SOURCE_EXEC_CONTEXT` | Preserve receiver-band labels; never substitute for exact spectral coverage. |
| `gal_latitude` | `double` / deg | Derived spatial cross-check | Service-derived Galactic coordinate. Do not replace ICRS position. |
| `gal_longitude` | `double` / deg | Derived spatial cross-check | Service-derived Galactic coordinate. Do not replace ICRS position. |
| `pwv` | `float` / mm | Deferred environment evidence | Preserve for later sensitivity/quality analysis; not core candidate identity. |

### Spectral association and support — 13 fields

| Archive field | TAP type / unit | Internal owner | Required handling |
|---|---|---|---|
| `frequency` | `double` / GHz | `SOURCE_SPW_ASSOCIATION` | Exact row reference frequency. Require a finite value strictly greater than zero; keep separate from parsed support-component centre. |
| `bandwidth` | `double` / Hz | `SOURCE_SPW_ASSOCIATION` | Archive bandwidth. Require a finite value strictly greater than zero; keep separate from interval width and brace token 2. |
| `em_xel` | `int` / — | `RAW_ARCHIVE_ROW` diagnostic metadata | Preserve the raw spectral-axis element count without deriving Archive UI type or TDM/FDM. Channel count alone is not policy-grade correlator-mode evidence. |
| `frequency_support` | `char` / GHz | `FREQUENCY_SUPPORT_SIGNATURE` | Service declares GHz, but the raw composite embeds GHz, kHz, sensitivity, and polarization values. Preserve raw text; dispatch bracket/brace grammar and retain error states. The raw string does not expose a reliable per-SPW correlator mode; never infer one from string tokens, `em_xel`, bandwidth, resolution, or top-level `type`. |
| `spectral_resolution` | `double` / kHz | `SOURCE_SPW_ASSOCIATION` | Preserve independently from parsed component resolution and bandwidth. |
| `velocity_resolution` | `double` / m/s | `OBSERVATION_MODE_EVIDENCE` | Archive summary; do not replace with or require equality to a row-level derivation. |
| `em_resolution` | `double` / m | `OBSERVATION_MODE_EVIDENCE` | Wavelength-domain resolution cross-check. Compare only after explicit unit conversion. |
| `em_min` | `double` / m | Spectral cross-check | Lower wavelength bound. Use tolerance-aware conversion to frequency. |
| `em_max` | `double` / m | Spectral cross-check | Upper wavelength bound. Account for inverse wavelength/frequency ordering. |
| `em_res_power` | `double` / — | Spectral cross-check | Preserve resolving-power evidence; not primary SPW identity. |
| `sensitivity_10kms` | `double` / mJy/beam | `SOURCE_SPW_ASSOCIATION` | Estimated line sensitivity at a nominal 10 km/s bandwidth. It does not fully include flagging or Hanning-smoothing effects, and 10 km/s may not be achievable for every dataset. Keep it distinct from native and continuum sensitivity and do not label it achieved QA2 RMS. |
| `cont_sensitivity_bandwidth` | `double` / mJy/beam | `SOURCE_EXEC_CONTEXT` | Estimated noise over the aggregated continuum bandwidth. It does not fully include flagging or dynamic-range limitations. Keep it distinct from component-native and line sensitivity and do not label it achieved QA2 RMS. |
| `pol_states` | `char` / — | `SOURCE_SPW_ASSOCIATION` | Preserve raw polarization representation; allow future grammars. |

### Time, role, QA, and release — 10 fields

| Archive field | TAP type / unit | Internal owner | Required handling |
|---|---|---|---|
| `t_min` | `double` / d | `SOURCE_EXEC_CONTEXT` | Lower MJD temporal bound. Preserve service semantics; do not rename as an exact execution start. |
| `t_max` | `double` / d | `SOURCE_EXEC_CONTEXT` | Upper MJD temporal bound. Validate `t_max >= t_min` when both are present. |
| `t_exptime` | `double` / s | Cross-check | Exposure summary; not a unique execution duration. |
| `t_resolution` | `double` / s | Cross-check | Optional time-resolution evidence. |
| `science_observation` | `char` / — | Retrieval role | Normalize known `T`/`F`. Initial duplication search uses `T`; other roles remain a separate population. Its `T` value is unrelated to top-level `type = 'T'`. |
| `scan_intent` | `char` / — | Observation-role evidence | Preserve the complete raw intent list; do not collapse TARGET, calibration, CHECK, and WVR roles. |
| `data_rights` | `char` / — | Access metadata | Preserve raw state. Do not infer release from this field alone. |
| `qa2_passed` | `char` / — | QA metadata | Normalize known `T`/`F`; preserve missing or other states independently from access. Retain it as quality-state evidence, not a default ingestion filter. Any inclusion/exclusion rule belongs to explicit duplication policy. |
| `obs_release_date` | `char` / — | Release metadata | Parse into a derived timestamp. Classify `3000-01-01...` as a sentinel, not a real future date. |
| `lastModified` | `char` / — | Cache/query provenance | Parse separately as a timestamp for cache invalidation. Not scientific identity. |

### Row product and service metadata — 14 fields

| Archive field | TAP type / unit | Internal owner | Required handling |
|---|---|---|---|
| `dataproduct_type` | `char` / — | `ROW_PRODUCT_METADATA` | Current science rows are cube or image. Do not infer physical file count. |
| `calib_level` | `int` / — | `ROW_PRODUCT_METADATA` | Current science snapshot is level 2; service definition also permits other levels. Do not encode level 2 as permanent. |
| `access_url` | `char` / — | `ROW_PRODUCT_METADATA` deferred | URL locator only. Do not use URL stability as scientific or product identity. |
| `access_format` | `char` / — | `ROW_PRODUCT_METADATA` deferred | MIME-like value. Preserve raw. Observed output was width-limited to `applicati`; validate declared width before parsing. |
| `access_estsize` | `int` / kbyte | `ROW_PRODUCT_METADATA` optional | NULL in all current science rows. Never require it. |
| `collections` | `char` / — | `ROW_PRODUCT_METADATA` optional | External-product collection labels when available; not core identity. |
| `pol_xel` | `int` / — | `ROW_PRODUCT_METADATA` optional | Polarization-axis element count. Available in all current science rows. |
| `s_xel1` | `int` / — | `ROW_PRODUCT_METADATA` optional | First spatial-axis size. NULL in all current science rows. |
| `s_xel2` | `int` / — | `ROW_PRODUCT_METADATA` optional | Second spatial-axis size. NULL in all current science rows. |
| `t_xel` | `int` / — | `ROW_PRODUCT_METADATA` optional | Time-axis element count. Available in all current science rows. |
| `facility_name` | `char` / — | Service namespace | Preserve facility label; not candidate identity. |
| `instrument_name` | `char` / — | Service namespace | Preserve instrument label. |
| `obs_collection` | `char` / — | Service namespace | Preserve collection name to namespace records. |
| `o_ucd` | `char` / — | Raw metadata | Preserve observable-axis UCD; no initial duplication-rule role. |

### Discovery, publication, and provenance — 15 fields

These fields are retained in raw rows but are outside initial reconstruction
and duplication identity.

| Archive field | TAP type / unit | Engineering treatment |
|---|---|---|
| `authors` | `char` / — | Deferred publication authorship metadata. |
| `proposal_authors` | `char` / — | Deferred proposal Co-I metadata. |
| `proposal_abstract` | `char` / — | Deferred proposal text; never log or index without an explicit feature need. |
| `pub_abstract` | `char` / — | Deferred publication text. |
| `pub_title` | `char` / — | Deferred publication title. |
| `first_author` | `char` / — | Deferred publication metadata. |
| `bib_reference` | `char` / — | Deferred bibliographic reference/bibcode. |
| `publication_year` | `int` / — | Deferred publication-year filter. |
| `science_keyword` | `char` / — | Deferred discovery/filter metadata. |
| `scientific_category` | `char` / — | Deferred discovery/filter metadata. |
| `obs_title` | `char` / — | Deferred project title; not identity. |
| `schedblock_name` | `char` / — | Deferred scheduling-block provenance; not ASDM identity. |
| `obs_creator_name` | `char` / — | Deferred creator/PI search metadata. |
| `pi_name` | `char` / — | Deferred PI display metadata. |
| `pi_userid` | `char` / — | Sensitive identifier. Exclude from core model, normal logs, and UI output unless explicitly authorized. |

The catalogue contains all 73 live fields exactly once.

## Cross-field constraints

Current engineering rules below are separated from the
[recorded experiments](evidence/exploration_snapshots.md#archive-cross-field-experiments).
Historical counts establish counterexamples and evidence scope, not permanent
population constraints.

| Area | Engineering rule |
| --- | --- |
| Query completeness | Require expected/retrieved reconciliation and status inspection. `OK` text alone is insufficient. |
| Publisher DID | Treat as Project alternate ID, never row/product key. Revalidate on ingest. |
| `obs_id` parsing | Preserve and interpret the response datatype/`arraysize` once per query. Store live width conformance independently from historical boundary evidence. Complete grammar above a reported maximum retains schema-drift evidence and may proceed to Member UID validation; exact historical-boundary and malformed values remain unsafe. Missing, invalid, or unbounded metadata is not coerced to 64. |
| Candidate keys | Use surrogate row keys. Do not claim product multiplicity from collisions. |
| Source-SPW cardinality | Persist explicit observed associations; no Cartesian reconstruction. |
| Support grammar | Grammar dispatch plus unknown fallback. Top-level census does not prove every bracket interior. |
| Brace mapping | `SPW_SUPPORT_MAP` is many-to-many-capable. Count equality is not proof of one-to-one mapping. |
| Brace token 2 | Preserve raw and normalized token; status remains semantically ambiguous. |
| Execution ownership | Keep these values at Source-Execution scope, not pure Source scope. |
| STC-S | Retain raw syntax and unsupported states. The independent spatial layer supports only limited `CIRCLE ICRS`; sampled POLYGON/UNION parsing is not production support. |
| Resolution fields | Separate storage and comparison; never alias. |
| Primary angular-resolution evidence | Use `spatial_resolution` for initial Archive candidate retrieval; retain `s_resolution` as an independent cross-check. Neither field is a measured FITS restoring beam. |
| Top-level `type` | Treat as proposal/project classification with an unknown-value fallback. It is unrelated to `science_observation = 'T'` and must not be interpreted as FDM/TDM. |
| Frequency-Support mode representation | Preserve raw `em_xel` only. Do not classify it as UI `continuum`/`line` in production and never derive formal mode from `em_xel`, top-level `type`, bandwidth, or spectral resolution. Mode remains unavailable until supported configuration evidence is obtained and reliably associated with the candidate SPW. |
| Sensitivity basis | Preserve them as distinct estimated evidence. Do not represent either as achieved QA2 image-product RMS. |
| Query-arithmetic units | Probe the request-specific fields in `TAP_SCHEMA.columns`, gate frequency and angular filters independently, retain requested bounds and fallback status in provenance, and preserve NULL-valued rows for local non-evaluability. |
| QA2 boundary | Preserve `qa2_passed` as evidence; do not add `qa2_passed = 'T'` as an implicit client filter. |
| Wavelength/frequency bounds | Explicit unit conversion and declared tolerance; no direct float equality. |
| Product metadata | Row-level product description only; physical file granularity unresolved. |
| Determinism | Reconstruction and mapping must not depend on TAP row order. |

## Implemented status values

This is the documentation index for the following Archive enum vocabularies.
Code definitions are authoritative; other documents should link here instead of
maintaining duplicate complete lists.

| Concern / Python enum | Implemented values | Code reference |
| --- | --- | --- |
| `ArchiveQueryStatus` | `COMPLETE`, `OVERFLOW`, `COUNT_MISMATCH`, `ERROR` | [Source](../src/alma_duplicate/clients/archive_contract.py) |
| `ObsIdConfidence` | `PARSED_COMPLETE`, `PARSED_AT_HISTORICAL_TRUNCATION_BOUNDARY`, `FAILED_AT_HISTORICAL_TRUNCATION_BOUNDARY`, `FAILED_OTHER` | [Source](../src/alma_duplicate/domain/archive.py) |
| `ObsIdWidthMetadataStatus` | `BOUNDED_VARIABLE`, `FIXED`, `UNBOUNDED`, `MISSING`, `INVALID`, `INCOMPATIBLE_DATATYPE` | [Source](../src/alma_duplicate/domain/archive.py) |
| `ObsIdWidthStatus` | `NOT_EVALUABLE`, `WITHIN_UNBOUNDED`, `BELOW_REPORTED_MAXIMUM`, `AT_REPORTED_MAXIMUM`, `ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT` | [Source](../src/alma_duplicate/domain/archive.py) |
| `ParseStatus` | `PARSED`, `PARTIAL`, `FAILED` | [Source](../src/alma_duplicate/domain/spectral.py) |
| `FrequencySupportGrammar` | `BRACKET`, `BRACE`, `MISSING`, `BLANK`, `UNKNOWN` | [Source](../src/alma_duplicate/domain/spectral.py) |
| `ReconstructionStatus` | `LINKED`, `OBS_ID_UNSAFE`, `MEMBER_UID_MISSING`, `ASDM_UID_MISSING`, `PARSED_MEMBER_MISMATCH` | [Source](../src/alma_duplicate/domain/reconstruction.py) |
| `SupportMappingStatus` | `ASSIGNED`, `RECONSTRUCTION_UNLINKED`, `ROW_FREQUENCY_MISSING`, `UNSUPPORTED_GRAMMAR`, `SUPPORT_PARSE_UNSAFE`, `NO_USABLE_COMPONENT`, `OUTSIDE_INTERVAL`, `AMBIGUOUS_MULTIPLE_INTERVALS`, `OUTSIDE_REPRESENTATION_TOLERANCE`, `AMBIGUOUS_EQUAL_DISTANCE` | [Source](../src/alma_duplicate/domain/reconstruction.py) |
| `MissingValueStatus` | `PRESENT`, `MASKED`, `NULL`, `BLANK_NORMALIZED`, `SENTINEL_3000_DATE` | [Source](../src/alma_duplicate/domain/normalization.py) |

Support assignment ambiguity belongs to `SupportMappingStatus`, not `ParseStatus`.
STC-S families recorded in notebook experiments are not an implemented production
STC-S enum. This does not exclude the implemented `SpatialStatus` availability
enum or limited `CIRCLE ICRS` parsing in the independent
[spatial layer](search_plan_spatial.md#spatial-evidence). `SpatialStatus` describes
evidence availability, not STC-S families or a duplication outcome. Raw project
classifications likewise are not a correlator-mode enum.
Future rule evaluability states are design requirements, not reconstruction states.

## Not established by the public view

- official ALMA internal tables, keys, or execution schema;
- a stable physical product/file identifier or download granularity;
- future `frequency_support` or STC-S grammars;
- semantic distinction of brace token 2 in the current degenerate population;
- global physical-target identity from source labels;
- individual mosaic pointings;
- moving/Solar-system target equivalence;
- supported and validated per-SPW correlator-mode evidence for the Appendix A
  FDM-specific criterion;
- achieved image-product sensitivity or measured FITS restoring-beam values;
- a complete production snapshot of TAP datatype, unit, UCD, arraysize, and
  description for every retrieved field;
- primary-beam, spectral-smoothing, and final duplication thresholds; or
- current-cycle CSV correspondence and known-duplicate end-to-end decisions.

The correlator-mode field-access gap is not closed by TAP `em_xel`.
Configuration-backed mode evidence and its reliable association with Archive
candidates remain separate future work. The other gaps belong to parser
regression tests, the queue-CSV integration, or the duplication-policy layer.

## Semantic-source references

- [Cycle 13 ALMA Science Archive Manual](https://almascience.eso.org/documents-and-tools/cycle13/science-archive-manual)
- [ALMA query by spatial resolution](https://almascience.eso.org/alma-data/archive/archive-notebooks/nb5_ALMA_Query_by_spatial_resolution.html)
- [ALMA query by sensitivity](https://almascience.eso.org/alma-data/archive/archive-notebooks/nb7_ALMA_Query_by_sensitivity.html)
- [ALMA data resources](https://almascience.eso.org/alma-data)
- [ALMA processing resources](https://almascience.eso.org/processing)

The service metadata and population counts above were captured directly from
the ALMA TAP service. External documentation supplies scientific semantics;
it does not override contradictory raw TAP evidence or create fields that the
current `ivoa.obscore` representation does not expose.
