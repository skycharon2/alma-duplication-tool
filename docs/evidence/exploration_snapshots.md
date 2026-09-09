# Exploration snapshots and historical evidence

These records were consolidated from the documentation at commit
`76d50029a025d79c59b686b8a31c37bcf0f6227e`. This migration did not rerun notebooks,
query TAP or acquire a new Queue snapshot. Dates, checksums, sample scopes,
limitations and reported derivations remain historical. Unspecified dates or
unrecomputed checksums remain unspecified. Different capture populations must
not be combined into one census.

Current contracts: [data model](../data_model.md),
[Archive dictionary](../archive_data_dictionary.md), and
[Queue ingestion](../queue_csv_contract.md). The tables below preserve evidence,
not current API definitions or approved duplication methods.

## Archive capture register

Source: former Archive dictionary “Evidence snapshots”; Notebooks 04b/04c and
the separately dated mode investigation. Later mode counterexamples supersede
channel-count inference; the runtime retains raw `em_xel` only.


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

## Archive exploration summary

Source: former data-model “Historical exploration evidence summary”. Unqualified
structural counts belong to the 2026-08-25 closure; rows naming later captures
or samples retain that narrower qualification. “Current” in retained evidence
means current at its recorded capture, not today.


The observations below describe the named notebook populations and capture
dates. Their counts are historical evidence, not a current live census or proof
that each experimental derivation is implemented in production.

| Question | Current evidence | Model consequence |
|---|---|---|
| Live schema | 73 columns; schema SHA-256 `2cb2009067ab50f1727454ccb57cb1280c81ad4bfa3a10a9c2df2f0de7044c15` | Classify all fields and detect future schema drift |
| Science-target population | 442,507 rows on 2026-08-25 and 443,211 rows at `2026-08-31T12:27:55.081125+00:00` | Treat all counts as time-specific snapshots and preserve capture provenance |
| Query completeness | COUNT/retrieve reconciliation, valid empty result, and intentional `OVERFLOW` verified | Never infer absence from an incomplete response |
| Retrieval field metadata | PyVO exposes VOTable `FIELD` descriptors independently of result rows; the current client preserves them in projection order | Carry units and semantic descriptors with the same query result, including valid empty results |
| Comparison-field units | Live units for frequency, bandwidth, spectral/spatial resolution, and two sensitivity estimates are checked at runtime | Convert only compatible units; preserve missing/incompatible status rather than assuming units from names |
| Query arithmetic units | Frequency ADQL assumes `frequency=GHz`, `bandwidth=Hz`; angular ADQL assumes `spatial_resolution=arcsec` | Verify exact `TAP_SCHEMA` units for each requested numeric prefilter, disable unsafe filters independently, retain original bounds in provenance, and keep NULL evidence rows for local non-evaluability |
| Archive frequency frame | Public documentation identifies sky frequency but not a comparison-ready TAP reference frame | Derive typed Archive coverage but keep cross-source frame alignment unavailable |
| `obs_publisher_did` | 5,611 proposal IDs and 5,611 publisher DIDs; exact `ADS/JAO.ALMA#<proposal_id>` mapping with no exception | Project-level external identifier, not a row or product key |
| `obs_id` | 442,141 parsed; 366 width-truncated failures; 275 additional parseable values at the historically observed 64-character truncation boundary; a later live mosaic response returned seven complete 65-character values while that response reported `arraysize="64*"` | Preserve raw value; evaluate grammar, live VOTable width conformance, and historical truncation evidence independently; never use as an Archive-wide key |
| Row identity | 134 duplicate `obs_id` groups; 42 duplicate parsed Source-Execution-SPW groups, all affected by identifier-width risk | Use internal surrogate row identifiers |
| Source-SPW cardinality | 39 complete grids and one explicit sparse association in the expanded census | Store observed associations; never synthesize a Cartesian grid |
| Support mapping | One context mapped 7 SPW rows to 4 support components | Allow many SPWs to map to one support component |
| Frequency-support grammar | 442,452 bracket rows, 55 brace rows, no missing/blank/unknown top-level family | Dispatch by grammar family and preserve unknown fallback |
| Brace population | Complete 55/55-row census; all structures and mappings valid | Support brace grammar in production; retain token-2 semantic ambiguity |
| Repeated source across ASDM | Spatially verified `3C279`/`3c279` case across two ASDMs | Keep footprint, time, antenna, support, and resolution at Source-Execution scope |
| STC-S family | 194,500 CIRCLE, 245,655 POLYGON, 2,352 UNION; no missing/blank/unknown | Retain all raw geometry; current local parsing supports only `CIRCLE ICRS`; POLYGON/UNION support remains deferred |
| Product population | 305,618 cube and 136,889 image rows, all `calib_level=2` | Treat product metadata as row evidence; physical file granularity remains unresolved |
| Spatial resolution | 41,365 of 442,507 rows had `s_resolution != spatial_resolution` | Preserve the two fields separately |
| Primary angular-resolution evidence | Service definitions differ; official ALMA query examples use `spatial_resolution` | Use `spatial_resolution` for initial Archive candidate retrieval, preserve `s_resolution` as a cross-check, and treat neither as a measured FITS restoring beam |
| Top-level `type` | Eight values were observed on 2026-08-31; all 5,614 distinct proposal/type pairs matched the terminal `proposal_id` suffix | Model as optional proposal/project classification with an unknown-value fallback; do not confuse `type = 'T'` with `science_observation = 'T'` |
| Frequency-Support mode | TAP has no direct policy-grade FDM/TDM field; public `em_xel` is a channel count and valid configurations overlap across modes | Preserve raw `em_xel` only; do not derive Archive UI type or correlator mode from channel count; leave formal mode unavailable until configuration-backed evidence is implemented and reliably associated |
| Sensitivity semantics | TAP metadata defines continuum and nominal 10 km/s sensitivity as estimates with documented limitations | Store separate estimated-evidence concepts; never label them achieved QA2 product RMS |
| QA2 boundary | Archive metadata may be available after QA0 while processing or QA2 remains incomplete | Keep `qa2_passed` as evidence and leave inclusion/exclusion to explicit policy |
| Reconstruction determinism | Five shuffle seeds produced identical reconstructions | Require order-independent production reconstruction |

## Archive cross-field experiments

Source: former Archive dictionary “Cross-field constraints”. The detailed
evidence column is preserved here; current engineering rules remain in the
[dictionary](../archive_data_dictionary.md#cross-field-constraints). The later
65-character mosaic response has no capture timestamp recorded in that section.

| Area | Recorded closure evidence |
| --- | --- |
| Query completeness | A deliberately limited result returned `OVERFLOW`; valid zero-row responses returned complete `OK`. |
| Publisher DID | All 442,507 rows matched `ADS/JAO.ALMA#<proposal_id>`; 5,611 IDs mapped one-to-one and 442,501 rows repeated a DID. |
| `obs_id` parsing | 441,866 parsed below 64 chars; 275 parsed at the historical 64-character boundary with risk; 366 failed there due truncation. A later mosaic response returned seven syntactically complete 65-character values while its VOTable FIELD reported `arraysize="64*"`. |
| Candidate keys | `obs_id`: 496 duplicate rows in 134 groups. Parsed `(Member, ASDM, Source, SPW)`: 114 rows in 42 duplicate groups, all width-risk affected. |
| Source-SPW cardinality | Expanded sample: 39 complete grids and one sparse Moon association. |
| Support grammar | Archive-wide top-level partition: 442,452 bracket, 55 brace, zero missing/blank/unknown. |
| Brace mapping | Complete 55-row population: 52 components across 13 Source-Execution contexts; all rows mapped. One context had 7 SPWs to 4 components; three components received 2 SPWs. |
| Brace token 2 | All brace rows had `em_xel=1`; token 2 matched both bandwidth and spectral resolution after conversion. |
| Execution ownership | Verified `3C279`/`3c279` across two ASDMs, maximum separation 0.000547 arcsec; footprint, support, resolution, antenna, time, and sensitivity differed. |
| STC-S | Archive-wide families: 194,500 CIRCLE, 245,655 POLYGON, 2,352 UNION; zero missing/unknown. Strict parsing tested 40 examples per family. |
| Resolution fields | `s_resolution != spatial_resolution` in 41,365 of 442,507 rows. |
| Primary angular-resolution evidence | The service definitions differ, and the official ALMA spatial-resolution query examples use `spatial_resolution`. |
| Top-level `type` | On 2026-08-31, all 5,614 distinct proposal/type pairs matched the terminal `proposal_id` suffix; observed values were `S`, `L`, `T`, `V`, `SV`, `E`, `P`, and `CAL`. |
| Frequency-Support mode representation | TAP has no direct FDM/TDM string and the 2026-08-31 raw-string census found none of the standard tokens. Although Archive UI channel counts matched public TAP `em_xel` in a sampled case, channel count is not a unique discriminator across valid correlator configurations. |
| Sensitivity basis | TAP metadata defines `cont_sensitivity_bandwidth` and `sensitivity_10kms` as estimates with documented limitations. |
| Query-arithmetic units | The frequency overlap predicate requires `frequency=GHz`, `bandwidth=Hz`; the angular predicate requires `spatial_resolution=arcsec`. |
| QA2 boundary | Observational metadata can be available after QA0 while later processing or QA2 remains incomplete. |
| Wavelength/frequency bounds | Five exact floating-point sample failures were all within 1 Hz; maximum boundary difference was about `2.84e-5 Hz`. |
| Product metadata | 305,618 cube and 136,889 image rows; all current science rows level 2. Axis/size availability is uneven. |
| Determinism | Reconstruction hashes matched for seeds 0, 1, 7, 42, and 2026. |

## Evidence labels


The following labels organize historical research evidence in this document;
they are not a shared runtime enum or a comparison-readiness scale:

1. `SERVICE_DEFINED`: field names, types, units, and descriptions from the
   live TAP schema.
2. `ARCHIVE_WIDE_CENSUS`: complete current-snapshot row counts or mappings.
3. `COMPLETE_CURRENT_POPULATION`: complete validation of a bounded current
   population, such as all 55 brace rows.
4. `SAMPLE_SUPPORTED` or `COUNTEREXAMPLE`: purposive evidence. A
   counterexample is sufficient to reject a universal constraint but not to
   estimate prevalence.

## Queue pinned snapshot

All following Queue subsections refer to this same pinned full snapshot unless
explicitly identified as a fixture. Source date, retrieval date and checksum
remain distinct; these counts are not required for arbitrary future exports.

Source: former Queue contract “Historical reference”; Notebook 05. No runtime
retrieval timestamp is inferred from this record or from the notebook mtime.


The v1 contract is based on the public file inspected in Notebook 05.

| Property | Observed value |
|---|---:|
| Source page | `https://almascience.eso.org/proposing/duplications` |
| Retrieval date used by the exploration | 2026-09-01 |
| Source-provided queue date in the description | 2026-03-03 |
| SHA-256 | `8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5` |
| Physical CSV records | 3,241 |
| Embedded dictionary entries | 35 |
| Operational columns | 79 |
| Data rows | 3,200 |
| Unique exact row-content fingerprints | 3,135 |
| Rows participating in exact-content duplicates | 75 |
| Excess duplicate copies | 65 |

The retrieval date, source-provided queue date, and checksum describe different
facts and must not be substituted for one another. Counts in this section are
regression evidence for the pinned snapshot, not permanent ALMA-wide
cardinality constraints.

A compatible future snapshot may contain different projects, row counts, SPW
occupancy, and category values. It must receive a new checksum and capture
provenance and must pass the same schema and consistency gates before entering
reconstruction.

## Queue SPS bandwidth evidence

The pinned snapshot contains one spectral-scan row:

| Field | Value |
|---|---:|
| Project | `2025.1.00299.S` |
| Target | `HBC_687` |
| Band | `ALMA_RB_06` |
| Start frequency | 261.5 GHz |
| End frequency | 268.7 GHz |
| Raw SPS bandwidth | 1000.0 |
| SPS spectral resolution | 0.000564453125 MHz |
| Sensitivity reference frequency | 265.141 GHz |
| Sensitivity reference width | 0.565 MHz |

Interpreting the raw bandwidth as 1,000 GHz is inconsistent with the 7.2-GHz
scan range and Band 6 context. Interpreting it as 1,000 MHz is numerically and
scientifically plausible and agrees with the embedded dictionary description,
which defines it as the bandwidth of each scan window.


## Queue SPW occupancy

The pinned snapshot provides the following evidence:

| Property | Observed value |
|---|---:|
| Reserved slots | 16 |
| Highest populated slot | 7 |
| Rows with partial triples | 0 |
| Rows with non-contiguous populated slots | 0 |
| Long-form regular-SPW records | 16,216 |

Slots 8–16 are valid reserved schema fields even though they are empty in the
pinned snapshot.


## Queue spectral representation counts

The pinned snapshot contains 3,199 regular rows and one complete SPS row. No
row contains both representations, neither representation, or a partial SPS
record.


## Queue spatial census

Pinned-snapshot evidence at this tolerance includes:

- 2,940 rows labelled `Custom`;
- 140 rows labelled `Rectangle`;
- 120 rows with a blank mosaic label;
- 420 repeated custom-mosaic centre rows;
- 2,520 repeated custom-mosaic offset rows;
- 231 custom-mosaic project–target–band groups;
- exactly one centre and six offset spatial components in every custom group;
- rectangle extents on all 140 rectangle rows; and
- nine blank-labelled rows with meaningful nonzero offsets.


## Queue sparse associations

Within 419 pinned-snapshot groups:

- 417 groups' observed spatial–spectral pairs happen to fill the local
  Cartesian product;
- `2025.1.00539.S / M33 / ALMA_RB_06` has five spatial and five spectral
  signatures but only five observed pairs rather than 25; and
- `2025.1.00576.L / NGC_0253 / ALMA_RB_06` has two spatial and two spectral
  signatures but only two observed pairs rather than four.


## Queue repeated exports

Five pinned-snapshot groups also contain repeated identical exports. Their
raw-row multiplicity and source-line provenance remain evidence and are not
discarded during component deduplication.


## Queue full-snapshot regression expectations

The full pinned snapshot remains a local acceptance test. Its expected
regression checks include:

```text
raw_rows = 3200
operational_columns = 79
regular_rows = 3199
sps_rows = 1
long_spw_records = 16216
row_associations = 3200
partial_spw_triples = 0
noncontiguous_spw_rows = 0
reference_frequency_failures = 0
project_target_band_groups = 419
sparse_or_paired_groups = 2
groups_with_exact_export_multiplicity = 5
```


## Queue reference-frequency consistency

Nominal bounds remain available for conservative discovery and the pinned
snapshot's historical reference-frequency consistency check. In the pinned
snapshot, all 3,199 regular rows place `Ref.Frequency` inside both at least one
nominal interval and at least one derived usable interval.

The reference-frequency diagnostic uses a numerical boundary tolerance of
`1e-12 GHz`. Values outside every derived nominal interval produce a warning;
they do not exclude the row while the reference remains unverified. The pinned snapshot passed for all 3,199
regular rows. The SPS row's reference frequency also lies inside its declared
scan range.


## Queue physical line layout

The pinned snapshot has the following physical layout:

| Physical line | Meaning |
|---:|---|
| 1 | Source description |
| 2 | Blank separator |
| 3 | Embedded-dictionary header: `Column Heading,Units,Description` |
| 4–38 | 35 embedded-dictionary entries |
| 39 | Blank separator |
| 40 | 79-column operational header |
| 41 | Mixed secondary header/unit row |
| 42–3241 | 3,200 operational data rows |

## Queue requested-sensitivity evidence

All 3,200 pinned-snapshot rows contain positive values for all three fields.
The values vary within some project–target–band groups and therefore belong to
the spectral/setup side of reconstruction rather than to target identity.

`Ref.Freq.Width` is an independent request value. In the 3,199 regular rows:

- 29 match the derived aggregate non-overlapping bandwidth;
- three match a source SPW spectral resolution; and
- 3,167 are other or user-defined reference widths.

The parser must not recompute this field from SPW bandwidth or resolution.

For the SPS row, the 0.565-MHz reference width is approximately 1,001 times the
native scan resolution and 0.000565 of the 1,000-MHz per-window bandwidth. Its
requested 2.5-mJy sensitivity is therefore tied to the separate reference
width, not to a native spectral element or a complete scan window.
