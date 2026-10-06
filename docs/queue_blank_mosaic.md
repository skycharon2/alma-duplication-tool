# Queue blank Mosaic interpretation

## Evidence reviewed on 2026-10-06

The Cycle 13 CSV dictionary identifies `N/A` as a single pointing. The current
3200-row snapshot instead contains 120 blank Mosaic cells, 2940 `Custom` cells
and 140 `Rectangle` cells. Its SHA-256 is
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.

The [Portal-hosted Cycle 13 auxiliary script](https://almascience.eso.org/documents-and-tools/cycle13/python-script/view)
reads CSV with pandas' default missing-value handling. Its `isObsMosaic` function
treats missing values and `N/A` as non-mosaic. Its coordinate correction applies
provided offsets independently of that classification. The downloaded script
has 117603 bytes and SHA-256
`eed6c9f557e13ec9bdf1c5cf3fd3b370f6201bb52fd67f7cac1bb39960e40df9`, matching the
previous official-source capture. This is a user-contributed implementation
hosted by the Portal, not a normative policy or an official supported product.

The [official duplication page](https://almascience.eso.org/proposing/duplications)
explains that custom mosaics have one row per pointing. That statement alone
does not establish an independent single-point RMS interpretation for each row.
Custom and rectangular mosaic science remain outside this increment.

## Adopted interpretation

Current formal Queue methods may interpret the parser's
`UNSPECIFIED_WITH_OFFSET` as one pointing only when the source Mosaic token is
actually blank. Parsing remains lossless and unchanged: source snapshot, raw
Mosaic value and parsed geometry are retained. The report separately records
`PORTAL_BLANK_MOSAIC_SINGLE_POINTING` and `effective_queue_geometry=SINGLE_FIELD`.
This is an explicit project interpretation of the Portal workflow, not fabricated
source metadata or a change to an existing report.

The current row-beam adapter uses the existing spherical offset transport in
ICRS/J2000 or Galactic coordinates. It does not copy the auxiliary script's
small-angle coordinate addition. Frame, source binding, placeholder coordinates,
local-domain offset bounds, candidate frequency and diameter guards still apply.
Custom, Rectangle, unknown nonblank categories and conflicting evidence are not
promoted. Legacy candidate-beam retrieval keeps its conservative interpretation.

Only newly interpreted blank-with-offset rows use `queue_pos_single_7` and
`queue_angular_factor_8`; existing supported rows retain their previous methods.
These versions change geometric applicability, not numerical thresholds. Formal
LINE pair preparation applies the same interpretation and records
`queue_line_pair_builder_2` for those rows. Mode inference, frequency coverage,
resolution, sensitivity associations and complete-beam aggregation are unchanged.

## Spectral scans

The existing Queue contract intentionally uses a shared coherent single-field,
regular-SPW scope for its common and continuum methods. Therefore the remaining
single-field spectral scan is not a UI wiring defect. This change does not invent
regular windows for a scan or remove that common scope gate. Supporting independent
position/angular conclusions for scans requires a separate method and aggregation
contract, including frequency-dependent beam coverage; it cannot be achieved by
simply deleting `REGULAR_QUEUE_SETUP_REQUIRED`.

## Verification

`tests/integration/test_queue_blank_mosaic.py` checks offset transport, source
preservation, formal CONTINUUM and LINE preparation, legacy isolation and invalid
geometry/frame/coordinate guards. The full Queue replay compares all context
records with the previous report and requires only the nine blank-offset contexts
to change. It also records all 120 blank-Mosaic outcomes separately.

The browser groups scope explanations by recorded custom/rectangle/scan evidence,
counts each affected candidate once per group and keeps overlapping raw diagnostic
occurrence counts in technical details. Presentation never recalculates a verdict.

The 2026-10-06 full replay confirmed 119 criteria-not-met and one indeterminate
SPS context among the 120 blank-Mosaic rows for the CASE1 continuum engineering
request. Exactly nine context records changed; the other 3191 were identical to
the previous report. Overall: 119 not met, 3081 indeterminate, zero met. This is
a regression check for that input, not a universal absence-of-duplication claim.
Full suite: 1818 passed, 12 skipped. Local generated replay artifacts are under
`reports/queue-blank-mosaic-check-2026-10-06/`.
