# Step 03 — Browser-only required LINE fields before assessment

## Scope and non-goals

Only an explicit browser **Run assessment** action activates the completeness
check for every requested LINE window. The shared request validator, API, CLI,
Archive query, LINE pairing and science aggregation are untouched. Form
`Validate input` and request `Download` retain the legacy evidence-audit
semantics: structurally valid, scientifically incomplete inputs may be exported.
The Step 02 `SUBMITTED_LINE_REQUIREMENTS_V2` scope stays unsupported and
fail-closed; this patch does **not** enable it.

The input form currently uses the same `rows` sequence for requested LINE
windows and optional physical SPW bandwidth details. When LINE is selected,
every listed row is presented as a requested LINE window, including rows
added using the optional evidence control. Thus this step checks each row; a
future separate UI contract should split the row roles explicitly. This step
does not silently infer a different set of intended LINE windows.

## Browser Run-only requirements

For FIXED + LINE assessments, per requested window require:

- A parsed, convertible frequency: SKY frequency, or REST frequency with
  a user-supplied redshift. No representative-continuum fallback.
- An explicit proposed correlator mode (`FDM` or `TDM`, not `UNKNOWN`). A known
  TDM mode is a **complete input**, not a pass: `LINE-FDM` science still decides.
- A usable planned spectral resolution prepared through
  `prepare_line_window` (not channel spacing or noise bandwidth).
- Exactly one window-bound LINE sensitivity with numeric RMS and supported
  basis, without borrowing a setup/other-window sensitivity.

No optional bandwidth or complete physical SPW list is required, and neither
`setup_complete` nor Continuum qualification is changed by the gate. REST
frequency conversion errors and missing fields yield an `ERROR` bound to the
appropriate browser field. Shared-validator structural errors still block
assessment independently.

## Safety and provenance

- Run-only errors are appended **after** shared validation, and set browser
  search readiness to BLOCKED. The original request JSON and the validator
  result's scientific evidence are not mutated.
- No provider is constructed for these rejected Run submissions. Both
  `BrowserAssessment.assess` and `.assess_mosaic` are guarded in tests with
  fail-on-invocation stubs.
- No method ID, `three_or`, `PROPOSED_ENUMERATION_INCOMPLETE`, candidate
  discovery, `s_region` geometry, CLI parsing or saved report format changes.
- A negative LINE context under `setup_complete=false` still has the legacy
  `INDETERMINATE` aggregation; changing this belongs to Step 04.
- Actual Archive evidence gaps still remain `Needs review`; this check only
  addresses what the user must submit before browser Run.

## Acceptance

Run `tests/ui/test_line_run_required.py`, `tests/ui/test_proposed.py`,
`tests/ui/test_runs.py`, `tests/ui/test_mosaic_execution.py`,
`tests/integration/test_line_scope_transition_baseline.py`, and the full
`python -m pytest -q` suite. Require zero changes under `rules/`, Archive
clients/discovery, shared validation or CLI. Also check no `line_evaluation_scope`
field is added to ordinary browser requests.
