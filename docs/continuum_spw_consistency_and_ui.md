# Continuum SPW evidence consistency and focused comparison UI

## Objective

A Continuum selection on the browser form is an affirmative user declaration that
its proposed setup contains at least two **distinct** spectral windows with
**usable** bandwidth strictly greater than 1.8 GHz each. The selection is
recorded as the existing `CONTINUUM_SETUP_DECLARATION` token in the request;
it is not proof inferred from a missing or partial window list.

The detailed SPW inventory remains optional. The browser permits a Continuum
request with no detailed rows and `setup_complete=false`. It likewise permits
LINE-only assessment without proposed SPW rows, although LINE outcomes can be
indeterminate without the required scientific evidence.

Choosing LINE alone does not assert that the Continuum width threshold is false.
A setup may have both scientific purposes.

## Contradiction handling

A complete window inventory is a separate, affirmative user statement. When
`CONTINUUM` is selected, a continuum declaration is present, and
`setup_complete=true`, the browser form adapter checks the complete
window list before an assessment can run. The shared request validator remains
unchanged, so CLI clients can still validate and evaluate conflicting evidence
as a scientifically indeterminate `CONT-SETUP` criterion:

1. Evaluate each supplied window's width using the existing direct
   `qualify_window` interpretation. Nominal values above the threshold remain
   unresolved without explicitly approved conversion. This validator does not
   invent a usable width or perform a scientific decision aggregation.
2. A complete list with fewer than two **possible** qualifying windows is a
   `CONTINUUM_SETUP_DECLARATION_CONFLICT` input error. This covers an empty
   complete list, a single window, and definite narrow-band evidence.
3. If fewer than two windows are verified to qualify but at least two could
   qualify, emit `INCOMPLETE_CONTINUUM_WINDOW_EVIDENCE`. The current evidence
   cannot corroborate the declared complete list, although it does not prove
   the Continuum condition false. Provide direct usable-width evidence or
   withdraw the full-inventory declaration.
4. As soon as two distinct windows are directly verified to qualify, the
   Continuum declaration is satisfied. Other listed windows may be narrow or
   have unknown widths: the rule never requires *every* window to be wide.
   Further validation and science evaluation are unchanged.

Without an explicit *complete-list* claim, missing per-window bandwidth evidence
does not invalidate an otherwise declared Continuum setup. An incomplete list
cannot establish a negative LINE result: `setup_complete` is never defaulted to
true. The shared request-schema token and underlying `CONT-SETUP` science method
remain unchanged; the new behavior is a browser-only input-validation error for a
contradictory full-inventory claim. API/CLI callers retain the previously
accepted conflict-provenance path; no request or validation schema is changed.
Existing CLI clients must continue to send
an explicit Continuum declaration when they rely on declaration-based evidence.

## Browser presentation

- The Continuum selection is an affirmative declaration in the interactive
  browser: `continuum-choice.js` checks the explicit confirmation field when
  the user actively selects Continuum. The separate checkbox remains an
  accessible fallback without JavaScript. The browser mapper serializes the
  declaration only when that field is explicitly present; it **never** infers
  declaration evidence from the posted `intents` array alone. This preserves
  browser/CLI parity for legacy, nominal-bandwidth, and mixed-purpose requests.
  Invalid explicit declaration values are still rejected.
- The Mosaic browser report opens on matching candidates only; stored other
  candidate categories remain reachable through a disclosure and the full
  report download. Matching contexts are the default visible context content.
  No candidate-level or context-level scientific status is reclassified.
- POS-MOSAIC table cells use saved `coverage.pointing_count` and
  `coverage.inside_count`, not empty scalar proposed/candidate quantity fields.
  Missing coverage remains labeled as unavailable. No geometry is recomputed.
- Single Pointing RA and Dec selectors stay synchronized in the two valid
  coordinate-format pairs: DEG/DEG and HMS/DMS. Valid entered coordinates are
  converted when either selector changes, preserving the sky position. Invalid
  text cancels a format change instead of silently reinterpreting it. Existing
  mixed-format saved forms are not changed on initial page load. Imported
  Mosaic OT positions are unaffected.

## Verification

On an unchanged checkout of the declared base commit, run:

```bash
node --test tests/ui/coordinate_format_sync.test.cjs
python -m pytest -q \
  tests/ui/test_continuum_window_consistency.py \
  tests/ui/test_proposed.py \
  tests/ui/test_mosaic_focus.py \
  tests/ui/test_mosaic_hierarchical_report.py \
  tests/ui/test_mosaic_execution.py
python -m pytest -q
python -m compileall -q src/alma_duplicate tests/ui

git diff --check
```

The first local patch triggered four focused failures and exposed a separate
CLI/form scientific-contract risk. The correction moves the contradiction
check out of shared request validation and into the browser form adapter. The
CLI continues to accept and report conflicts as scientific uncertainty.

The local user report from the first patch recorded four focused test failures.
They were traced to two generic fixtures that accidentally asserted exhaustive
SPW inventories or duplicated an existing MultiDict scalar field, and two
pagination tests that still assumed the old Mosaic default. These were corrected
without weakening the duplicate-scalar request guard or reverting positive-first
Mosaic behavior. Full repository regression and live Archive acceptance must be
run separately; isolated checks are not substitutes.
Before merging, verify the CASE2 browser request and compare downloaded
`report.json` and request content. Ensure no `archive_mosaic_backend_2` output
schema, discovery, or scientific aggregation changes were introduced. Check that
Mosaic `view=all` still displays all retained identities and Single Pointing
still uses its independent result-view semantics.

## Independent purposes and wide FDM windows

`LINE` and `CONTINUUM` are independent request intents, not mutually exclusive
correlator modes. An FDM SPW may be wide enough to count towards CONT-SETUP;
selecting LINE does not assert the continuum condition is false. Conversely,
having two qualifying bandwidths is necessary for a continuum observation
under the cited policy, but is not sufficient to infer the researcher's
scientific purpose or select the CONTINUUM comparison branch automatically.

The browser validates optional detailed bandwidths using the existing
`qualify_window` method, preserving the project's explicit usable-bandwidth
interpretation and strict >1.8 GHz threshold. Exactly two verified wide SPWs
suffice, irrespective of narrower or unknown additional windows. The
three-valued science evaluator and cross-purpose selection rules are unchanged.

Direct/raw form posts that omit `continuum_setup_declaration` retain the
existing nominal-width comparison path; they are not silently upgraded to a
user confirmation. In normal interactive browser use, the declared field is
checked on a deliberate Continuum selection, and no detailed SPW list is
required unless the user asserts that it is complete.
