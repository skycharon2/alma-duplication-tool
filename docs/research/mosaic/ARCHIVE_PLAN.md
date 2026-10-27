# Archive Mosaic pointing evidence

Historical pointing-acquisition plan. It remains useful for reconstruction research,
but does not set prerequisites for the current
[Archive s_region workflow](../../mosaic_s_region_position.md).

Status: local single-ASDM diagnostic fixtures now exist for both arrays. SPT0303-59 (`uid://A002/Xfb8480/X4f37`, 7m) has 19 science fields; NGC5248 (`uid://A002/Xeaae1d/X1a2`, 12m) has 11. The standalone comparison and local extraction tests pass for both samples. This does not establish full Member completeness or scientific approval of the coverage model.

Current files remain in `experiments/mosaic_footprint_ab/data/`; do not move or overwrite them simply to match the prospective receipt layout below. Next work is to document acquisition provenance, establish the completeness scope required by Appendix A implementation.

## First case

The original 7m starting case is:

| Field | Recorded value |
| --- | --- |
| Project / source | `2021.2.00176.S` / `SPT0303-59` |
| Member OUS | `uid://A001/X15aa/Xe5` |
| Sample ASDM | `uid://A002/Xfb8480/X4f37` |
| Sample observation ID | `uid://A001/X15aa/Xe5.source.SPT0303-59.spw.10` |
| Source-bound AQ array | `7m` |
| Auxiliary package size advertised by DataLink | 56,154,112 bytes; not downloaded |

The size makes this a practical starting point for product inspection; it does **not** establish that the auxiliary package contains a usable pointing list. The other recorded 7-m cases are `2017.1.01675.S` (`TUK93_122`) and `2023.1.00687.S` (`GMC104_south`).

## Investigation

1. **Establish the observation scope.** Recheck public/science/Mosaic selection and the exact Member, source, array, and ASDM associations. Enumerate the relevant executions and setups. A sampled TAP row or SPW is not a complete Member inventory. Preserve queries, response files, limits, timestamps, and hashes.
2. **Inspect products before downloading.** Look for individually accessible README, `listobs`, weblog, field, or scan metadata. Verify source and Member association before using a file. Do not automatically download the auxiliary tar or multi-GB ASDM/MS products. Record an unavailable product rather than assuming its contents.
3. **Extract science fields.** Retain the original `FIELD_ID`/`SOURCE_ID`, scan and intent, array, spectral-window or data-description association, EB/ASDM, direction values, reference frame, and product history. Exclude calibrator fields using intent evidence, not names alone. Preserve repeated records; do not merge fields by matching coordinates.
4. **Check direction meaning.** Distinguish scheduled/commanded field positions, MeasurementSet `PHASE_DIR`, and antenna/time-dependent `POINTING` directions. Processed products may have altered phase centres. The scientifically appropriate direction remains a separate decision.
5. **Reconcile completeness.** Compare the expected and extracted science fields, scans, and executions for the declared source/setup/array. Record missing EBs, count conflicts, limited queries, and processing losses. Completeness of this Member does not imply completeness of an Archive-wide candidate search.
6. **Validate the independent 12m case.** Apply the provenance and completeness checks to the existing NGC5248 fixture. Its fields are extracted independently, not inferred from the 7m grid.

## Evidence record

Store unmodified retrieved files under `evidence/archive_pointings/<receipt-id>/original/`, with acquisition source, query or product identifier, UTC time, SHA-256, and a small manifest. A case summary should include:

- Project, Member, ASDM/EB, source, array, and spectral setup;
- original field/scan identifiers, science intent, directions, frames, and units;
- expected versus observed counts and the basis for each count;
- missing metadata, conflicts, transformations, and the declared completeness scope.

Use explicit states such as `POINTING_LIST_UNAVAILABLE`, `PARTIAL`, `COUNT_CONFLICT`, or `SOURCE_BINDING_UNVERIFIED`. These are evidence labels, not implemented application statuses. Incomplete evidence must never support a global no-duplication conclusion.

## Exit criterion

Obtain one independently reviewable, source-bound 7-m science-pointing list and one 12-m list, **or** document the exact data/access limitation for each attempted case. This stage evaluates evidence feasibility only; it does not produce a Mosaic duplication verdict.

References: [ALMA Archive documentation](https://almascience.eso.org/alma-data/archive/archive-documentation), [MeasurementSet FIELD/POINTING specification](https://casacore.github.io/casacore-notes/229.html).
