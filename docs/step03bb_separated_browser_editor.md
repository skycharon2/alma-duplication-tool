# Step 03b-B — separated browser row editing and versioned request export

## Scope

Add a distinct `/proposed/separated` browser editor for the existing
`SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1` contract. The current `/proposed`
form stays operational and unchanged except for one navigation link; its
legacy assessment, CLI parity, existing Continuum selection, and historical
report bytes remain unchanged.

This new route **validates and exports request JSON but cannot run science**.
The shared validator's `SEPARATED_INPUT_NOT_EXECUTABLE` rejection remains in
place. The editor ignores this *single* execution-gate diagnostic solely to
allow a structurally valid download; it never strips it for evaluation. A
submitted `action=assess` is refused in the editor itself without constructing
an Archive or Queue provider. This is deliberate until the separately reviewed
Step 03b-C/04 integration work is complete.

## Distinct collections and stable identities

- `line_rows` uses stable `l` + 12-hex row tokens. Add/remove actions affect
  *only* `request.line_requirements`; these windows describe the requested
  **correlator-window centers** (not individual line rest frequencies), mode,
  planned spectral resolution and RMS.
- `spw_rows` uses separate `p` + 12-hex tokens. Add/remove affects *only*
  `request.physical_spw_evidence`. A physical row may carry its own center,
  optional bandwidth, `USABLE`/`NOMINAL`/`UNKNOWN` semantics, and a link to an
  existing LINE requirement ID. Frequency matches never create links.
- “Add optional linked bandwidth evidence” creates exactly **one** physical
  record and sets its explicit link; no additional LINE RMS is requested.
  Once a LINE row is linked, deleting it is blocked until the user unlinks
  its physical SPW. At most one physical SPW may link to one LINE requirement,
  as required by Step 03b-A.
- A shared source redshift applies to REST frequencies. `physical_spw_inventory_complete`
  is an independent checkbox; it is always serialized as a Boolean and never
  translated to legacy `setup_complete` or LINE completeness.
- Neither collection is internally merged or deduplicated by scientific value;
  duplicate/ambiguous identities are instead rejected by the shared contract.

## Deliberate limits

- The new editor initially selects only `LINE` purpose and `ARCHIVE` source.
  Existing Continuum declaration and formal assessment remain available in
  the legacy form. Wiring new-contract Continuum RMS and its complete report
  semantics belongs to Step 03b-C. **No Continuum bandwidth criterion is run
  by the new editor**; physical evidence is only exported and validated here.
- Mosaic geometry can be recorded in the new contract but OT pointings are not
  yet acquired or bound by this editor; no Mosaic assessment is attempted.
- The new input is not a report, does not produce a negative conclusion, and
  does not enable `SUBMITTED_LINE_REQUIREMENTS_V2`.
- The current legacy form may still show old combined rows; a new navigation
  link deliberately distinguishes the separated editor during migration.

## Acceptance

Run the isolated browser tests, the Step 03b-A contract tests, Step 03 UI tests,
CLI/Continuum/Mosaic parity tests, then full pytest and Ruff. Verify that a
physical SPW only adds physical evidence; a second explicit LINE row missing
RMS fails; linked evidence is never cloned; shared REST redshift is serialized;
malformed row identities, dangling links, ambiguous links and mixed legacy
fields fail; the new route can never call a source provider. Existing report
and scientific backend files must not change.
