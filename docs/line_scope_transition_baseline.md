# LINE scope transition — step 01: legacy baseline and scientific boundary

**Status:** characterization and migration design only; **no change to an assessment verdict**.

**Reviewed base:** `main` at `b7814ea3a4307f59a48ae237d887da09062015e0`
(after merged PR #187 and PR #188, 2026-10-27).

## Problem and decision

The primary LINE input is the set of **scientific LINE requirements submitted for
this assessment**: rest/sky frequency, correlator mode, spectral resolution and
RMS per requested window, plus any required redshift/frequency-frame evidence.
Researchers can submit multiple requested LINE windows; the valid comparison
scope is not necessarily limited to the first UI row.

The `SPW bandwidth details / Add window evidence` section describes an
**optional physical SPW inventory**. `I have listed every window in this setup`
currently serializes as `request.setup_complete`; this checkbox must not become
a precondition for a definitive comparison of the explicitly submitted LINE
requirements under the future contract. Do not infer inventory completeness
from a filled primary LINE row.

The desired successor contract, subject to explicit versioning and science
review, will aggregate coherent comparisons **within the validated submitted
LINE requirement set**. If any complete pair passes, it may yield a positive;
if all complete pairs definitively fail, a negative; if no pair passes and some
comparison remains genuinely unresolved, `INDETERMINATE`. Archive ambiguity,
mode/scope/TP restrictions, redshift and reference conversion uncertainty,
missing sensitivity, provenance, unapproved methods and missing candidate
metadata remain capable of producing `INDETERMINATE`. A FALSE criterion in
one pair must not be combined with TRUE criteria belonging to another pair.

## Existing behavior (not yet the desired successor)

`src/alma_duplicate/ui/proposed.py` serializes `setup_complete` separately
from its requested LINE rows, but both the LINE row and optional width details
share the request's `spectral_windows` objects.

`src/alma_duplicate/line_pairing.py` sets
`LinePairBuildResult.proposed_enumeration_complete` exclusively from
`request.setup_complete is True`.

`src/alma_duplicate/rules/line.py::evaluate_line` evaluates six criteria for
each bound requested-window/candidate-component pair (`AND`), then applies an
`OR` within one Archive comparison context. Under existing
`archive_line_context_or_1`, an unconfirmed complete physical inventory adds
`Truth.UNKNOWN` to the OR via `PROPOSED_ENUMERATION_INCOMPLETE`. Therefore an
individual definitive `CRITERIA_NOT_MET` pair can coexist with a context-wide
`INDETERMINATE`. Positives remain positive if another pair is TRUE.

**This step deliberately preserves that historical behavior** for both
Single Pointing and Mosaic. Do not change the validator, decision method,
request/report schema, CLI, UI gating, archive search, or source fixtures in
this patch. The new integration tests record real current evaluations with
fixed Archive replay; they are a baseline for the migration, not acceptance
of the new negative rule.

## Migration decisions required before changing science

1. **Scope discriminator / explicit opt-in:** define a versioned request scope
   and default handling of old inputs. Do **not** treat absent scope tags in
   old requests as new affirmative declarations. Separate physical inventory
   completeness from submitted LINE requirements and record which contract
   was actually evaluated.
2. **Browser readiness:** define mandatory fields for each submitted LINE
   requirement; reject missing or internally inconsistent user-entered values
   *before* a new browser assessment. Preserve CLI/raw input diagnostics and
   their prior semantics unless an explicitly reviewed API version changes.
   In particular, existing `tests/ui/test_proposed.py::test_partial_input_remains_search_ready`
   captures the old behavior and must be resolved deliberately, not removed
   without review.
3. **Aggregator scope:** introduce the approved new method/version for the
   submitted-requirement OR. Continue to evaluate actual pair criteria,
   status and scope gates; do not turn every current UNKNOWN into FALSE.
   Support one or multiple requested windows. Retain the original method for
   legacy requests and saved artifacts.
4. **Reporting:** display *pair result* separately from *context/Member result*;
   ensure browser, exported request, `report.json`, inspection and CLI all
   report the scope/version honestly. No reinterpretation of saved raw reports.
5. **Integration acceptance:** exercise Single Pointing and Mosaic with the
   same LINE requirements; LINE+CONTINUUM independent branches; complete
   requirements without optional bandwidth evidence; true Archive unknowns;
   provenance/identity binding; older request and report replay; CASE2 with
   SPW 25 matching and 27/29/31 definitely failing their **submitted** LINE
   comparison (subject to retained raw evidence).

## Step 01 automated checks

`tests/integration/test_line_scope_transition_baseline.py` checks:

- One fixed Archive LINE replay, both Single Pointing and Mosaic.
- A definitively failing `LINE-COVERAGE` pair with `setup_complete=false`
  remains pair FALSE / **legacy** context UNKNOWN.
- Identical failed pair with `setup_complete=true` becomes legacy context
  FALSE.
- A positive pair remains TRUE with `setup_complete=false`.
- Pair method `archive_line_pair_and_1` and context method
  `archive_line_context_or_1` remain unchanged in these legacy cases.
- A filled LINE requirement can be mapped with no optional bandwidth at
  either checkbox setting, without forging an inventory completeness claim.

Expected check for **this** step: all new tests pass *without* editing any
production source, and full suite remains green. The intended future
successor behavior is specified in this document rather than deceptively
marked as passing or disabled with `xfail`.

## Acceptance / stop condition

- Patch contains only this document and its integration test file.
- All new tests and the full suite pass; `git diff --check` passes.
- `git diff origin/main -- src/alma_duplicate tests/ui` is empty (no
  production/UI changes in this step).
- No scientific verdict, Archive query, publication bytes or legacy method
  identifier changes.
- Merge this small PR before **step 02: versioned input scope contract**.
  Do not combine step 01 with a UI hierarchy refactor or Mosaic acquisition
  expansion.
