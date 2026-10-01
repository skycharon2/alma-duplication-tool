# Queue array and beam inference, version 2

Date: 2026-10-01. Project implementation decision supplied and explicitly adopted
by the project owner. Scope: Queue fixed celestial, single-field, regular-SPW
assessment. This replaces the unconditional absent-column 12-m assumption of
[the September 24 decision](queue_row_beam_decision_2026-09-24.md).
It does not change the raw parser, Archive scientific methods, continuum/LINE
formula definitions or source-row identity.

Supplied specification: `queue_array_beam_inference_spec.md`.
SHA-256: `365de3f6cedba1a93ef5169e6fb31a337c3629d42b4263078ca60b2ec79ae314`.
The specification describes the AR inference as supervisor-approved; this record
preserves that supplied approval basis and does not claim a new independent review.

## Evidence and decision

Operational `standAlone_ACA` has priority. True selects 7 m, plus 12 m if TP is
requested. False selects 12 m, plus 7 m if requested. Inconsistent standalone
true/Use 7-m false is recorded. Empty, invalid or duplicate operational fields
are unresolved, never treated as absent. Invalid typed auxiliary flags remain
unresolved; normal parser errors still prevent unsafe source reconstruction.

Only an absent operational field uses the adopted inference:

- Use 7-m false: 12 m.
- Use 7-m true and TP true: 7 m + 12 m immediately.
- Use 7-m true and TP false: requested AR strictly below the band threshold
  gives 7 m + 12 m; equality or greater gives 7 m.
- Required AR/band unresolved: no diameter hypothesis.

No inferred boolean replaces a missing standalone source value. A compatible
7-m result is labeled `7M_COMPATIBLE_INFERENCE`. TP contributes a 12-m beam
hypothesis under this project decision; this is not independent TP sensitivity
telemetry or a general TP-only science evaluator. Identical diameters are
collapsed while their source/component reasons are retained.

## Fixed threshold table

Checked against [Cycle 13 Proposer's Guide, Table A-1](https://almascience.eso.org/proposing/proposing/proposers-guide)
on 2026-10-01. The table supports the numeric inputs; the absent-field inference
and full-variant interpretation are the supplied project decision.

| Band | Representative GHz | 7-m AR (arcsec) |
| --- | --- | --- |
| 1 | 40 | 31.8 |
| 2 | 75 | 16.9 |
| 3 | 100 | 12.7 |
| 4 | 150 | 8.47 |
| 5 | 185 | 6.87 |
| 6 | 230 | 5.52 |
| 7 | 345 | 3.68 |
| 8 | 460 | 2.76 |
| 9 | 650 | 1.95 |
| 10 | 870 | 1.46 |

This is an inference table, not an observing-cycle feasibility check. There is
no interpolation or scaling with Ref.Frequency, and no use of Req. LAS.

## Complete variants and versioning

Profile: `QUEUE_ARRAY_BEAM_INFERENCE_2`; position: `queue_pos_single_6`;
complete-branch OR: `queue_beam_variant_or_1`. Position reuses
FWHM=1.13*c/(frequency*D), half-FWHM radius and inclusive spherical comparison.
Frequency, offset transport and unsupported-target/geometry gates are unchanged.

A MIX row runs all requested branches independently for both diameters. For each
branch, any MET wins; without a MET, any unknown remains INDETERMINATE; otherwise
NOT_MET. Never combine individual conditions across variants. Original candidate
identity occurs once. Report-local variant IDs append `#beam-7m` or `#beam-12m`.
The [current contract](../queue_common.md) defines the additive report-v4 fields,
inspection-v3 traversal and matching-diameter evidence. Historical documents and
saved reports retain the meanings of their original methods.

## Verification scope

Tests cover the operational/absent flag matrix, all ten bands below/equal/above,
Band 6 at 5.51/5.52/5.53 arcsec and adjacent floating-point canonical values,
invalid evidence, TP deduplication and standalone inconsistency. Full assessment
checks cover physical 7-m-only matches, both/neither matches, three-valued OR,
cross-variant borrowing rejection, source identity, hidden candidates, LINE pair
bindings, inspection pointers, browser presentation and byte-identical downloads.

At one frequency and centre the 7-m beam contains the 12-m beam. A physical
7-m position failure with a 12-m position pass is impossible. Reverse OR order
is therefore tested with synthetic complete branch outcomes, not fabricated sky
geometry. Engineering tests do not add reviewed real-proposal labels.
