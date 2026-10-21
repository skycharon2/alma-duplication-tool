# Mosaic duplication: scientific decisions

The rules below apply to the Mosaic extension only. Existing Single Pointing decisions remain unchanged. No new Mosaic comparison policy has been approved for implementation as of 2026-10-21.

## Established rules

- [Cycle 13 Users' Policies, Appendix A](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies) requires **strictly more than half of the proposed Mosaic pointings** to lie within the other observation's half-power-beam coverage. The threshold is directional and concerns pointing count, not mapped area. Position is only one of the required duplication conditions.
- [Technical Handbook, section 3.2](https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook) defines HPBW/FWHM as a full width. For an assumed circular symmetric beam, its half-power radius is half that width; the choice of Mosaic coverage model is still open.
- [OT Reference Manual](https://almascience.eso.org/documents-and-tools/cycle13/alma-ot-refmanual) distinguishes Rectangle combined-image sensitivity from Custom per-pointing sensitivity. The 7-m and 12-m grids cannot be assumed interchangeable. TP on-the-fly scanning is not a list of interferometric field centres.

## Decisions required before duplication verdicts

| Topic | Outstanding decision | Original questions |
| --- | --- | --- |
| Spatial coverage | Candidate beam union or combined Mosaic response; frequency and array dependence; exact-edge and uncertainty handling. | M01-M02 |
| Observation modes | Single/Mosaic directional combinations; permitted 7-m/12-m comparisons and result aggregation; treatment of non-solar TP. | M04-M06 |
| Sensitivity | Comparable RMS/depth quantity for Custom versus Rectangle, partial coverage, and continuum/line setups. | M07 |
| Counting and completeness | Pointing identity across duplicate positions, tunings and executions; allowed conclusions from partial lists. | M03, M10 |
| Direction and source identity | Accepted Archive direction type; whether any restricted Queue grouping fallback is scientifically admissible. | M09, M11 |

M08 (coordinate/frame validation), M09 (authoritative Queue source mapping), M11 (Archive metadata extraction), and M12 (Mosaic candidate discovery) also require evidence and engineering work. Controlled OT export results do not determine a scientific positional tolerance.

## Implementation gate

A Mosaic verdict requires verified proposed and candidate pointing inputs with source, setup, array, frame, direction provenance and completeness; a recorded decision for every scientific rule used; separate tests for the position, resolution, and continuum/line conditions; and a candidate-discovery method with documented limits and recall tests.

Until those conditions are met, report the relevant evidence as unassessed. Do not infer pointings from a footprint, group Queue rows by target name alone, or treat missing data as a negative duplication result.

When a decision is made, record its date, reviewer, source reference, scope, and a worked boundary example here before using it in code.
