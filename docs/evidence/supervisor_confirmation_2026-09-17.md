# Confirmed Archive workflow

## Confirmed 2026-09-21

Decision identifier: `confirmed-2026-09-21`.

Source: project developer supplied **ALMA Duplication Confirmed Implementation
Guide, 2026-09-21**, recording supervisor confirmation on 2026-09-17 and
clarifications on 2026-09-21. The supplied handwritten continuum and line notes
were checked against the guide. This is a developer-recorded confirmation, not
an independently obtained reviewer signature. The guide supersedes the older
reported centre-average proposal. No additional Q1–Q8 approval gate is required
for the expressly confirmed scope.

Normative scope: fixed celestial target, single pointing, one setup, one coherent
Archive context; uniquely resolved 12-m or 7-m interferometry. Archive ICRS
coordinates are interpreted in that fixed-celestial workflow. This is an explicit
scope convention, not a moving-object classifier or name resolver. Conflicting
external position interpretations block evaluation.

| Decision | Adopted implementation |
| --- | --- |
| Q1 | Candidate `frequency` and uniquely resolved diameter; radius `0.5 * 1.13 * c / (nu * D)`; spherical separation `<= radius` |
| ANGULAR | User requested arcsec versus Archive estimated `spatial_resolution`; symmetric factor <=2 |
| Q2 | At least two distinct usable proposed windows strictly >1.8 GHz; preserve nominal/unknown semantics; no arbitrary conversion |
| Q3 | User `representative_frequency` (SKY), never mean SPW centres; compare with Archive `frequency`, symmetric factor <=1.3 |
| Q4 | Line-only scaling `sigma10 * sqrt(10 / dv_plan) * (theta_plan/theta_archive)^2`; block RMS if Archive resolution is coarser |
| Q5 | Direct setup aggregate continuum RMS: Archive estimate <=2 times proposed requested RMS; no lower bound; no continuum angular/spectral correction |
| Q6 | Accepted operational mode source: em_xel <=128 → UI continuum/TDM; >=129 → UI line/FDM, with validity, metadata, association and conflict gates |
| Q7 | Coherent source/execution/SPW context; Member grouping is presentation only; CASE1/2 remain retrieval evidence |
| Q8 | Three-valued AND/OR; approved criterion outcomes only; one branch/context at a time; both intents display separate branches |

This approval does not extend Archive-only semantics to Queue, arbitrary nominal
bandwidth conversion, mosaic, TP, moving targets, mixed arrays, or mixed-setup
aggregation. Queue mappings retain their historical approval state.

## Executable method versions in this increment

- `archive_pos_single_1`: new candidate-side inclusive position rule.
- `archive_angular_factor_3`: confirmed Archive wrapper around the existing exact factor calculation.
- `continuum_setup_3`: confirmed no-conversion wrapper; caller-selected portal conversion remains provisional.
- `archive_cont_freq_1`, `archive_cont_rms_1`: direct confirmed comparisons.
- `branch_three_value_1`: continuum branch assessment, never search-wide absence.

Legacy `angular_factor_2`, `continuum_setup_2`, Queue position, and old serialized
reports are unchanged. New evaluation/report schemas are 3/2. Approval is about
a method within scope; missing metadata can still produce an approved method's
`INSUFFICIENT_INFORMATION` result.

The new position rule uses literal `<=` on float64 spherical distance and radius,
with no equality band. The earlier retrieval selector and Queue method retain
their versioned conservative boundary behavior. Numeric equality is tested at
an equatorial constructed boundary; arbitrary printed coordinates have finite
precision and should not be interpreted as exact mathematical equality.

A 90% majority array label is insufficient for a formal unique diameter: all
recognized antenna families must agree and there must be no unknown tokens.
Legacy explicit `12-m`/`7-m` labels remain supported. No effective mixed diameter
is fabricated.

## Evidence and acceptance

`examples/confirmed_continuum` is synthetic numerical acceptance based on guide
example A, with negative and missing-evidence variants. Its identifiers and
manifest explicitly say synthetic. NGC6240 remains a captured real Archive
response test, not a supervisor-labeled duplicate set. A supplied-source complete
query is not proof of full search coverage.

The line formulas and mode rule are confirmed engineering inputs for the next
increment. This patch supplies the reference model and acceptance specification;
it does not claim line evaluators have been delivered.

Official sources checked 2026-09-21:

- [Cycle 13 Users' Policies, Appendix A](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies)
- [Science Archive Manual, column descriptions and sensitivity estimates](https://almascience.eso.org/documents-and-tools/cycle13/science-archive-manual)

These sources define policy and Archive metadata semantics. The particular
representative-frequency choice and line RMS operationalization above come from
the supplied project confirmation.

## Supplied source fingerprints

- `.codex-upload-07b5bd2ec6a245f1ae64455cd422f5de`: SHA-256 `5c8a968363d32765fa68ef8beca6beb4c952ce6c372633502ce7318063b04418`
- `ALMA_Duplication_Confirmed_Implementation_Guide_2026-09-21(2).md`: SHA-256 `20c5b21ae8747ef7a3b04631b785fc8f15be316df64e49b9b0a3502834f03a64`
- `Project_Plan_9_14(1).pdf`: SHA-256 `7e964cb9419ab67f8b867f956f3dca0700be9c25ffb7f35edb432c28077449c0`
- `ノート 2(2).pdf`: SHA-256 `768d49447b76d183a0a8db7bba3bb8c3ce01342b16bc49c8535236ce642c7917`
- `ノート(2).pdf`: SHA-256 `5c8a968363d32765fa68ef8beca6beb4c952ce6c372633502ce7318063b04418`
