# Multi-target Mosaic main-entry acceptance

## Result

The LMC0NT197 capture now passes through `assess_observation`, rebuilt package
readiness, candidate-local AQ binding and the shared duplication rules. Four Archive
contexts are evaluated. The three requested target fields are selected from a
multi-target original MS; six science fields belonging to other targets remain
excluded. No production-rule changes were necessary for this acceptance step.

## Regression cases

| Constructed proposal | Position result | Joint result |
| --- | --- | --- |
| Three LMC0NT197 coordinates with compatible continuum inputs | 3/3 satisfied | At least one TRUE branch |
| Three LMC1N127 coordinates against LMC0NT197 | 0/3, not satisfied | No TRUE branch |
| Two selected coordinates and two distant coordinates | 2/4, not satisfied | No TRUE branch |
| Three selected coordinates, incompatible angular resolution | 3/3 satisfied | No TRUE branch |
| Three selected coordinates, incompatible continuum frequency | 3/3 satisfied | No TRUE branch |

Pointing coordinates and execution identity come from listobs. Frequency, angular
resolution and sensitivity for the candidate come from the normal Archive metadata
path. AQ evidence selects the exact Member/source and cross-checks antenna diameter.

## Reproduction and scope

```sh
python -m pytest -q tests/integration/test_lmc_mosaic_acceptance.py
```

The test needs no network or local reports/cache. The small captured package audit,
TAP result and AQ receipt are stored in `tests/fixtures/archive/lmc_mosaic_2026_10_26/`.
The original public auxiliary package was inspected separately and the reconstruction
replayed offline. At the main-entry test boundary, discovery and preparation return
captured evidence; package integrity and readiness are checked again by production
code. This is an offline integration acceptance, not a live sky-search recall test.

The sample does not establish complete Member coverage. Exactly 50% is never a
positive Mosaic position result; insufficient completeness can retain UNKNOWN rather
than prove a negative. Search-wide absence remains unproven. N55 acquisition remains
unresolved because the inspected startup log has no pointing coordinates.

The next acquisition work should classify additional real failures, prioritize
recoverable supported product layouts, and add each recovered format to this same
main-entry regression path before broadening claims of Archive coverage.
