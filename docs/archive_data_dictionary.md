# ALMA Archive Data Dictionary

## Purpose

Implementation contract for ingesting the 73 columns in the public ALMA
`ivoa.obscore` TAP view into Archive Reconstruction Model v0.4. It consolidates
evidence from Notebooks 01 through 04c and records:

- the service type and unit;
- the internal owner or engineering role;
- mandatory normalization and validation behavior; and
- cross-field constraints established by Notebooks 01–04b.

It is not the official internal ALMA database schema. Raw TAP values always
remain authoritative evidence; normalized and derived values are versioned
projections.

## Evidence snapshots

The structural census was captured on 2026-08-25. Notebook 04c added a
semantic-closure snapshot captured at
`2026-08-31T12:27:55.081125+00:00`.

A read-only mode-closure investigation on 2026-09-02 examined 443,335 current
science-observation rows. `em_xel` was never NULL, ranged up to 8192, and had a
clear observed gap between 128 and 240. A matched Archive UI/TAP example
returned channel counts `1920, 128, 1920, 1920` from both the UI's `chaNum`
property and public TAP `em_xel`. Later review identified valid observing
configurations for which channel count does not uniquely determine TDM/FDM.
The production pipeline therefore preserves `em_xel` only as raw metadata and
does not reproduce the UI classification or derive correlator mode from it.

| Evidence | 2026-08-25 structural snapshot | 2026-08-31 semantic snapshot |
|---|---:|---:|
| Live `ivoa.obscore` columns | 73 | 73 |
| Schema SHA-256 | `2cb2009067ab50f1727454ccb57cb1280c81ad4bfa3a10a9c2df2f0de7044c15` | Not recomputed |
| Science-target rows | 442,507 | 443,211 |
| Proposal IDs / publisher DIDs | 5,611 / 5,611 | Not recounted |
| Distinct proposal / top-level `type` pairs | Not counted | 5,614 |
| Frequency-support bracket / brace rows | 442,452 / 55 | Not recounted |
| Standard `continuum` / `line` / `FDM` / `TDM` tokens in `frequency_support` | Not counted | 0 / 0 / 0 / 0 |
| STC-S CIRCLE / POLYGON / UNION rows | 194,500 / 245,655 / 2,352 | Not recounted |
| Cube / image rows | 305,618 / 136,889 | Not recounted |

The increase from 442,507 to 443,211 science-target rows demonstrates that
Archive populations are dynamic. Counts from different capture times must not
be combined as if they describe one immutable snapshot.

## Implementation boundary

The production Archive client v5/schema v2 preserves row values, selected column names,
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

| Area | Closure evidence | Engineering rule |
|---|---|---|
| Query completeness | A deliberately limited result returned `OVERFLOW`; valid zero-row responses returned complete `OK`. | Require expected/retrieved reconciliation and status inspection. `OK` text alone is insufficient. |
| Publisher DID | All 442,507 rows matched `ADS/JAO.ALMA#<proposal_id>`; 5,611 IDs mapped one-to-one and 442,501 rows repeated a DID. | Treat as Project alternate ID, never row/product key. Revalidate on ingest. |
| `obs_id` parsing | 441,866 parsed below 64 chars; 275 parsed at the historical 64-character boundary with risk; 366 failed there due truncation. A later mosaic response returned seven syntactically complete 65-character values while its VOTable FIELD reported `arraysize="64*"`. | Preserve and interpret the response datatype/`arraysize` once per query. Store live width conformance independently from historical boundary evidence. Complete grammar above a reported maximum retains schema-drift evidence and may proceed to Member UID validation; exact historical-boundary and malformed values remain unsafe. Missing, invalid, or unbounded metadata is not coerced to 64. |
| Candidate keys | `obs_id`: 496 duplicate rows in 134 groups. Parsed `(Member, ASDM, Source, SPW)`: 114 rows in 42 duplicate groups, all width-risk affected. | Use surrogate row keys. Do not claim product multiplicity from collisions. |
| Source-SPW cardinality | Expanded sample: 39 complete grids and one sparse Moon association. | Persist explicit observed associations; no Cartesian reconstruction. |
| Support grammar | Archive-wide top-level partition: 442,452 bracket, 55 brace, zero missing/blank/unknown. | Grammar dispatch plus unknown fallback. Top-level census does not prove every bracket interior. |
| Brace mapping | Complete 55-row population: 52 components across 13 Source-Execution contexts; all rows mapped. One context had 7 SPWs to 4 components; three components received 2 SPWs. | `SPW_SUPPORT_MAP` is many-to-many-capable. Count equality is not proof of one-to-one mapping. |
| Brace token 2 | All brace rows had `em_xel=1`; token 2 matched both bandwidth and spectral resolution after conversion. | Preserve raw and normalized token; status remains semantically ambiguous. |
| Execution ownership | Verified `3C279`/`3c279` across two ASDMs, maximum separation 0.000547 arcsec; footprint, support, resolution, antenna, time, and sensitivity differed. | Keep these values at Source-Execution scope, not pure Source scope. |
| STC-S | Archive-wide families: 194,500 CIRCLE, 245,655 POLYGON, 2,352 UNION; zero missing/unknown. Strict parsing tested 40 examples per family. | Support current families and raw fallback. Do not claim Archive-wide interior validation. |
| Resolution fields | `s_resolution != spatial_resolution` in 41,365 of 442,507 rows. | Separate storage and comparison; never alias. |
| Primary angular-resolution evidence | The service definitions differ, and the official ALMA spatial-resolution query examples use `spatial_resolution`. | Use `spatial_resolution` for initial Archive candidate retrieval; retain `s_resolution` as an independent cross-check. Neither field is a measured FITS restoring beam. |
| Top-level `type` | On 2026-08-31, all 5,614 distinct proposal/type pairs matched the terminal `proposal_id` suffix; observed values were `S`, `L`, `T`, `V`, `SV`, `E`, `P`, and `CAL`. | Treat as proposal/project classification with an unknown-value fallback. It is unrelated to `science_observation = 'T'` and must not be interpreted as FDM/TDM. |
| Frequency-Support mode representation | TAP has no direct FDM/TDM string and the 2026-08-31 raw-string census found none of the standard tokens. Although Archive UI channel counts matched public TAP `em_xel` in a sampled case, channel count is not a unique discriminator across valid correlator configurations. | Preserve raw `em_xel` only. Do not classify it as UI `continuum`/`line` in production and never derive formal mode from `em_xel`, top-level `type`, bandwidth, or spectral resolution. Mode remains unavailable until supported configuration evidence is obtained and reliably associated with the candidate SPW. |
| Sensitivity basis | TAP metadata defines `cont_sensitivity_bandwidth` and `sensitivity_10kms` as estimates with documented limitations. | Preserve them as distinct estimated evidence. Do not represent either as achieved QA2 image-product RMS. |
| Query-arithmetic units | The frequency overlap predicate requires `frequency=GHz`, `bandwidth=Hz`; the angular predicate requires `spatial_resolution=arcsec`. | Probe the request-specific fields in `TAP_SCHEMA.columns`, gate frequency and angular filters independently, retain requested bounds and fallback status in provenance, and preserve NULL-valued rows for local non-evaluability. |
| QA2 boundary | Observational metadata can be available after QA0 while later processing or QA2 remains incomplete. | Preserve `qa2_passed` as evidence; do not add `qa2_passed = 'T'` as an implicit client filter. |
| Wavelength/frequency bounds | Five exact floating-point sample failures were all within 1 Hz; maximum boundary difference was about `2.84e-5 Hz`. | Explicit unit conversion and declared tolerance; no direct float equality. |
| Product metadata | 305,618 cube and 136,889 image rows; all current science rows level 2. Axis/size availability is uneven. | Row-level product description only; physical file granularity unresolved. |
| Determinism | Reconstruction hashes matched for seeds 0, 1, 7, 42, and 2026. | Reconstruction and mapping must not depend on TAP row order. |

## Required status values

| Concern | Minimum states |
|---|---|
| Query | `COMPLETE`, `OVERFLOW`, `COUNT_MISMATCH`, `ERROR` |
| `obs_id` confidence | `PARSED_COMPLETE`, `PARSED_AT_HISTORICAL_TRUNCATION_BOUNDARY`, `FAILED_AT_HISTORICAL_TRUNCATION_BOUNDARY`, `FAILED_OTHER` |
| `obs_id` width metadata | `BOUNDED_VARIABLE`, `FIXED`, `UNBOUNDED`, `MISSING`, `INVALID`, `INCOMPATIBLE_DATATYPE` |
| `obs_id` live width conformance | `NOT_EVALUABLE`, `WITHIN_UNBOUNDED`, `BELOW_REPORTED_MAXIMUM`, `AT_REPORTED_MAXIMUM`, `ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT` |
| Support family | `BRACKET`, `BRACE`, `MISSING`, `BLANK`, `UNKNOWN` |
| Support parse | `PARSED`, `PARTIAL`, `FAILED`, `AMBIGUOUS` |
| STC-S family | `CIRCLE`, `POLYGON`, `UNION`, `MISSING`, `BLANK`, `UNKNOWN` |
| Reconstruction | `LINKED`, `UNLINKED_PARSE_FAILURE`, `UNLINKED_AMBIGUOUS`, `TRUNCATION_RISK` |
| Missing normalization | `PRESENT`, `MASKED`, `NULL`, `BLANK_NORMALIZED`, `SENTINEL_3000_DATE` |
| Project classification | Known current raw values plus explicit unknown-value preservation; never coerce an unknown value into a current class |

Status vocabularies and parser versions belong in code constants and tests,
not ad-hoc strings distributed across notebooks.

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
