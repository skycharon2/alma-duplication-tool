# ALMA Archive Data Dictionary

This document records the mapping between ALMA Archive metadata and the
preliminary internal data model of the duplication-checking tool.

The mappings are based on exploratory queries to the European ALMA TAP service,
official metadata from `TAP_SCHEMA.columns`, and the structural validation
performed in Notebooks 1 and 2. Unless explicitly identified as an official
field definition, relational constraints remain supported by the tested samples
rather than guaranteed for the complete Archive.

## Archive columns

| Archive column | Type | Unit | Current interpretation and model scope |
|---|---|---|---|
| `proposal_id` | string | — | ALMA proposal/project identifier; Proposal-level field |
| `obs_publisher_did` | string | — | Publisher identifier; matched `ADS/JAO.ALMA#<proposal_id>` for all 1,226 extended-sample rows and behaved as proposal-scoped |
| `group_ous_uid` | string | — | Optional Group OUS identifier; empty strings must be normalized to missing values |
| `member_ous_uid` | string | — | Member OUS dataset identifier and primary grouping key for reconstructing related Archive rows |
| `asdm_uid` | string | — | UID of the ASDM containing the field; one Member may reference multiple ASDMs |
| `obs_id` | string | — | Internal dataset identifier; encoded Member, source, and SPW components in all tested rows |
| `target_name` | string | — | Intended target name; useful for display but not a reliable physical-target identifier |
| `s_ra` | float | deg | ICRS right ascension of the central coordinate |
| `s_dec` | float | deg | ICRS declination of the central coordinate |
| `s_region` | region/string | — | Spatial footprint bounded by the observation; stable at Source Context level in the extended sample |
| `frequency` | float | GHz | Observed/tuned reference frequency on the sky; exact value belongs to the source–SPW record |
| `bandwidth` | float | Hz | Total bandwidth; must be explicitly converted before comparison with GHz values |
| `frequency_support` | string | embedded mixed units | Description of all frequency ranges used by the field, including resolution, sensitivity, and polarization |
| `spatial_resolution` | float | arcsec | Archive spatial-resolution summary; stable at Source Context level in the extended sample |
| `sensitivity_10kms` | float | mJy/beam | Estimated line sensitivity normalized to 10 km/s; varied between SPWs and belongs at source–SPW level |
| `cont_sensitivity_bandwidth` | float | mJy/beam | Estimated continuum noise over the aggregate bandwidth; stable at Source Context level in the extended sample |
| `antenna_arrays` | string | — | Blank-separated pad–antenna pairs; source/ASDM contextual metadata |
| `is_mosaic` | string | — | `T`/`F` mosaic flag; stable within tested Source Contexts but not always single-valued at Member level |
| `band_list` | string | — | ALMA receiver-band description; not a substitute for exact frequency coverage |
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

## Frequency-support representation

The inspected `frequency_support` values described complete correlator setups
as frequency ranges separated by ` U `.

Example:

```text
[689.28..691.15GHz,976.56kHz,10.8mJy/beam@10km/s,1.2mJy/beam@native, XX YY]
U
[691.10..692.98GHz,976.56kHz,10.8mJy/beam@10km/s,1.2mJy/beam@native, XX YY]
U
[702.98..704.86GHz,976.56kHz,10.5mJy/beam@10km/s,1.2mJy/beam@native, XX YY]
U
[706.65..708.53GHz,976.56kHz,10.5mJy/beam@10km/s,1.2mJy/beam@native, XX YY]
```

The line breaks above were added for readability. Each component may contain:

- lower and upper frequencies in GHz;
- frequency resolution, for example in kHz;
- sensitivity at 10 km/s in mJy/beam;
- sensitivity at native resolution in mJy/beam;
- polarization products.

For this example, four components were present, each with a bandwidth of
approximately 1.875 GHz. The frequency resolution was 976.56 kHz, the line
sensitivities were approximately 10.5–10.8 mJy/beam at 10 km/s, the native
sensitivity was 1.2 mJy/beam, and the polarization products were `XX YY`.

Exact `frequency_support` string equality is too strict for comparing frequency
coverage because strings with the same ranges may differ in sensitivity or
other embedded metadata. A parser will be developed and validated separately.

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

## Preliminary internal model

The current evidence supports the following structure:

`Proposal → optional Group OUS → Member OUS → Source Context × Logical SPW → Archive Row`

The internal representation should separate:

1. **Raw Archive Row** — preserve all original values and identifiers.
2. **Proposal** — store `proposal_id` and proposal-scoped publisher metadata.
3. **Group OUS** — represent as optional.
4. **Member OUS** — group related Archive records.
5. **ASDM association** — allow one Member to reference multiple ASDMs.
6. **Source Context** — store source label, coordinates, footprint, mosaic
   state, ASDM association, spatial resolution, and continuum sensitivity.
7. **Logical Spectral Window** — store SPW identifier and nominal bandwidth.
8. **Source–SPW Record** — store `obs_id`, exact frequency, line sensitivity,
   and other row-level values.
9. **Physical-Target Candidate** — support later normalization without
   overwriting raw source labels or observational contexts.

## Current implementation implications

1. Preserve every raw Archive row and its original identifiers.
2. Use `member_ous_uid` as the outer dataset-grouping key.
3. Represent Group OUS as optional and normalize empty identifiers to missing
   values.
4. Represent ASDM as an association because one Member may reference multiple
   ASDMs.
5. Reconstruct Source Context using `(member_ous_uid, parsed obs_id source)`.
6. Store coordinates, footprint, mosaic state, geometry, spatial resolution,
   and continuum sensitivity at Source Context level when validated.
7. Represent spectral windows as variable-length collections.
8. Store exact frequency and `sensitivity_10kms` at source–SPW record level.
9. Preserve `frequency_support` as raw text until its components have been
   parsed and validated.
10. Use explicit units: GHz for `frequency`, Hz for `bandwidth`, arcseconds for
    spatial resolution, and mJy/beam for Archive sensitivity fields.
11. Do not use `target_name`, `obs_publisher_did`, or coordinate equality as an
    Archive-row primary key.
12. Keep science targets separate from calibration and checking records using
    `science_observation` and `scan_intent`.
13. Preserve `data_rights`, `qa2_passed`, and raw `obs_release_date` as separate
    fields.
14. Treat mosaic-overlap calculation, moving objects, frequency parsing, and
    duplication-rule thresholds as later validation tasks.

## Remaining questions

The following questions are intentionally deferred to later notebooks and
implementation tasks:

- parsing every component of `frequency_support`;
- matching an Archive row to a parsed support interval;
- defining tolerance-aware frequency equivalence;
- interpreting and comparing sensitivity at compatible resolutions;
- distinguishing continuum, spectral-line, FDM, and TDM setups;
- retrieving or reconstructing mosaic pointings;
- representing moving objects and Solar observations;
- mapping current-cycle CSV records into the internal model;
- validating the final duplication rules with known examples.

