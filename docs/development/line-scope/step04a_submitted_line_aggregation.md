# Step 04A — submitted-LINE context OR (not an executable science entrypoint)

## Status

This step adds the **pure, unconnected** `archive_line_context_submitted_or_2`
context aggregator in `alma_duplicate.rules.submitted_line`. It does **not**
activate `SUBMITTED_LINE_REQUIREMENTS_V2`, change the shared validator, or make
`SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1` executable. The existing guard
`SEPARATED_INPUT_NOT_EXECUTABLE` remains in force for both Single Pointing and
Mosaic; existing legacy LINE requests and their output bytes/method versions
remain unchanged.

Review of the new aggregation method does not by itself approve or establish
whole-project non-duplication. There is no search-wide absence inference.

## Accepted operands

`aggregate_submitted_line_context` accepts **only**:

- A tuple of explicit LINE requirement IDs, in submission order. These IDs
  should ultimately come from `SeparatedSetupOperands.line_comparison_operands`,
  never from optional physical SPW evidence.
- A `LinePairBuildResult` for **one candidate context**, containing no attempt
  for an ID outside the submitted requirements.
- A tuple of existing `LinePairEvaluation` values for that same pairing, each
  with its **six independent criteria**, including the correct position
  criterion (`POS-SINGLE` or `POS-MOSAIC`) and the approved
  `archive_line_pair_and_1` per-pair method.
- The geometry and a trusted science evaluator's computed context-supported
  Boolean. A browser-supplied flag must never be accepted as support evidence.

It validates unique requirement IDs and matching attempt/pair/context identity.
An extra unsubmitted attempt, duplicate pair, wrong geometry, stale pairing
attempt, or cross-context evaluation is a programmer/contract error. Missing
submitted attempts/evaluations are **not** treated as FALSE: they contribute
UNKNOWN and appear in `missing_requirement_ids`.

The result retains the **original pair objects**, their criteria, window IDs,
component references and source context. The aggregation does not splice
criterion outcomes across windows or candidate SPWs.

## Three-valued aggregation

Within a supported candidate context, using `three_or()` over entire pair
outcomes (with an UNKNOWN for each missing submitted evaluation):

| Input | V2 context result |
| --- | --- |
| Any complete evaluated pair TRUE | TRUE |
| At least one UNKNOWN and no TRUE | UNKNOWN |
| Every submitted pair FALSE, none missing | FALSE |
| Zero submitted requirements | UNKNOWN |
| Unsupported candidate context | UNKNOWN regardless of pairs |

A V2 FALSE is limited to **this one candidate context and the submitted LINE
requirements**. It is not a statement about unsubmitted windows, the full setup,
the entire Archive, a project, or the absence of duplication elsewhere.

### Explicit separation from physical inventory

No `setup_complete`, `physical_spw_inventory_complete`, physical bandwidth,
`line_evaluation_scope`, or client-provided validation flag is accepted by the
04A aggregator. The legacy pairing result's
`proposed_enumeration_complete` field is deliberately **not consulted**. In
particular, one definite FALSE with a partial physical SPW inventory stays
FALSE in **this V2 context-only result**, whereas the existing legacy
`archive_line_context_or_1` would still report UNKNOWN.

This must **not** be achieved by passing new physical SPW records into the old
`request.spectral_windows` list, or by setting legacy `setup_complete=True`.

## Versions and provenance

- Context-OR method: `archive_line_context_submitted_or_2`.
- Reused (unchanged) full-pair method: `archive_line_pair_and_1`.
- New context scope: `ONE_CANDIDATE_CONTEXT_SUBMITTED_LINE_REQUIREMENTS_ONLY`.
- Result container: `SubmittedLineContextResult` with the new branch,
  ordered `submitted_requirement_ids`, original per-pair values and explicit
  `missing_requirement_ids`.
- Old context method remains `archive_line_context_or_1` and retains its
  `PROPOSED_ENUMERATION_INCOMPLETE` semantics.
- No reporting schema/JSON, Archive, Queue, s_region, UI or CLI changes.

## Required later work (Step 04B/04C)

A separately reviewed evaluator must construct V2 pairing attempts **only**
from the typed `line_comparison_operands`, calculate actual context support
(including Archive source, association, alternatives and spatial scope),
prepare approved pair criteria using the existing reference-bound science,
and invoke this aggregator. It must retain fail-closed behavior for invalid
or unsupported inputs and explicitly integrate the new method version into
report provenance. Step 04A does **not** do any of these operations.

Formal search-wide outcomes, Continuum support in the new input contract,
and independent real-proposal policy approval remain out of scope.

## Acceptance

The regression suite runs existing offline Guide B paired evidence in both
geometries, checks all three truth values, false/true and false/unknown
multiwindow combinations, cross-pair isolation, missing pairs, duplicate IDs,
source-context mismatch, physical inventory independence, and legacy method
stability. No live Archive or AQ access is needed.

```bash
python -m pytest -q tests/integration/test_submitted_line_aggregation_step04a.py
python -m pytest -q \
  tests/integration/test_line_scope_transition_baseline.py \
  tests/integration/test_line_scope_contract_step02.py \
  tests/integration/test_separated_setup_contract_step03ba.py \
  tests/integration/test_separated_cross_scope_step03bc.py \
  tests/integration/test_line_evaluation.py \
  tests/integration/test_mosaic_scientific_acceptance.py
python -m pytest -q
ruff check src/alma_duplicate/rules/submitted_line.py \
  tests/integration/test_submitted_line_aggregation_step04a.py
git diff --check
```
