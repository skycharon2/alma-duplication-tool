# Step 02 — Versioned LINE evaluation scope (reserved, fail-closed)

## Status and boundary

This is an **input-contract change only**, not approval of the successor LINE
scientific method. The authoritative legacy pair and context methods remain
`archive_line_pair_and_1` and `archive_line_context_or_1`. The `setup_complete`
field retains its legacy meaning. The Step 01/01b baseline tests remain valid.

The wire request may optionally contain:

```json
"line_evaluation_scope": "LEGACY_SETUP_ENUMERATION_V1"
```

The exact supported values are:

| Wire value | Step 02 result |
| --- | --- |
| Field omitted | Legacy scope; same evaluator, diagnostics, and report serialization shape as before |
| `LEGACY_SETUP_ENUMERATION_V1` | Explicitly requests existing legacy behavior; accepted |
| `SUBMITTED_LINE_REQUIREMENTS_V2` | Reserved **but not executable**; hard validation error `LINE_SCOPE_NOT_IMPLEMENTED` |
| Null, unknown token, wrong type | Hard schema validation error; never defaulted to legacy |

The scope is separate from `setup_complete`, which continues to describe the
optional inventory's completeness. Step 02 **does not** allow a complete set of
submitted scientific requirements to determine negative context verdicts. That
scientific behavior is deliberately deferred to Step 04 and a scientific review.

The browser currently renders **no scope selector** and exports the legacy
request without the new field. The browser adapter only passes through a scope
explicitly supplied on its wire input and exposes the corresponding validation
error. It must not infer the successor scope from the presence of a required
LINE window, optional bandwidth rows, or a completeness checkbox.

## Stable serialized legacy reports

The domain `ProposedObservationRequest` exposes a computed, read-only
`line_evaluation_scope` property from its existing immutable `raw_input`. It is
**not** a new dataclass field. Therefore existing requests that omit this wire
field keep their previous `asdict` / JSON shape: no newly defaulted field is
inserted in reports. The request model and validation version numbers are not
bumped for old requests; existing saved reports are neither rewritten nor
reclassified. A request that explicitly opts into the old scope can preserve
that supplied marker in `raw_input`, which is intentional provenance.

## Entry points and negative tests

`validate_proposed_observation` is the shared API/CLI/browser gate: a reserved
scope creates an `ERROR` and returns no parsed request, so a normal assessment
returns `REQUEST_NOT_SEARCH_READY` before Archive/Queue access. The shared
`build_line_pairs` and `evaluate_line` also verify the domain property's scope
and raise `ValueError` for the successor or other unsupported values when
called directly with a constructed or replaced request.

Tests cover implicit and explicit legacy parity (including the old negative
result), unsupported/invalid inputs, mixed LINE+CONTINUUM, browser form wire
mapping, the assessment boundary, and direct Single Pointing/Mosaic callers.
The existing Step 01b `s_region` replay is preserved; **this step does not
claim a new end-to-end live `s_region` science acceptance test**.

## Next steps

- **Step 03:** separately implement browser pre-query completeness checks for
  submitted LINE scientific requirements; specify required values and field
  errors without altering shared legacy API/CLI request assessment.
- **Step 04:** after explicit science approval, implement an independent,
  versioned submitted-requirements LINE method and formally enable V2 in the
  shared validator **in the same change**. Preserve V1 behavior and old report
  versions; apply coherent AND within each proposed-window/Archive-SPW pair,
  then OR whole pairs. Genuine missing Archive evidence and unresolved REST/SKY
  conversions must remain UNKNOWN.
- **Step 05:** align scope presentation in Single Pointing, Mosaic, CLI, JSON.
- **Step 06:** fixed CASE2, online Archive, mirror/coordinate UI acceptance.

## Non-goals

No change to Archive candidate retrieval or `s_region`, optional SPW bandwidth,
CONTINUUM qualification, scientific criterion thresholds, old LINE aggregation,
existing report schema, or report hierarchy. Do not silently activate V2 or
rewrite old stored assessment results.
