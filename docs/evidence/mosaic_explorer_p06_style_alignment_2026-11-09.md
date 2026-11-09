# P0.6 — Mosaic Explorer / Single Pointing visual alignment

Date: 2026-11-09
Baseline: Mosaic Frequency P0.5, including the setup disclosure (v3) and DOM test-harness correction.

## Scope

Presentation-only alignment. The existing Single Pointing `visualization.css` is the
style authority. The Mosaic template, Mosaic CSS, and Mosaic-only controller are
updated, but no scientific evaluator, frequency evidence, report schema, source
query, coordinate transform, or saved-report format is changed.

Expected visible changes:

- `Position` / `Frequency` share the Single Pointing card-header typography and
  show zoom controls in those headers, not in the plot body.
- Frequency setup notes move to an optional disclosure *below* the plot.
- Position metadata and layer toggles move below the plot, preserving both layers.
- Plot SVG text uses the shared 10px baseline; summary, captions, and details
  reuse Single Pointing CSS styles.
- Comparison filters and bottom cards reuse the shared control and list classes.
- The `Charts` / `Sky preview` selector has the same heading/meta hierarchy and
  page count treatment; actual sky imagery remains out of scope until P1.

## Automated checks (fill actual observations)

- [ ] `git apply --check`: passed
- [ ] `git diff --check`: passed
- [ ] `node --check src/alma_duplicate/ui/static/mosaic-visualization.js`: passed
- [ ] `node --test tests/ui/*.test.cjs`: record pass/fail counts
- [ ] `python -m ruff check --select F src tests examples`: passed
- [ ] `python -m pytest -q tests/ui/test_mosaic_style_alignment.py tests/ui/test_mosaic_explorer_acceptance.py tests/ui/test_mosaic_frequency_parity.py`: record pass/fail counts
- [ ] `python -m pytest -q`: record pass/skip/fail counts

## Browser review (manually mark each item)

- [ ] Case 2 / NGC253 (Archive LINE): card headers, fonts, spacing, and chart zoom controls visually match Single Pointing.
- [ ] The collapsed and expanded Setup states show the original saved components and SPW 25 comparison, with correct frequency positions.
- [ ] Changing the selected comparison updates only its own header zoom controls.
- [ ] Position proposal/candidate layer checkboxes still work from beneath the chart.
- [ ] `Charts` and `Sky preview` change views and update the page counter.
- [ ] Filters, comparison list, and text-report links still work.
- [ ] Queue Custom 12-m / Continuum and Queue 7-m (when captured): distinct source/array evidence remains separate.
- [ ] Narrow viewport: controls wrap without hiding chart labels or modifying chart data.
- [ ] Screenshots: Case 2 and Single Pointing matched viewport, and one Queue case.

## Retention / scientific invariants

Archive component indices are not assumed to be SPW IDs. Full setup bars are
supplementary display evidence only. No missing intervals are invented. Matching
statuses remain those in the saved report. Unchecked browser observations should
remain pending, not marked as passed.
