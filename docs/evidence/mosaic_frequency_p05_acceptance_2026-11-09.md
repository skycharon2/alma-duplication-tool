# P0.5 — Mosaic full recorded frequency setup acceptance

Baseline: `9e9846d70237602a1cb0e8f7d238bf4c5b0ad0cf` (merged P0 PR #245).
This is a proposed verification record, **not** a claim that the checks below have
already been run in the developer's complete repository or against live ALMA.

## Contract

- A matching Archive Mosaic context may retain its exact raw-row-bound
  `spectral_setup_display` without changing any criteria, branch status or
  Member/ASDM/context identity. Archive components are not relabeled as SPW numbers.
- A matching Queue regular-SPW candidate may retain nominal SKY interval bounds
  from the parsed, snapshot-bound source rows. Custom rows must agree in spectral
  evidence. No SPS expansion, usable-width inference or array-specific OT
  ownership is claimed.
- The full setup and existing matching comparisons use one GHz coordinate scale;
  gaps, invalid components, source identity and matching-pair numbers are kept.
- Legacy reports lacking full setup evidence remain readable and show the
  original matching comparisons with a scope disclaimer.
- The browser never reparses a source, queries TAP/Queue or assigns scientific
  outcomes. New fields are display-only, derived from typed saved evidence.
- Single Pointing templates, JS, report production and rule implementations
  remain unchanged.

## Automated checks (record actual local outputs before merge)

- [ ] `node --check src/alma_duplicate/ui/static/mosaic-visualization.js`
- [ ] `node --test tests/ui/*.test.cjs`
- [ ] `python -m pytest -q tests/ui/test_mosaic_frequency_parity.py tests/ui/test_mosaic_explore_charts.py tests/ui/test_mosaic_execution.py tests/ui/test_mosaic_explorer_acceptance.py`
- [ ] `python -m ruff check --select F src tests examples`
- [ ] `python -m pytest -q`
- [ ] `git diff --check`
- [ ] Confirm merged main CI (Python 3.11/3.12 and Node) succeeds

## Browser checks (record screenshots and matching source lines)

- [ ] Archive Case 2 / NGC253: SPW 25 matching interval unchanged. Other
  frequency_support components appear **only if independently recorded and
  associated**; missing setup is explicit, not invented.
- [ ] Archive `s_region`, proposed pointings and POS-MOSAIC unchanged.
- [ ] Queue Custom and Rectangle: all regular-SPW nominal intervals for each
  matching configuration visible; no cross-candidate or cross-snapshot mixing.
- [ ] Queue 7-m/12-m branches retain separate matching statuses, while their
  common candidate spectral setup is labelled as such.
- [ ] Source/Member/array filters, selection, Setup hide/show, SPW-detail link,
  zoom/pan/reset and report-page navigation behave correctly.
- [ ] Old report lacking the new fields shows matching intervals only, plus
  `Full setup evidence not retained...`.
- [ ] Invalid support rows and >128 components do not produce partial or
  fabricated interval bars; the saved matching evidence remains accessible.
- [ ] Downloaded original report and request are byte-identical before/after
  opening Explore (read-only UI), and no new retrieval is triggered.

## Limitations and follow-up

- Historical reports are not backfilled. Re-run a saved source workflow to
  generate new optional display fields; live Archive execution remains opt-in.
- Archive component indices from parsed frequency_support are *not* the SPW
  label of a LINE comparison; they appear as separate grouped evidence.
- Queue boundaries are nominal SKY support from the Queue CSV parser, not a
  proof of true usable bandwidth. Spectral Scan is not expanded.
- Full scientific acceptance requires independently reviewed real ALMA cases.
- Sky imagery is outside P0.5 and remains a later PR.
