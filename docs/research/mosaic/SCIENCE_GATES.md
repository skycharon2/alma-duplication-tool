# Mosaic duplication: scientific decisions

The rules below apply to the Mosaic extension only. Existing Single Pointing decisions remain unchanged. The circular half-power beam union was accepted as the project coverage model on 2026-10-23, as recorded below. The remaining duplication rules still require separate decisions.

## Established rules

- [Cycle 13 Users' Policies, Appendix A](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies) requires **strictly more than half of the proposed Mosaic pointings** to lie within the other observation's half-power-beam coverage. The threshold is directional and concerns pointing count, not mapped area. Position is only one of the required duplication conditions.
- [Technical Handbook, section 3.2](https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook) defines HPBW/FWHM as a full width. For an assumed circular symmetric beam, its half-power radius is half that width; the project uses the circular half-power beam union recorded below.
- [OT Reference Manual](https://almascience.eso.org/documents-and-tools/cycle13/alma-ot-refmanual) distinguishes Rectangle combined-image sensitivity from Custom per-pointing sensitivity. The 7-m and 12-m grids cannot be assumed interchangeable. TP on-the-fly scanning is not a list of interferometric field centres.

## Decisions required before duplication verdicts

| Topic | Outstanding decision | Original questions |
| --- | --- | --- |
| Spatial coverage | Circular half-power beam union accepted; comparison-frequency selection, array applicability, exact-edge and uncertainty handling remain to be specified. | M01-M02 |
| Observation modes | Single/Mosaic directional combinations; permitted 7-m/12-m comparisons and result aggregation; treatment of non-solar TP. | M04-M06 |
| Sensitivity | Comparable RMS/depth quantity for Custom versus Rectangle, partial coverage, and continuum/line setups. | M07 |
| Counting and completeness | Pointing identity across duplicate positions, tunings and executions; allowed conclusions from partial lists. | M03, M10 |
| Direction and source identity | Accepted Archive direction type; whether any restricted Queue grouping fallback is scientifically admissible. | M09, M11 |

M08 (coordinate/frame validation), M09 (authoritative Queue source mapping), M11 (Archive metadata extraction), and M12 (Mosaic candidate discovery) also require evidence and engineering work. Controlled OT export results do not determine a scientific positional tolerance.

## Implementation gate

A Mosaic verdict requires verified proposed and candidate pointing inputs with source, setup, array, frame, direction provenance and completeness; a recorded decision for every scientific rule used; separate tests for the position, resolution, and continuum/line conditions; and a candidate-discovery method with documented limits and recall tests.

Until those conditions are met, report the relevant evidence as unassessed. Do not infer pointings from a footprint, group Queue rows by target name alone, or treat missing data as a negative duplication result.

When a decision is made, record its date, reviewer, source reference, scope, and a worked boundary example here before using it in code.

## Coverage model decision — 2026-10-23

Yuki Shi reported confirmation with the project supervisor to use the implemented
union of pointing-centred circular half-power disks as “the half power beam width
area covered by the other observation.” This records project-level acceptance;
it does not claim a separate endorsement by ALMA. The supervisor's name was not
provided. The source of this decision is Yuki Shi's confirmation on 2026-10-23.

For each eligible pointing, the current model uses HPBW = k c / (frequency ×
dish diameter), with radius HPBW / 2, and spherical angular distances. The worked
runs use k = 1.13 and the reported SPW centre. Coverage is the union of these disks,
not a sum of responses or the sampled TAP s_region polygon. Selecting a comparison
frequency or combining arrays/executions is outside this model-choice confirmation.

Worked example: IC1954, ASDM uid://A002/Xc63024/X4c8, SPW 16, 7 m dishes,
229.7063782 GHz and k = 1.13 give 22 disks of radius 21.728171955726108 arcsec.
A point on one disk's edge can be inside the union if it lies inside another disk.
Points on the union boundary retain the explicit BOUNDARY classification; the
counting treatment of this numerical band remains a separate decision.

This acceptance resolves the beam-union versus combined-response model choice.
It does not establish Member completeness, approve all duplication conditions,
or convert the existing diagnostic reports into completed policy evaluations.
Existing diagnostic status strings remain historical implementation labels until
a versioned assessment interface incorporates this decision explicitly.
