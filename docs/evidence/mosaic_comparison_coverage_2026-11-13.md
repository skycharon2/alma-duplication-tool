# Mosaic comparison coverage parity — 2026-11-13

Working tree based on `0dc4061`, including the user's staged shared-chart work.
Reviewed the README, architecture, roadmap, Mosaic report projection contracts,
GitHub main's Mosaic visualization implementation, and the Single Pointing
spectral/selection implementation. The official AQ entry page is a dynamic
application; its initial HTML did not supply an additional spectral contract.

The Mosaic view now adapts `source_reference` to the shared `spectral_view`
contract. Where a saved report has no `spectral_display`, its exact raw-row
reference and assigned component index select one validated component from its
context-keyed setup sidecar. Missing, foreign, invalid and duplicate bindings
remain unavailable. The UI never selects by frequency proximity or assigns all
Member/setup intervals to a comparison.

Coverage survives server chart projection and browser conversion, contributes
to axis bounds/focus, and is drawn beneath representative dots. Selected details
show GHz bounds, interval width and saved spectral resolution. Summary/list/detail
identity accents use the same candidate palette as the charts. Coincident
footprints use the selected candidate's color when selected. The full-setup
parameter disclosure remains accessible, while comparison parameters sit in the
Selected comparison panel, alongside recorded conditions.

Validation:

- `python -m pytest -q tests/ui`: 646 passed.
- `node --test tests/ui/mosaic*.test.cjs`: 61 passed.
- Saved V462_Lup Archive report replay: 40 matching contexts, each with its own
  bound interval. Expanded first setup shows four comparison bars; SPW 4 detail
  shows 335.55–337.53 GHz, width 1.98 GHz, resolution 31250 kHz.
- Playwright: linked selection, isolate/restore and focus passed. At 390 px,
  document width remains 390 px; the frequency plot scrolls within its panel.
- Screenshots: `output/playwright/mosaic-coverage-fixed.png`,
  `mosaic-detail-fixed.png`, `mosaic-mobile-fixed.png` (local artifacts).

Replay imports copies into a separate temporary store. Original saved reports,
criteria, acquisition and scientific evaluation remain unchanged. Browser replay
checks Archive-only display; combined Archive/Queue and LINE behavior are also
covered by the automated UI suite. Sky imagery colors retain their existing
source-specific Archive/Queue meaning.

## Follow-up: overlap preview and report hierarchy

The overlapping-footprint chooser now floats within viewport bounds and shows
candidate colors, project, purpose, SPW, Member/configuration and saved ASDM.
Pointer hover and keyboard focus preview both charts without changing selection,
isolation or persistent setup expansion. Leaving the entry restores the selected
plots; clicking commits selection. Escape and outside clicks dismiss the chooser.
Preview scrolls only the frequency viewport, preventing pointer drift caused by
scrolling the document. The repetitive native polygon title was removed.

The header summarizes submitted pointings, proposed array and purposes, with
source/page scope beside filters. The selected summary includes ASDM when saved.
The list shows its filtered count; detail identities precede frequency values,
with compact spacing and unambiguous frequency/pair labels.

Verification: 660 Python UI tests and 62 Mosaic Node tests passed. The new hover
regression also passed after the viewport-scroll correction. A 42-comparison
Archive+Queue saved `case3` report was replayed in Playwright: hover leaves
selection unchanged, click changes #1 to #2, Escape dismisses, and the chooser
fits within a 390 px viewport (374 px wide). Screenshots are local artifacts at
`output/playwright/mosaic-ux-{hover,header,details,mobile}.png`.

## Final detail audit

Added keyboard pan/zoom/Home controls to both shared charts, restored focus after
Setup redraw, added per-comparison text-detail links and an explicit empty-page
interpretation. SVG downloads retain report URL, visible comparison identities,
selection and viewport metadata in an SVG description. No scientific values or
result grouping were changed.

Verification: 660 UI Python tests and 63 Mosaic Node tests passed. Playwright
confirmed keyboard zoom, Home reset, and repeated Enter toggles retaining Setup
focus on the 42-row Archive+Queue replay.


## Queue window and aggregate display

Both explorers now disclose saved Queue window references alongside the actual
aggregate continuum comparison (or evaluated LINE comparisons). Window rows do
not increase match counts. Nominal intervals use a light bar, saved usable or
evaluated intervals a darker bar, and a hollow marker denotes the interval
midpoint rather than the candidate representative frequency. Requested SKY
frequencies are repeated on window rows for comparison. Single Pointing nominal
bounds use only saved SKY centre and nominal bandwidth; missing fields leave the
nominal layer absent. Mosaic preserves its source-bound saved usable bounds.

Validation: 660 existing Python UI tests passed, then 8 focused tests (including
2 new interval preservation/fallback regressions) passed; all 118 JavaScript
tests passed. Live legacy preview confirmed 4 midpoint markers and one aggregate
comparison. Full refreshed browser validation of the usable layer was unavailable
because that preview's original temporary report directory had been removed.
