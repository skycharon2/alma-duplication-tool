# Positive-first Mosaic report and synchronized coordinate representation

## Scope

The Mosaic browser report now opens on stored `CRITERIA_MET` candidate identities
and renders their matching contexts. Unresolved and nonmatching candidates remain
available through a subordinate diagnostic disclosure or the complete original
report download. No candidate, branch, pair, or criterion is reclassified.

`view=all`, `view=review`, and `view=not_met` remain explicit inspection paths.
The inherited `view=matches` default is now an alias for `view=matching` on Mosaic
runs only. Single Pointing keeps its existing behavior. Existing Mosaic links
without a view selector therefore open on positive matches rather than all results.

The POS-MOSAIC criterion uses recorded `coverage.pointing_count` and
`coverage.inside_count` instead of displaying empty scalar operands. These values
are display-only. Missing coverage remains explicitly unavailable; no calculation
from point rows or `s_region` is performed by the UI.

## Spectral-window completeness is not a convenience default

Spectral-window rows are optional. Confirming that *every* proposed window is
listed is a separate scientific statement and remains unchecked unless the user
explicitly confirms it. Empty input does not prove an exhaustive negative LINE
result. Auto-confirming completeness could turn an otherwise indeterminate result
into `CRITERIA_NOT_MET`, incorrectly excluding a possible duplicate.

The form describes this distinction explicitly. If only one proposed window exists,
the user can confirm completeness to enable definitive negative LINE outcomes.

## Single Pointing coordinate formats

The RA and Dec selectors are linked at the presentation level: choosing decimal
Degrees sets both selectors to DEG, while choosing RA HMS selects Dec DMS and
choosing Dec DMS selects RA HMS. The two sexagesimal formats retain their distinct
astronomical meanings. Existing valid coordinate text is converted in the browser on user action while
preserving the sky coordinates. Invalid or out-of-range input prevents the format
switch instead of being silently reinterpreted. The form invalidates any
previous validation after conversion. Legacy mixed-format values are not silently
modified when loading a saved form.
Mosaic imported OT positions have no visible coordinate selectors and are not
changed by this enhancement.

## Invariants and verification

- Archive queries, scientific aggregation, `setup_complete`, the three-valued LINE
  evaluation, `s_region` handling, and published JSON data remain unchanged.
- All 214 discovered candidates are retained in report storage even when the
  matching-only page loads just one matching candidate.
- A match remains scoped to one stored branch/context, not an entire Member.
- A recorded criterion with no explicit formal-aggregation eligibility flag may
  still carry an explicit SATISFIED/NOT_SATISFIED outcome; only an explicitly
  false flag displays the criterion as indeterminate. This is presentation only.
- Run targeted Python tests and the Node test, then full pytest and interactive
  browser checks on both Single Pointing and Mosaic.

Commands:

```sh
python -m pytest -q tests/ui/test_mosaic_focus.py tests/ui/test_mosaic_hierarchical_report.py tests/ui/test_mosaic_execution.py tests/ui/test_proposed.py
node tests/ui/coordinate_format_sync.test.cjs
python -m pytest -q
```

These instructions describe expected verification. No live Archive scientific
result is claimed based solely on an isolated template or script test.
