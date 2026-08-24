# ALMA Archive Data Dictionary

This document records the mapping between ALMA Archive metadata and the
preliminary internal data model of the duplication-checking tool.

The mappings are based on exploratory queries to the European ALMA TAP service,
official metadata returned by `TAP_SCHEMA.columns`, and the structural and
spectral validation performed in Notebooks 1, 2, 2b, 3, and 4.

Notebook 1 established Archive connectivity, schema access, complete-result
retrieval, and the Centaurus A case study. Notebook 2 tested row granularity,
identifier relationships, Source Contexts, candidate keys, and structural
counterexamples across larger samples. Notebook 2b visualized the observed
relationships and evaluated candidate field-ownership levels. Notebook 3
parsed and validated `frequency_support` and investigated its relationship to
logical SPWs, row-level frequencies, bandwidths, sensitivities, sources, and
ASDM executions. Notebook 4 extended the validation to observation-mode-related
fields, Source-SPW reconstruction, overlapping support intervals, derived
resolution fields, sensitivity ownership, and mosaic footprints.

Unless explicitly identified as an official TAP field definition, structural
relationships and field-ownership levels remain supported by the tested
samples rather than guaranteed for the complete Archive. Purposive sample
counts must not be interpreted as Archive-wide prevalence estimates.

## Archive columns

| Archive column | Type | Unit | Current interpretation and model scope |
|---|---|---|---|
| `proposal_id` | string | — | ALMA proposal/project identifier; Proposal-level field |
| `obs_publisher_did` | string | — | Publisher identifier; matched `ADS/JAO.ALMA#<proposal_id>` for all 1,226 extended-sample rows and behaved as proposal-scoped |
| `group_ous_uid` | string | — | Optional Group OUS identifier; empty strings must be normalized to missing values |
| `member_ous_uid` | string | — | Member OUS dataset identifier and primary grouping key for reconstructing related Archive rows |
| `asdm_uid` | string | — | UID of the ASDM containing the field; one Member may reference multiple ASDMs |
| `obs_id` | string | — | Internal dataset identifier. All tested values encoded source and SPW components using `.source.<source>.spw.<identifier>`. It is a strong candidate raw-row identifier in the tested samples, but not an officially confirmed Archive-wide primary key. |
| `target_name` | string | — | Intended target name; useful for display but not a reliable physical-target identifier |
| `s_ra` | float | deg | ICRS right ascension of the central coordinate |
| `s_dec` | float | deg | ICRS declination of the central coordinate |
| `s_region` | region/string | — | Spatial footprint bounded by the observation; stable at Source Context level in the extended sample |
| `frequency` | float | GHz | Observed/tuned reference frequency on the sky. The exact value belongs to the source–SPW Archive record. It is related to, but not identical to, the centre derived from a parsed `frequency_support` interval. |
| `bandwidth` | float | Hz | Archive total bandwidth. Notebook 4 found differences from parsed support-interval width ranging from -7.5 to +20 MHz in the 1,619-row sample. The two values agreed on the strict `> 1.8 GHz` boundary for every tested row but are not numerically interchangeable. |
| `frequency_support` | string | embedded mixed units | Raw composite description of all frequency ranges used by the field. It may encode multiple intervals, resolution, 10-km/s sensitivity, native sensitivity, and polarization. It is not guaranteed to be unique at Member level and should currently be associated conservatively with a Source–Execution Context. |
| `spectral_resolution` | float | kHz | Archive spectral-resolution value. In Notebook 4 it behaved as SPW/component-level metadata and differed from parsed component resolution by at most approximately 0.00484 kHz in the tested sample. Preserve both representations. |
| `velocity_resolution` | float | m/s | Archive velocity-resolution summary. It was constant within each of the 19 tested Member OUS datasets but did not consistently equal the row-level value derived as `c * delta_frequency / frequency`. Treat it as a setup/Member summary rather than a replacement for SPW spectral resolution. |
| `em_resolution` | float | m | Wavelength-resolution representation. Notebook 4 found close agreement with `c * delta_frequency / frequency^2`; the mean difference was approximately `1.87e-12 m`. Preserve the Archive value but treat it as derived metadata. |
| `s_resolution` | float | arcsec | ObsCore typical spatial resolution. It must remain distinct from the Archive-specific `spatial_resolution` value until their relationship is formally validated. |
| `spatial_resolution` | float | arcsec | Archive spatial-resolution summary; stable at Source Context level in the extended sample. It must not be silently merged with `s_resolution`. |
| `sensitivity_10kms` | float | mJy/beam | Row/SPW-level estimated line sensitivity normalized to 10 km/s. It varied within every tested Source–Execution Context in Notebook 4 and closely matched, but was not numerically identical to, parsed component-level `@10km/s` sensitivity. |
| `cont_sensitivity_bandwidth` | float | mJy/beam | Estimated continuum noise over the aggregate continuum bandwidth. It was single-valued within all 376 tested Source–Execution Contexts and may vary within a Member or ASDM. It is not equivalent to component-level native sensitivity. |
| `antenna_arrays` | string | — | Blank-separated pad–antenna pairs; source/ASDM contextual metadata |
| `is_mosaic` | string | — | `T`/`F` mosaic flag; stable within tested Source Contexts but not always single-valued at Member level |
| `band_list` | string | — | ALMA receiver-band description; not a substitute for exact frequency coverage |
| `pol_states` | string | — | Archive polarization-state representation. The Notebook 4 sample contained only `/XX/YY/`, so broader polarization behavior is not established by that sample. Preserve the raw value. |
| `t_min` | float | MJD days | Lower temporal bound returned by ObsCore; should not be interpreted as an execution duration without validation |
| `t_max` | float | MJD days | Upper temporal bound returned by ObsCore; should not be interpreted as an execution duration without validation |
| `science_observation` | string | — | `T` for science-target records and `F` for calibration/checking records in the tested sample |
| `scan_intent` | string | — | Observational role, such as `TARGET`, `BANDPASS`, `FLUX`, `PHASE`, `CHECK`, or `WVR` |
| `data_rights` | string | — | Archive access state, for example `Public` or `Proprietary` |
| `qa2_passed` | string | — | QA2 status represented as `T` or `F` |
| `obs_release_date` | timestamp/string | — | Raw release-date metadata; `3000-01-01` must currently be treated as an unconfirmed sentinel |

## Validated structural findings

The relationship analysis in Notebooks 1 and 2 supports the following
sample-based interpretation:

$$
N_{\mathrm{Archive\ rows}}
=
N_{\mathrm{source\ contexts}}
\times
N_{\mathrm{unique\ SPWs}}
$$

All 120 tested Member OUS datasets, containing 1,419 Archive rows, were
consistent with this relationship. All tested `obs_id` values could be parsed
into source and SPW components.

In the 1,226-row extended sample:

- all `obs_id` values were unique;
- all `(member_ous_uid, obs_id_source, spw_identifier)` combinations were
  unique;
- Archive records formed complete source–SPW grids;
- `obs_publisher_did` matched `ADS/JAO.ALMA#<proposal_id>` for every row;
- Member OUS could contain multiple sources, SPWs, footprints, and ASDMs;
- SPW counts were variable and could not be represented by a fixed four-window
  structure.

The current sample-supported row interpretation is:

> One Archive row represents one source–spectral-window-related record within a
> Member OUS, rather than one complete observation.

These candidate keys and functional relationships are not claimed as official
Archive-wide primary-key constraints. The application should use an internal
surrogate key while preserving all original Archive identifiers.

## Coordinate-query experiment

> This section preserves the original Notebook 1 case-study results. Later
> Notebook 2 experiments found counterexamples to some relationships that were
> one-to-one in this coordinate sample, including Member OUS–ASDM and
> Member-level mosaic-state relationships.

A coordinate query was performed around:

- right ascension: 201.365 deg;
- declination: -43.019 deg;
- search radius: 0.006 deg = 21.6 arcsec;
- coordinate frame: ICRS;
- observation filter: `science_observation = 'T'`.

The initial exploratory query used `TOP 100`. A separate `COUNT(*)` query
showed that 434 rows matched the spatial constraints. The query was repeated
without `TOP 100`, and all 434 rows were retrieved successfully.

### Identifier counts

| Identifier | Unique values |
|---|---:|
| `proposal_id` | 24 |
| `group_ous_uid` | 82 |
| `member_ous_uid` | 108 |
| `obs_id` | 434 |
| `asdm_uid` | 108 |
| `target_name` | 8 |

The 434 Archive rows must not be interpreted as 434 independent observations.
The `obs_id` values contained components such as
`.source.<name>.spw.<number>`, consistent with source–spectral-window records.
Multiple rows belonged to the same Member OUS.

The eight target-name strings also demonstrated that target names alone are not
reliable identifiers for fixed celestial sources. Coordinate and footprint
matching should be used for primary spatial candidate retrieval.

### Member OUS grouping observations

Within this coordinate-query sample, every Member OUS had one ASDM, one Group
OUS value, one mosaic state, and one complete `frequency_support` value. Later
Notebook 2 experiments showed that these one-to-one relationships do not hold
for all tested Member OUS datasets.

The number of matching rows per Member OUS was variable:

| Matching rows per Member OUS | Member OUS count |
|---:|---:|
| 3 | 10 |
| 4 | 92 |
| 5 | 4 |
| 8 | 2 |

The application must support variable numbers of Archive records and spectral
windows. It must not assume that every Member OUS contains exactly four rows or
four SPWs.

### Mosaic observations

| Mosaic flag | Archive rows | Proposals | Member OUS | ASDM |
|---|---:|---:|---:|---:|
| `F` | 324 | 22 | 79 | 79 |
| `T` | 110 | 12 | 29 | 29 |

Archive-row counts must not be interpreted as observation counts. In this
sample, 110 mosaic-related rows belonged to 29 Member OUS groups. A proposal
could contain both mosaic and non-mosaic Members.

The `is_mosaic` flag does not provide the individual pointings or the overlap
percentage required by the duplication rules. Additional spatial information
will be needed for mosaic-overlap assessment.

## Notebook 3 frequency-support validation

### Experimental scope

The main purposive frequency-support sample contained:

| Quantity | Result |
|---|---:|
| Member OUS datasets | 18 |
| Archive rows | 171 |
| Parsed logical SPWs | 95 |
| Parsed frequency-support components | 95 |
| Unparsed `obs_id` values | 0 |
| Failed or partial support components | 0 |

The number of components per exact support signature was variable:

| Components per signature | Signature count |
|---:|---:|
| 4 | 12 |
| 5 | 1 |
| 6 | 2 |
| 8 | 1 |
| 11 | 2 |

The application must not assume a four-SPW correlator structure.

### Observed grammar

In the tested records, `frequency_support` consisted of bracketed components
joined by ` U `.

Example component:

```text
[214.32..216.21GHz,976.56kHz,8.8mJy/beam@10km/s,546.7uJy/beam@native, XX YY]
```

Each tested component contained:

1. a lower and upper frequency;
2. a frequency-resolution value;
3. sensitivity at 10 km/s;
4. sensitivity at native resolution;
5. polarization products.

The exploratory parser derives:

- `frequency_low_ghz`;
- `frequency_high_ghz`;
- `interval_center_ghz`;
- `interval_width_ghz`;
- `resolution_mhz`;
- `sensitivity_10kms_mjy_per_beam`;
- `sensitivity_native_mjy_per_beam`;
- `polarization_products`;
- `parse_status`;
- `validation_issues`.

The parser preserves the complete raw string and raw component text. Parsing
and semantic validation are separate operations: a syntactically parsed value
may still be rejected because of reversed boundaries, unsupported units,
missing sensitivity bases, or unknown polarization products.

### Parser evidence and limitations

All 95 components in the main sample were parsed successfully. They used:

- frequency in GHz;
- resolution in kHz;
- either `XX YY` or `XX XY YX YY` polarization;
- both `10km/s` and `native` sensitivity entries.

A separate purposive validation across ALMA Bands 3–10 returned 80 distinct
query records representing 78 unique Member OUS datasets and 401 parsed
components. All 401 sampled components passed the current parser and validator.

This does not prove that every current or future Archive row follows the same
grammar. The Band queries were purposive small samples, and the format-exception
query searched for missing expected substrings rather than applying the parser
to every Archive row. Production code must preserve raw text and handle missing,
partial, invalid, and previously unseen formats.

### Relationship to logical SPWs

For all 18 Member OUS datasets in the main sample:

- parsed component count equalled unique parsed SPW count;
- Archive-row count equalled source-context count multiplied by SPW count.

A one-to-one assignment based on frequency-centre and width differences mapped
all 95 logical SPWs to parsed support components. All 95 row-level reference
frequencies fell inside their assigned parsed intervals.

This provides strong sample-level evidence that one bracketed support component
corresponds to one logical SPW. However, `component_index` is not an official
SPW identifier. The current component-to-SPW assignment remains derived
metadata and must retain its method, numerical differences, validation status,
and provenance.

### Row values versus parsed interval values

The main-sample numerical comparison produced:

| Comparison | Median absolute difference | Maximum absolute difference |
|---|---:|---:|
| Row `frequency` vs. parsed interval centre | 1.379 MHz | 4.705 MHz |
| Row `bandwidth` vs. parsed interval width | 5 MHz | 30 MHz |
| Row `sensitivity_10kms` vs. parsed `@10km/s` sensitivity | 0.0167 mJy/beam | 0.0472 mJy/beam |

The Centaurus A case study in Notebook 1 also contained one larger bandwidth
outlier: approximately 0.527 GHz in the Archive `bandwidth` field versus
approximately 0.960 GHz in the assigned support interval.

Therefore, the following raw and derived values must remain separate:

- row-level tuned reference frequency;
- parsed interval centre;
- Archive total bandwidth;
- parsed interval width;
- row-level 10-km/s sensitivity;
- parsed component-level 10-km/s sensitivity.

The observed differences must not be converted directly into duplication-rule
tolerances.

### Exact signatures and spectral geometry

Exact `frequency_support` string equality is too strict for comparing frequency
coverage.

One targeted multi-ASDM Member OUS contained:

- 2 ASDM identifiers;
- 2 Source Contexts;
- 4 SPWs;
- 8 Archive rows;
- 2 exact support strings.

The two support strings had the same frequency intervals, spectral resolutions,
and polarization products, but different sensitivity estimates.

The repeated-Member Band experiment found both:

- one Band 5 Member with the same spectral geometry but different sensitivity;
- one Band 7 Member with different spectral geometry and different sensitivity.

The model must therefore distinguish:

1. the complete raw exact signature;
2. a parsed spectral-geometry signature;
3. a parsed sensitivity signature.

Exact-string inequality does not necessarily mean different frequency coverage.

### Ownership level

The initial samples often contained one exact support string per Member OUS.
Later experiments found multiple exact signatures within a Member.

The targeted and additional multi-ASDM samples did not contain an identical
parsed source label repeated across multiple ASDM executions. A coordinate
comparison also found no pair of tested cross-context positions separated by
less than 60 arcsec.

The experiments therefore cannot yet distinguish definitively whether changes
in `frequency_support` are caused by source, execution, field, or observing
configuration. The raw signature should currently be stored conservatively in
a Source–Execution Context rather than treated as a single Member-level,
Source-level, or ASDM-level value.

### Sensitivity representations

The parsed `@10km/s` sensitivity closely matched the row-level
`sensitivity_10kms` column, but small differences remained, probably including
display precision or rounding effects. Both raw representations must be
preserved.

The parsed `@native` value is a component-level native-resolution sensitivity.
`cont_sensitivity_bandwidth` is an aggregate continuum-bandwidth estimate. They
are different quantities and must not overwrite one another.

### Archive-wide metadata snapshot

An aggregate query executed during Notebook 3 inspected 442,506 rows satisfying
`science_observation = 'T'`.

No SQL NULL values were found for:

- `frequency_support`;
- `sensitivity_10kms`;
- `cont_sensitivity_bandwidth`.

The tested aggregate conditions also found no:

- blank `frequency_support` strings;
- non-positive frequencies;
- non-positive bandwidths;
- non-positive line sensitivities;
- non-positive continuum sensitivities.

These results are a time-specific Archive snapshot, not permanent schema
constraints. The application must continue to handle missing, blank,
non-finite, non-positive, malformed, and unsupported values defensively.

## Notebook 4 observation-mode and Source-SPW validation

### Experimental scope

Notebook 4 constructed a complete purposive sample and then added one known
multi-ASDM Member OUS. The final analysis contained:

| Quantity | Result |
|---|---:|
| Archive science-target rows | 1,619 |
| Member OUS datasets | 19 |
| ASDM executions | 20 |
| Source–Execution Contexts | 376 |
| Parsed support components | 1,619 |
| Parser or validation issues | 0 |

All 24 selected Archive fields were populated in this sample, and all rows had
`scan_intent = 'TARGET'`. This is a purposive-sample result, not a permanent
non-null constraint for the Archive.

All 1,619 tested `obs_id` values matched the observed
`.source.<source>.spw.<identifier>` structure, and the embedded Member OUS UID
matched the separate `member_ous_uid` column. `obs_id`,
`(Member, source, SPW)`, and `(Member, ASDM, source, SPW)` were all unique in
the sample. The normalized model nevertheless retains ASDM in the conservative
execution-aware context and preserves raw `obs_id`.

### One-to-one support-component assignment

Every one of the 376 Source–Execution Contexts had equal Archive-row and parsed
component counts. Simple interval containment was not sufficient for identity:
1,393 rows fell inside one interval, while 226 rows fell inside two overlapping
intervals.

Context-level one-to-one assignment, ordered by row reference frequency and
component interval centre, assigned all 1,619 rows. There were no count
mismatches, duplicate assignments, or assigned frequencies outside their
intervals. The maximum observed absolute row-frequency-to-centre difference was
approximately 4.850 MHz.

The mapping is strong sample-supported evidence, not an official Archive key.
Production code must record its mapping method and status and preserve rows
that cannot be mapped.

### Observation-mode-related fields

No direct FDM/TDM or correlator-mode column was found in the tested ObsCore
schema. The model can store observation-mode evidence but must not assign a
formal mode solely from an unvalidated resolution threshold.

Notebook 4 found:

- Archive `bandwidth` and parsed interval width differed by -7.5 to +20 MHz,
  but agreed on the strict `> 1.8 GHz` boundary for all 1,619 rows;
- Archive `spectral_resolution` and parsed component resolution differed by at
  most approximately 0.00484 kHz and behaved as SPW/component-level values;
- `em_resolution` closely matched the wavelength-resolution value derived as
  `c * delta_frequency / frequency^2` and should be treated as derived metadata;
- `velocity_resolution` was single-valued within every tested Member OUS but
  did not consistently equal row-level `c * delta_frequency / frequency`;
- `sensitivity_10kms`, parsed `@10km/s`, and parsed `@native` sensitivities
  varied at SPW/component level;
- `cont_sensitivity_bandwidth` was single-valued within all 376 tested
  Source–Execution Contexts and is an aggregate context-level value.

The observed numerical differences are evidence about representation and
ownership. They do not define duplication-policy tolerances.

### Mosaic spatial representation

The expanded sample contained 59 mosaic Source–Execution Contexts from eight
Member OUS datasets and nine ASDM executions. Each tested source context had
one central coordinate and one STC-S footprint repeated across its SPW rows.
All tested mosaic footprints were Polygons, and one mosaic ASDM contained from
one to 21 source contexts.

ObsCore therefore supports an aggregate Source-level spatial footprint in the
tested data. It did not demonstrate individual mosaic pointing identifiers or
pointing-by-pointing geometry. A footprint-overlap operation may be developed,
but individual-pointing mosaic comparison remains unsupported by these fields.

### Supervisor reference cases

Projects `2021.A.00028.S` and `2018.1.00294.S` were included only to provide
structural coverage. Their presence does not validate the supervisor's CASE1
and CASE2 retrieval expectations or any formal duplication decision. Those
cases must later be executed without filtering on expected `proposal_id`.

## Notebook 2 relationship validation

### Identifier hierarchy

The tested records were consistent with the directional hierarchy:

`Proposal → optional Group OUS → Member OUS → ASDM`

No violations were observed for Member OUS → Proposal, Member OUS → Group OUS,
Group OUS → Proposal, or ASDM → Member OUS. These relationships are not
one-to-one. In particular, one tested Member OUS contained two ASDMs.

### Source Context

The internal Source Context is provisionally defined as:

`(member_ous_uid, parsed obs_id source)`

Across the 1,226-row extended sample, Source Context consistently determined:

- target name;
- central coordinate;
- spatial footprint;
- mosaic state;
- geometry type;
- ASDM association;
- antenna-array description;
- frequency-range signature;
- spatial resolution;
- continuum sensitivity.

Line sensitivity was the exception:
`(Member, source) → sensitivity_10kms` produced 184 violations. Line sensitivity
must therefore remain associated with the source–SPW Archive record rather than
being represented as one Source Context value.

Source Context is an internal data-model concept and is not claimed to be an
official ALMA Archive entity.

Notebook 3 does not invalidate the observed Source Context stability in the
Notebook 2 sample, but it limits how that result may be generalized. Later
samples contained multiple exact `frequency_support` strings within the same
Member OUS, and the available multi-ASDM cases did not repeat the same parsed
source across executions.

Consequently, `frequency_support`, antenna metadata, time bounds, spatial
resolution, and continuum sensitivity should currently be stored
conservatively through a Source–Execution Context. They may later be promoted
to a simpler ownership level only after broader validation.

### Spectral windows and frequency

Exact frequency was not determined by `(Member, SPW)` or `(ASDM, SPW)` in the
tested data. Source-dependent frequency spreads ranged from approximately
0.027 MHz to 5.52 MHz, while bandwidth remained stable in the tested cases.

The model should distinguish:

- a logical SPW identifier;
- nominal bandwidth;
- source-specific exact frequency;
- row-level line sensitivity;
- raw `frequency_support`;
- a later tolerance-aware frequency representation.

### Mosaic and spatial metadata

Four Member OUS datasets contained both mosaic and non-mosaic records. In all
eight affected Source Contexts, `is_mosaic`, geometry type, and `s_region` were
individually stable. The mixed Member-level state was caused by different
source contexts rather than variation between SPWs of the same source.

The data model must keep the following concepts separate:

- raw source label;
- physical-target candidate;
- central coordinate;
- spatial footprint;
- mosaic state;
- Member-level derived mosaic state.

A Polygon footprint does not imply a mosaic, and multiple source contexts do
not imply a mosaic. Member-level mosaic state may be derived as non-mosaic,
mosaic, mixed, or unknown.

### Observation role and release metadata

In a targeted 836-row query without a science-only filter:

- 600 rows had `science_observation = 'T'` and `scan_intent = 'TARGET'`;
- 236 rows had `science_observation = 'F'` and calibration/checking intents.

Candidate-key tests found no duplicate `obs_id`, Member–source–SPW, or
Member–source–SPW–role combinations. Observation role was not required to make
the tested row keys unique. Candidate retrieval for duplication checking should
normally retain the `science_observation = 'T'` filter.

All 836 role-test rows simultaneously had `data_rights = 'Proprietary'`,
`qa2_passed = 'F'`, and an `obs_release_date` beginning with `3000-01-01`.
This association does not establish the official meaning of the date. The raw
date, access state, and QA status must be preserved separately.

## Preliminary internal model after Notebook 4

The current evidence supports a relational rather than flat interpretation:

`Proposal → optional Group OUS → Member OUS`

Within one Member OUS, the Archive may contain:

- one or more Source Contexts;
- one or more Logical SPWs;
- one or more ASDM associations;
- one or more Source–Execution Contexts;
- one or more exact frequency-support signatures;
- source–SPW-related Archive records.

The model separates:

1. **Archive Query Run** — preserves endpoint, ADQL, parameters, limits,
   expected rows, retrieved rows, completeness, and retrieval time.
2. **Raw Archive Row** — preserves every original TAP value and unit.
3. **Proposal** — preserves the proposal identifier.
4. **Optional Group OUS** — preserves the Group OUS identifier when available.
5. **Member OUS** — provides the outer grouping container.
6. **ASDM Execution** — preserves ASDM-related execution provenance.
7. **Source Context** — preserves raw source and target metadata without
   claiming global physical-target identity.
8. **Spatial Footprint** — preserves coordinates, raw `s_region`, geometry, and
   mosaic state.
9. **Source–Execution Context** — conservatively stores source/ASDM contextual
   metadata whose final ownership remains uncertain.
10. **Logical SPW** — stores the parsed SPW identifier and candidate nominal
    bandwidth.
11. **Frequency-Support Signature** — preserves one exact raw support string and
    its geometry and sensitivity signatures.
12. **Frequency-Support Component** — stores one parsed bracketed component.
13. **SPW–Support-Component Mapping** — stores the provisional mapping,
    numerical differences, method, and validation status.
14. **Source–SPW Record** — preserves exact row-level frequency, bandwidth,
    line sensitivity, and row identifiers.
15. **Physical-Target Candidate** — provides a future optional normalization
    layer without overwriting raw labels or observational contexts.
16. **Normalized Frequency Coverage** — provides a future comparison-ready
    representation without embedding policy tolerances in the Archive model.
17. **Observation-Mode Evidence** — preserves comparable bandwidth,
    resolution, sensitivity, and coverage evidence without assigning FDM/TDM
    or a formal duplication result.

## Current implementation implications

1. Preserve every raw Archive row and its original identifiers.
2. Use `member_ous_uid` as the outer dataset-grouping key.
3. Represent Group OUS as optional and normalize empty identifiers to missing
   values.
4. Represent ASDM as an association because one Member may reference multiple
   ASDMs.
5. Reconstruct Source Context using `(member_ous_uid, parsed obs_id source)`
   and use `(Member, ASDM, source)` as the conservative Source–Execution
   Context.
6. Store coordinates, footprint, mosaic state, and geometry through Source
   Context and Spatial Footprint records. Store uncertain execution-related
   metadata conservatively through Source–Execution Context.
7. Represent spectral windows as variable-length collections.
8. Store exact frequency and `sensitivity_10kms` at source–SPW record level.
9. Preserve every raw `frequency_support` string and parse it into separate
   signature and component records without overwriting the raw text.
10. Use explicit units: GHz for `frequency`, Hz for `bandwidth`, arcseconds for
    spatial resolution, and mJy/beam for Archive sensitivity fields.
11. Do not use `target_name`, `obs_publisher_did`, or coordinate equality as an
    Archive-row primary key.
12. Keep science targets separate from calibration and checking records using
    `science_observation` and `scan_intent`.
13. Preserve `data_rights`, `qa2_passed`, and raw `obs_release_date` as separate
    fields.
14. Separate exact support-string equality, spectral-geometry equality, and
    sensitivity equality.
15. Do not assume one support signature per Member OUS.
16. Do not treat support-component order as an official SPW identifier. Use a
    validated context-level one-to-one mapping because support intervals may
    overlap.
17. Preserve Archive bandwidth and parsed interval width separately.
18. Preserve row-level and parsed 10-km/s sensitivities separately.
19. Do not equate component-level native sensitivity with aggregate continuum
    sensitivity.
20. Record parser version, parse status, validation issues, mapping method, and
    provenance for every derived spectral value.
21. Treat `spectral_resolution` as SPW-level evidence, `em_resolution` as
    derived wavelength-resolution metadata, and `velocity_resolution` as a
    separately preserved setup summary.
22. Preserve aggregate STC-S footprints, but do not claim that ObsCore exposes
    individual mosaic pointings.
23. Keep frequency tolerances and duplication decisions outside the Archive
    reconstruction layer.
24. Treat mosaic-overlap calculation, moving objects, primary-beam calculation,
    spectral smoothing, sensitivity policy, and duplication-rule thresholds as
    later validation tasks.

## Remaining questions

The following questions are intentionally deferred to later notebooks and
implementation tasks:

- validating the parser against additional Archive formats and future schema
  changes;
- confirming the scientific meaning of the provisional SPW-to-component
  mapping;
- defining tolerance-aware frequency equivalence;
- interpreting and comparing sensitivity at compatible resolutions;
- distinguishing continuum, spectral-line, FDM, and TDM setups;
- validating spectral-smoothing and primary-beam calculations;
- retrieving or reconstructing mosaic pointings;
- representing moving objects and Solar observations;
- mapping current-cycle CSV records into the internal model;
- validating the final duplication rules with known examples.
