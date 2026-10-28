# Step 03b-A — separated LINE requirements and physical SPW evidence

## Status and activation boundary

`SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1` is a **new, explicitly versioned
input contract**. This step validates it and prepares *two independent typed
sets of operands*. It **does not authorize a new input to run a scientific
assessment**: the shared validator returns `SEPARATED_INPUT_NOT_EXECUTABLE`
with blocked readiness and no parsed `ProposedObservationRequest` or search
options. The source provider is never constructed. This applies to both
Single Pointing and Mosaic and even to Continuum-only new-format requests;
formal new-format Continuum wiring needs a separately reviewed release.

Legacy wire requests that omit all the new contract keys are unchanged, including
partial-input CLI/API diagnostics, saved reports, `setup_complete` behavior,
LINE pairing and aggregation method identifiers. Step 02's
`SUBMITTED_LINE_REQUIREMENTS_V2` remains disabled. Neither this step nor a
physical completeness declaration may issue new formal negative LINE verdicts.

## New request namespace

Within `request`:

```json
{
  "line_input_contract": "SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1",
  "line_requirements": [
    {
      "requirement_id": "line-a",
      "window_center": {"value": "225.1", "unit": "GHz", "kind": "SKY"},
      "correlator_mode": "FDM",
      "spectral_resolution": {"value": "20", "unit": "km/s"},
      "rms": {"value": "0.3", "unit": "mJy/beam"}
    }
  ],
  "physical_spw_evidence": [
    {
      "spw_id": "physical-a",
      "linked_line_requirement_id": "line-a",
      "bandwidth": {"value": "1875", "unit": "MHz"},
      "bandwidth_kind": "USABLE"
    },
    {
      "spw_id": "physical-b",
      "bandwidth": {"value": "2000", "unit": "MHz"},
      "bandwidth_kind": "NOMINAL"
    }
  ],
  "physical_spw_inventory_complete": false
}
```

Shared target, geometry, setup, positional and Continuum metadata fields stay
in their existing request locations. The new fields must not coexist with
legacy `spectral_windows`, `sensitivities`, `setup_complete`,
`line_requirement_window_ids`, or `line_evaluation_scope`; their presence
is an error **even when the legacy field is empty or false**. New-contract keys
without `line_input_contract` also fail closed rather than defaulting to V1.
`validated`, `complete_line`, and similar client-supplied authority markers are
not recognized. The validator calculates completeness from parsed line inputs.

## Data identity, association and meaning

- LINE requirement IDs are unique *within the LINE collection*; physical SPW
  IDs are unique *within the physical collection*. ID overlap between the two
  namespaces does **not** create a link.
- Each physical SPW has zero or one explicit `linked_line_requirement_id`.
  Missing targets are errors. For this initial contract, **at most one physical
  SPW may link to a given LINE requirement**; a second such link is rejected
  as ambiguous rather than deduplicated.
- Two different physical IDs are always two records, even if they have equal
  frequencies, equal bandwidths or the same setup; they are never merged.
- A LINE requirement describes the centre of a *requested correlator window*,
  not the rest frequency of an individual molecular transition. SKY is used
  as given; REST needs a usable `source_redshift` for preparation. The mode may
  be known TDM; FDM suitability remains a **science** decision.
- Physical `bandwidth_kind` must be explicitly `USABLE`, `NOMINAL` or `UNKNOWN`
  whenever a bandwidth is given. Neither nominal-to-usable conversion nor
  missing-width inference happens in the input adapter.
- `physical_spw_inventory_complete` is a strictly typed Boolean about **only
  the physical inventory**, not an input completeness or LINE-science claim.
  It must *never* be translated to legacy `setup_complete`.

## Independent science-adapter ports (not execution authorization)

`parse_separated_setup()` reuses the current validator's canonical frequency,
quantity, window and sensitivity parsers, returning `SeparatedSetupOperands`.
`line_comparison_operands` contains only LINE correlator-window requirements
and their own WINDOW-scoped RMS declarations; it **never includes optional
physical SPWs**. `continuum_window_evidence` contains only physical SPW
records, exactly once per physical ID; linking one to a LINE requirement
creates no extra physical bandwidth record. This separate collection is
compatible with `rules.continuum_setup.qualify_window` and the existing
USABLE/NOMINAL distinctions. The existing legacy Continuum declaration and
conflict logic remain untouched and executable for legacy requests.

These are preparatory typed ports, **not** a mapped `ProposedObservationRequest`
for new-format assessment. Mapping both sets into old
`request.spectral_windows` would reintroduce mixed roles. Step 03b-B will
connect independent browser row editing; Step 03b-C will cover end-to-end
association and Continuum counting. Step 04 must add a separately approved
LINE evaluation scope, with its own formal negative-verdict semantics; until
then new-format science remains fail-closed.

## Acceptance

- Identical legacy request parses and serializes without new fields.
- New scope yields typed independent LINE/physical operands but no formal run.
- Explicit duplicate IDs, dangling/ambiguous links, conflicting old/new
  representations, missing LINE inputs, unsupported bandwidth semantics and
  user-supplied validation markers fail validation.
- Physical completeness true or false cannot authorize LINE evaluation.
- Fail-on-invocation source providers remain untouched for both geometries.
- No UI, Archive, Mosaic geometry, numerical LINE rule, or report-schema edits.
