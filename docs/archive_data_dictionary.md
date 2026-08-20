# ALMA Archive Data Dictionary

This document records the preliminary mapping between ALMA Archive metadata
and the internal data model of the duplication-checking tool.

The mappings are based on initial queries to the European ALMA TAP service
and remain subject to further validation.

## Archive columns

| Archive column | Type | Unit | Preliminary interpretation |
|---|---|---|---|
| `proposal_id` | string | — | ALMA proposal/project identifier |
| `target_name` | string | — | Target name supplied in the proposal |
| `s_ra` | float | deg | Right ascension in ICRS |
| `s_dec` | float | deg | Declination in ICRS |
| `s_region` | region/string | — | Spatial footprint used for coordinate-intersection queries |
| `frequency` | float | GHz | Central frequency associated with the returned record |
| `bandwidth` | float | Hz | Bandwidth associated with the returned record |
| `frequency_support` | string | — | Frequency-support description containing one or more frequency ranges |
| `spatial_resolution` | float | arcsec | Spatial/angular resolution |
| `sensitivity_10kms` | float | mJy/beam | Spectral-line sensitivity normalized to 10 km/s |
| `cont_sensitivity_bandwidth` | float | mJy/beam | Continuum sensitivity over the aggregate bandwidth |
| `group_ous_uid` | string | — | Group OUS identifier |
| `member_ous_uid` | string | — | Member OUS identifier and candidate grouping key |
| `obs_id` | string | — | Archive record identifier; contained source and spectral-window components in the test sample |
| `asdm_uid` | string | — | ASDM-related identifier; distinct from `member_ous_uid` in the test sample |
| `antenna_arrays` | string | — | Antenna-array information associated with the record |
| `is_mosaic` | string | — | Mosaic flag represented as `T` or `F` |

## Initial observations

- Multiple rows may share the same proposal, target, and Member OUS while
  containing different central frequencies.
- Archive records must therefore be grouped before a complete correlator
  setup can be reconstructed.
- Archive bandwidth values are returned in Hz.
- Archive sensitivities are returned in mJy/beam.
- The five-row initial sample contained no missing values, but it is not
  representative of the complete Archive.
- The exact relationship between Archive rows, spectral windows, datasets,
  and Member OUS identifiers requires further investigation and validation
  using additional targets.

## Coordinate-query experiment

A coordinate query was performed around:

- Right ascension: 201.365 deg
- Declination: -43.019 deg
- Search radius: 0.006 deg = 21.6 arcsec
- Coordinate frame: ICRS
- Observation filter: `science_observation = 'T'`

The initial exploratory query used `TOP 100`. A separate `COUNT(*)` query
showed that 434 rows matched the spatial constraints. The query was therefore
repeated without `TOP 100`, and all 434 rows were retrieved successfully.

### Identifier counts

| Identifier | Unique values |
|---|---:|
| `proposal_id` | 24 |
| `group_ous_uid` | 82 |
| `member_ous_uid` | 108 |
| `obs_id` | 434 |
| `asdm_uid` | 108 |
| `target_name` | 8 |

The 434 Archive rows must not be interpreted as 434 independent
observations. In this sample, the `obs_id` values contained source and
spectral-window components such as `.source.<name>.spw.<number>`, which is
consistent with source--spectral-window records. Multiple rows belonged to
the same Member OUS.

The eight distinct target-name strings also demonstrate that target names
alone are not reliable identifiers for fixed celestial sources. Coordinate
and footprint matching must be used as the primary spatial comparison.

### Member OUS grouping observations

For all 108 Member OUS groups in this coordinate-query sample:

- every `obs_id` was unique within its Member OUS;
- every Member OUS was associated with one ASDM UID;
- every Member OUS was associated with one Group OUS UID;
- every Member OUS had one consistent `is_mosaic` value;
- every Member OUS had one consistent `frequency_support` value.

These are observations from the current test sample and must not yet be
treated as guaranteed constraints for the complete ALMA Archive.

The number of matching Archive rows per Member OUS was variable:

| Matching rows per Member OUS | Member OUS count |
|---:|---:|
| 3 | 10 |
| 4 | 92 |
| 5 | 4 |
| 8 | 2 |

The application must therefore support a variable number of matching Archive
records per Member OUS. It must not assume that every Member OUS contains
exactly four records or exactly four spectral windows.

### Member OUS and ASDM identifiers

The sample contained 108 unique Member OUS--ASDM pairs. Each Member OUS was
associated with one ASDM UID, and no ASDM UID was connected to multiple
Member OUS identifiers in this sample.

However, `member_ous_uid` and `asdm_uid` are distinct identifier values.
None of the 434 rows had identical values for these two fields. They must
therefore remain separate fields in the application data model.

The observed one-to-one relationship is sample-specific and must not yet be
treated as an Archive-wide guarantee.

### Mosaic observations

| Mosaic flag | Archive rows | Proposals | Member OUS | ASDM |
|---|---:|---:|---:|---:|
| `F` | 324 | 22 | 79 | 79 |
| `T` | 110 | 12 | 29 | 29 |

The Archive-row count must not be used as the number of mosaic observations.
For this sample, 110 mosaic-related rows corresponded to 29 Member OUS
groups.

A proposal may contain both mosaic and non-mosaic Member OUS groups.
Consequently, proposal counts in the two categories are not mutually
exclusive.

The `is_mosaic` flag identifies whether a record is associated with a mosaic,
but it does not by itself provide the percentage of overlapping mosaic
pointings required by the ALMA duplication rules. Additional spatial
information will be needed for the mosaic-overlap calculation.

### Frequency-support representation

For the inspected example Member OUS, `frequency_support` appeared to
describe the complete correlator setup as frequency ranges joined by `U`.

The same `frequency_support` value was repeated across all matching rows of
that Member OUS.

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

The line breaks above were added for readability. The Archive returned the
frequency-support description as one string with components separated by
` U `.

Each frequency-support component may contain:

- lower and upper frequency in GHz;
- frequency resolution, for example kHz;
- sensitivity at 10 km/s in mJy/beam;
- sensitivity at native resolution in mJy/beam;
- polarization products.

For the inspected example:

- four frequency-support components were present;
- every component had a bandwidth of approximately 1.875 GHz;
- the frequency resolution was 976.56 kHz, equivalent to 0.97656 MHz;
- the line sensitivities were approximately 10.5--10.8 mJy/beam at 10 km/s;
- the native sensitivity was 1.2 mJy/beam;
- the polarization products were `XX YY`.

Duplication checks should eventually compare a proposed observing frequency
with the complete frequency interval rather than comparing only central
frequency values.

A parser for `frequency_support` will be developed and validated separately.
It must support a variable number of frequency-support components and must
not assume that all records use the same units or string structure.

## Current implementation implications

The current Archive investigation suggests the following preliminary design:

1. Use `s_region` and ADQL spatial-intersection queries for fixed-source
   candidate retrieval.
2. Do not use `target_name` as the primary identifier for a fixed source.
3. Preserve the individual Archive rows returned by TAP.
4. Group related candidate rows using `member_ous_uid` when reconstructing
   an observing setup.
5. Preserve `group_ous_uid`, `member_ous_uid`, `asdm_uid`, and `obs_id` as
   separate identifiers.
6. Support a variable number of records and spectral windows per Member OUS.
7. Preserve both the individual `frequency` and `bandwidth` columns and the
   complete `frequency_support` string.
8. Convert units explicitly inside the application rather than relying on
   implicit assumptions.
9. Treat `is_mosaic` only as a classification flag; mosaic-overlap rules
   require additional spatial analysis.
10. Validate all preliminary assumptions with more targets and known
    duplication cases before implementing the final duplication rules.