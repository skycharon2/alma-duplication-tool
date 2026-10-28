# Step 03b-C — cross-scope acceptance for separated LINE and physical SPW inputs

## Purpose and implementation status

This is a **tests-and-documentation-only** acceptance step, based on PR #194
(`main` commit `9c21ce009791387c81febfaf56e7fc76aab64cd7`). It introduces no
new production behavior, science method, Archive retrieval, Mosaic geometry,
shared validator, report field, or UI layout change.

Its supported end-to-end boundary is:

`POST /proposed/separated` → exported JSON → `parse_separated_setup()` →
independent typed LINE and physical-SPW operand preparation →
`validate_proposed_observation()` / `assess_observation()` **fail closed**.

The new editor currently exposes LINE input and physical SPW editing, not
Continuum-only editing or Mosaic OT pointings upload. Consequently, tests of
new-contract Continuum-only and mixed-purpose requests adjust the exported
JSON **at the shared wire-contract boundary**; they do **not** claim an
end-to-end Continuum browser workflow or a computed Continuum report. Real
Mosaic candidate discovery and execution are not authorized yet.

## Acceptance matrix

| Dimension | Exact assertion |
| --- | --- |
| Geometry | Single Pointing and Mosaic export independent records; Mosaic position is null, Single uses ICRS. |
| Physical completeness | False and true remain `physical_spw_inventory_complete` only; neither creates legacy `setup_complete` nor authorizes formal LINE science. |
| LINE operand selection | Only explicit requirements enter `line_comparison_operands`; a physical SPW, linked or unlinked, cannot add a pair or RMS. |
| Second LINE requirement | Distinct per-window ID, RMS, mode and resolution; missing RMS rejects browser export regardless of physical bandwidth evidence. |
| REST preparation | Shared redshift converts a REST correlator-window centre in both geometries; missing redshift prevents export. |
| Continuum evidence | Only `continuum_window_evidence` contributes physical SPWs. One linked physical SPW is counted once; same frequency does not merge two different SPW IDs. |
| Bandwidth semantics | USABLE is checked directly; NOMINAL remains unresolved without approved mapping, and may qualify with `PORTAL_SCRIPT_V1`. |
| Independent purposes | Mixed and Continuum-only wire requests retain physical evidence without cloning LINE operands; no new formal science is authorized. |
| Lifecycle / link | Removing optional SPW cannot remove LINE requirement; deleting linked LINE requirement fails until unlinked. |
| Execution | Browser POST `action=assess` and shared `assess_observation()` do not invoke providers, produce a report, or claim a formal negative. |
| Legacy | Legacy request remains valid/search-ready and carries no new contract field. |

## Scientific guardrails

- The requested LINE frequency is the *correlator window center*; it is not
  inferred from a molecular transition or a physical SPW bandwidth record.
- `prepare_line_window()` is used only to verify typed LINE operands. No
  numerical comparison against Archive candidates is performed here.
- `qualify_window()` checks physical Continuum bandwidth operands separately.
  Qualification of two widths is **not** a formal Continuum duplication verdict.
- At this step, `SUBMITTED_LINE_REQUIREMENTS_V2` remains reserved. Neither
  physical inventory completeness nor an exhaustive set of submitted LINE
  requirements can be used to force the legacy `archive_line_context_or_1`
  branch to a negative verdict.
- No physical SPW records are cloned from LINE links, and no distinct physical
  SPW IDs are merged by frequency.

## Run locally

```bash
python -m pytest -q tests/integration/test_separated_cross_scope_step03bc.py
python -m pytest -q \
  tests/integration/test_separated_setup_contract_step03ba.py \
  tests/ui/test_separated_editor_step03bb.py \
  tests/ui/test_line_run_required.py \
  tests/integration/test_line_scope_transition_baseline.py \
  tests/integration/test_mosaic_scientific_acceptance.py
python -m pytest -q
ruff check tests/integration/test_separated_cross_scope_step03bc.py
git diff --check
```

## Exit criteria

Both the focused and full suite pass on a real ALMA development environment;
Ruff and Git diff checks pass. The PR contains **only this integration test and
this document**. Specifically, there should be no diff under `src/`, the
Archive clients, `rules/`, `cli/`, or `ui/`. The merge base must include PR #194.

After the PR merges, Step 04 can separately implement and review the V2 LINE
scoping and aggregation. Approval of Step 03b-C does *not* approve V2 science.
