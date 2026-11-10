# P1 — Mosaic Aladin Sky Preview acceptance

Branch: `feat/mosaic-aladin-sky-preview`
Baseline: `main` commit `6824549` (merged PR #246)
Status: **Pending full repository / Safari validation**

## Automated results (fill with actual runs)

- [ ] `node --check src/alma_duplicate/ui/static/mosaic-report-sky.js`
- [ ] `node --check src/alma_duplicate/ui/static/mosaic-sky-geometry.js`
- [ ] `node --test tests/ui/*.test.cjs`
- [ ] `python -m ruff check --select F src tests examples`
- [ ] `python -m pytest -q tests/ui/test_mosaic_sky_preview.py tests/ui/test_mosaic_explorer_acceptance.py`
- [ ] `python -m pytest -q` (record counts and any skips)
- [ ] GitHub CI (Python 3.11 + 3.12, lint, Node) successful

## Manual browser evidence

- [ ] Case 2 NGC253: open Charts first and confirm no Aladin / survey download occurs until clicking Sky preview
- [ ] Click Sky preview: local Aladin 3.8.2 starts; DSS optical survey appears where available
- [ ] Three OT pointings drawn as independent labelled crosses/diamonds; optional magenta proposed half-power circles reflect the *saved* proposed frequency and array display model
- [ ] Archive `s_region` polygon visually follows the saved boundary; no fabricated single Archive beam or pointing centre
- [ ] Queue Custom/Rectangle: only saved, candidate/snapshot/array-bound beam union is displayed; no inferred mosaic grid on missing evidence
- [ ] Project / Member / Array filters and comparison selection update sky overlays without re-evaluation
- [ ] Show/hide proposed, candidate, other comparisons and imagery toggles behave independently
- [ ] Focus selected and fit visible footprints work near RA 0/360 and with nonzero declination
- [ ] Simulate offline imagery: geometry-only SVG is visible, clearly marked **no optical imagery**; retry does not change saved evidence
- [ ] Missing or oversized geometry yields an explanation, not an incomplete or invented footprint
- [ ] Compare report/request download bytes before/after opening sky and changing filters: identical
- [ ] Confirm Single Pointing Sky Preview still operates unchanged

Record screenshots, browser/version, report ID (non-sensitive), source snapshot and test output after verification. Do not mark manual items Passed solely because Python/Node tests passed.

## Scope / scientific disclaimer

The optical image is context, not an ALMA detection. The sky preview does not query new ALMA observations, infer missing beam positions, recompute completeness, or change matching/duplication decisions. Archive region overlays must pass the recorded SHA-256 and parser validation; Queue overlays must pass saved candidate, source row, snapshot, completeness and array binding checks. If reference imagery fails, display the saved geometry without an image.

## Local P1.1 correction verification (2026-11-10)

Corrected Aladin 3.8.2 dash configuration at graphic-overlay level, separated
Archive/Queue catalogs and overlays, and kept the selected white halo separate.
Fit now includes each pointing offset plus its spherical beam radius, respects
per-beam radii, avoids accumulating radii across candidates, and accounts for the
canvas aspect ratio. Removed the 0.08-degree minimum that hid compact mosaics.
Async module loading rechecks selection and active slide; restoring a valid
filter selection retries initialization. Oversized optional overlays now have an
explicit omission notice.

- Node: 78 tests passed (all `tests/ui/*.test.cjs`).
- Ruff `--select F src tests examples`: passed.
- JavaScript syntax and `git diff --check`: passed.
- Chrome, saved NGC253 fixture: DSS loaded; proposed circles visibly dashed;
  submitted crosses and Archive outline readable at automatic fit.
- New regression coverage: off-centre beam extent, order independence,
  per-beam radius, async empty-selection recovery, overlay-level dashes and
  source-specific catalog colors.
- Safari hardware trackpad validation and GitHub CI remain pending.
- No scientific criteria, saved assessment data, or Single Pointing code changed.
- Full Python regression after corrections: 3401 passed, 12 skipped (77.18s).
