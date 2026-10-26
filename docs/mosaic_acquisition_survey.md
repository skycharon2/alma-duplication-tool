# Mosaic acquisition survey and s_region comparison

## Scope and reproduction

The 2026-10-26 experiment separates product availability, successful science-field
reconstruction and position readiness. None is inferred from the other. It does not
change the production position rule or claim a representative Archive-wide success
rate. Local raw responses and package inspection receipts remain under
`reports/mosaic-dev/acquisition-survey-01/`, `acquisition-inspection-01/`,
`acquisition-inspection-02/` and `acquisition-inspection-nonsolar-01/`.

```sh
python -m experiments.mosaic_acquisition_survey.run --output-dir reports/mosaic-dev/new-survey
python -m experiments.mosaic_acquisition_survey.inspect_sample \
  --survey reports/mosaic-dev/new-survey/survey.json --output-dir reports/mosaic-dev/new-inspection
python -m experiments.mosaic_acquisition_survey.compare_case2 --output-dir reports/mosaic-dev/new-region-comparison
```

The survey queries ten strata: project years 2013, 2016, 2019, 2022 and 2024,
each below/above 200 GHz. Each query takes an ordered pool of at most 50 rows and
selects five Member/target identities, preferring distinct projects. This is a bounded
convenience sample, not random sampling. Arrays, mosaic size and pipeline version
have not yet been balanced; a larger follow-up must explicitly stratify those too.

## Results

Of 50 selected identities, 49 had one accessible auxiliary candidate accepted by the
existing receipt validator and one had none. Two selected identities were explicitly
named Sun and are excluded from duplication applicability. Thus 47 of the remaining
48 had a product, not necessarily usable pointing evidence. The 49 products advertised
31,411,456,512 bytes in total; 17 were within the default 300 MB download limit.
Only metadata was fetched for the complete sample.

The inspection experiment reserves at most 200 MB in aggregate and at most 100 MB
per selected package. It sets the downloader cap to the advertised size for each
selected product, so a changed larger product cannot bypass the reservation. It
prefers the smallest package per stratum and skips explicitly solar targets.
The final non-solar subset reserved 99,412,992 bytes for three packages:

| Target | Member | Result |
| --- | --- | --- |
| SgrA_star | uid://A001/X122/X407 | No listobs found in current inspection scope |
| N55 | uid://A001/X145/X43d | No listobs found; calibrated log archive lies outside current weblog scope |
| LMC0NT197 | uid://A001/X879/X6e7 | Target mismatch: parser encounters ON_SOURCE LMC1N127 |

None of these three produced a usable bound execution. This does not establish that
pointings are absent: for N55 another log container was skipped, and the LMC failure
shows a target-selection limitation requiring investigation in a multi-target MS.
Do not loosen identity matching or count another target's fields as a successful
reconstruction. Existing CASE2 and IC1954 successes remain separate evidence.

Initial inspection included two solar packages before the scope review; those runs
are preserved and not included as duplication successes. One exposed a real parser
bug: a listobs.png plot was decoded as UTF-8 listobs text. Known image/PDF/SVG listobs
artifacts are now recorded as NON_TEXT_LISTOBS_ARTIFACT and skipped. Text and unknown
formats still undergo strict validation. Regression tests preserve this distinction.

## s_region comparison

For the eight captured CASE2 contexts, use production-bound execution circles and
Archive frequency/array evidence, then compare sampled membership to the associated
STC-S polygon. The diagnostic supports small simple ICRS polygons within one degree
of the projection origin, with gnomonic projection and minor great-circle edges.
Other shapes fail explicitly. It samples a 41 by 41 bounding grid, polygon vertices,
circle centres and rings at 0.99, 1.00 and 1.01 radii. Boundary tolerance is 0.001 arcsec.

Each context has 2143 probes. BEAM_ONLY counts range from 22 to 78; two contexts also
have one REGION_ONLY point. Recorded disagreement witnesses lie roughly 0.0015 to
0.0683 arcsec inside the beam-union boundary, or about 0.0033 arcsec outside it.
These are sampled edge differences, not sky-area fractions or astrometric errors.
Polygon discretization and frequency-dependent radii are hypotheses to test, not
established causes. Only CASE2 was compared, and only metadata-bound execution
coverage was used. No whole-Member equivalence or inclusion relationship is proven.

The result does not support treating s_region as an exact replacement for the current
circle union, nor does it prove severe overall disagreement. More than 50% is sensitive
to individual edge classifications. A future conservative region method needs
validated inner/outer error bounds; fitting pointing centres from boundary vertices
would not establish their historical identity or number.

ALMA's official query notebook describes s_region as a footprint for intersection
queries, not a pointing list:
https://almascience.eso.org/alma-data/archive/archive-notebooks/nb1_ALMA_Query_one_source.html
The Pipeline user guide describes Spatial Setup and Listobs Output on MS overview
pages, supporting further investigation of those alternative evidence paths:
https://almascience.nrao.edu/processing/alma_pipeline_user_s_guide_for_release_2024-1.pdf

## Next experiments

Prioritize target-aware extraction in the LMC multi-target MS and bounded inspection
of N55's calibrated logs. Keep science-scan identity and per-target completeness
explicit. Expand region comparisons to further fixed, non-solar cases with verified
pointings before proposing any production s_region fallback. The committed result
summary is `experiments/mosaic_acquisition_survey/results-2026-10-26.json`; large
packages and generated run directories remain ignored.

## Multi-target parser follow-up

The original LMC0NT197 MeasurementSet contains three science targets. The parser
now validates all ON_SOURCE scan names against their FIELD entries, then selects
only the exact requested target. Excluded science fields and their scan IDs are
recorded in the acquisition inspection. Conflicting identities, missing FIELD rows,
unsupported frames and absent requested targets remain errors.

An offline replay of the cached 76,870,656-byte package reconstructed
`uid://A002/Xb8f857/X3977` with three LMC0NT197 science fields and no unresolved
executions. Six fields belonging to the other two targets were excluded. The report
is `reports/mosaic-dev/lmc-target-selection-01/package_audit.json`.
This repairs the earlier parse failure; it does not establish complete Member
coverage or a final duplication decision.

Manual bounded inspection of N55's `calibrated.log.tgz` found only a 208-byte
CASA startup log, with no MeasurementSet header or FIELD coordinates. That evidence
is retained as a negative fixture. General CASA log parsing has not been enabled:
this package supplies no positive example on which to validate such a fallback.
N55 therefore remains unresolved through the inspected route.
