# Thin-interface contract over report v4

Contract version 1, backend baseline PR #73 (`a3d2923`). The browser UI is not
implemented by the acceptance increment. The [form sketch](proposed_observation_form.md)
owns layout; the [request API](proposed_observation_api.md) owns field validation;
[reporting](evaluation_cli.md) owns JSON; [rules](rules.md) owns every formula and
aggregation. This document defines how the first UI must consume those contracts.

## Three actions

1. Edit proposed observation plus search options; call the existing validator.
   Show ERROR at the affected field; distinguish selected-branch MISSING from
   EVIDENCE provenance notes. Valid partial inputs can search. LINE REST centers
   require explicit redshift for evaluation; planned resolution can use frequency
   or velocity units. Missing noise bandwidth alone does not block the confirmed
   direct line method. Invalid supplied fields still fail validation.
2. Run the existing search/evaluation pipeline and display its report. Candidate
   selection does not set FDM, confer continuum bandwidth eligibility, fill missing
   RMS or supply a scientific verdict. Valid SUN produces the existing no-search
   exemption. Queue mappings keep their source-specific limitations.
3. Expand a context/pair and export the **same complete report**, including hidden
   contexts. Never rebuild report criteria from a displayed subset or calculate
   formula/aggregation logic in the browser. A diagnostic inspection is an optional
   separate export, not a replacement for report v4.

## Labels and ownership

| Report path / state | Display meaning | Forbidden inference |
| --- | --- | --- |
| report_kind=SOLAR_EXEMPTION | Solar observation: assessment not applicable; search not performed | Zero duplicate candidates after a completed search |
| branches[].status=CRITERIA_MET | Meets the criteria for this branch and context | Entire proposal/search confirmed duplicate |
| branches[].status=CRITERIA_NOT_MET | Does not meet this branch's criteria in this context | No duplicates exist anywhere or in the other branch |
| branches[].status=INDETERMINATE | Insufficient evidence or unsupported scope; expand reasons | False / safe to ignore |
| criterion.outcome=null | Not computed; display evaluation/applicability/reasons | Numeric zero, failed condition or unavailable value borrowed from another pair |
| criterion.approval=PROVISIONAL | Method remains provisional | Formal approval just because an outcome was computed |
| top-level NOT_AGGREGATED | Inspect independent context branches; no whole-search assessment | A failed run or “no duplication” |
| zero context_evaluations | No evaluated retained candidates within this run | Proof of absence |
| sources[].status FAILED/INCOMPLETE/NOT_PROVIDED | Source not successfully covered; show other available results | A completed empty source |
| result_limit / display_truncated | Display cap; show retained, shown and evaluated counts | Retrieval cap or skipped hidden evaluation |
| line_pairing.assessment=NOT_EVALUATED | Preparation builder did not judge criteria | LINE evaluator did not run; read line_pairs and branches |

Both intents render separate branches; neither branch silently overrides the other.
The UI must not turn UNKNOWN into a binary boolean. Preserve new/unrecognized
reason codes as visible details rather than guessing their meaning.

## Pair details and source scope

Use `context_evaluations[].line_pairs[]`. Show proposed window and candidate
Source–SPW/component together. Keep the reference associated with all six criteria.
Render `derived` key/value arrays with their declared units: sky/interval GHz,
resolution km/s, angular resolution arcsec and RMS mJy/beam. A blocked RMS has
null computed values; explain the dependency and show the available resolution.
No condition from another pair may be substituted for a missing one.

Show original input and mode provenance in expandable evidence details. Where
report v4 contains a reference rather than full raw content, link to the retained
capture only if that artifact is available; do not invent raw values. A source
status of COMPLETED does not establish all-sky coverage or an up-to-date Queue.
Show capture/snapshot date, effective filters and retrieval limitations separately
from display truncation. Report v4's existing generated timestamp is not a capture date.

## Optional gap inspection

`report_inspection.inspect_report(report_document)` is a read-only report consumer.
It neither re-evaluates science nor modifies report v4. `inspection_version=1`
provides branch counts, source statuses, scope and traceable gap occurrences:

- USER_INPUT_MISSING: missing proposed evidence.
- ARCHIVE_EVIDENCE_MISSING: unavailable candidate evidence; not a demand to edit the proposal.
- ASSOCIATION_UNRESOLVED: source/SPW/reference cannot be safely linked.
- SCOPE_UNSUPPORTED: geometry, array/source mapping or branch applicability is outside scope.
- SOURCE_OR_SEARCH_INCOMPLETE: missing/failed/incomplete sources or unevaluated requested filters.
- METHOD_OR_DEPENDENCY: unapproved method or blocked calculation such as coarse resolution.
- UNCLASSIFIED: a reason not safely mapped by the current consumer; preserve its code and location.

Counts concern unevaluable evidence, including issues in otherwise false or true
branches. They are not counts of duplicate observations. Multiple reasons can
refer to one context; do not sum category totals as candidate totals. Shared
POS-SINGLE and ANGULAR count once per context, not once per pair. Distinct line
pairs and request-level diagnostics remain separate occurrences. Each group
reports unique affected contexts, unscoped occurrences and reason-code counts.
Source/filter gaps remain distinguishable through their original code/location.
Do not label every unresolved reason “missing user input”.

## First UI acceptance gate

Use the [pinned catalog](acceptance_cases.md). Compare the UI-exported report with
the backend report, accounting only for genuinely run-generated timestamp fields.
Keep input/capture hashes, methods, associations, all retained contexts and outcomes
identical. The UI must demonstrate guide A/B, mixed intents, missing RMS, coarse
resolution blocking, multi-window pair expansion, source-not-provided and display
truncation. Add a Solar exemption check and explicit unsupported request handling.
No formula or independent aggregation implementation belongs in the browser.
Human review of actual proposal cases remains visibly separate from UI/CLI parity.
