# Thin-interface contract over report v4

Contract version 2. The [shared entry](assessment_entry.md) and configuration
preflight are implemented; [status](status.md) owns the reviewed baseline.
The browser UI is not implemented yet. The [form sketch](proposed_observation_form.md)
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
2. Call [assess_observation](assessment_entry.md) and display its report. Candidate
   selection does not set FDM, confer continuum bandwidth eligibility, fill missing
   RMS or supply a scientific verdict. Valid SUN produces the existing no-search
   exemption. Queue mappings keep their source-specific limitations.
3. Expand a context/pair and export the **same complete report**, including hidden
   contexts. Never rebuild report criteria from a displayed subset or calculate
   formula/aggregation logic in the browser. A diagnostic inspection is an optional
   separate export, not a replacement for report v4.

## Effective backend configuration

Selecting Queue as a source does not enable its formal science methods.
`evaluate_candidate_search()` still defaults `queue_continuum` and `queue_line`
to False. The UI integration must explicitly enable the formal Queue option for
each selected intent when Queue is selected, and display the report's effective
`evaluation_configuration`. Reuse the existing option implications/validation;
do not create an independent UI method-selection policy. Solar exemption must
continue to run before source access.

The [shared LINE precision contract](line_precision.md) separates exact decision
operands from display floats. Display the backend results; never reconstruct a
comparison from rounded values or parse rational evidence to run browser rules.

## Call order and execution errors

Construct `request`, `search_options` and explicit `AssessmentOptions` first,
then call `assess_observation()`. When `AssessmentResult.document` is present,
render and export that report v4 document; derive the optional gap view with
`inspect_report(document, inspection_version="3")`. Inspection is a report
consumer, not a step that selects Queue methods or precedes assessment.

Invalid/non-search-ready input returns validation details without a document.
Source failures can leave a usable report with independent source states.
Configuration and provider-construction exceptions may propagate: display an
execution error without inventing a report or a scientific outcome. Valid Solar
requests return the exemption before method checks and source access. See the
[application contract](assessment_entry.md) for the exact execution boundary.

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
Render each result/evidence value according to the unit defined by its backend
field/report contract. For `derived` key/value arrays, preserve the field-specific
unit indicated by the field name and report contract; do not apply one
source-agnostic label. Queue LINE includes MHz resolution quantities and mJy
candidate/comparable RMS alongside proposed mJy/beam;
do not apply one source-agnostic label. Queue LINE includes MHz resolution
quantities and mJy candidate/comparable RMS alongside proposed mJy/beam. A blocked RMS has
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
It neither re-evaluates science nor modifies report v4. The default
`inspection_version="3"` provides branch counts, source statuses, scope and
traceable gap occurrences. Versions 1 and 2 remain explicitly callable to
reproduce their historical behavior; new consumers use version 3.

Version 3 retains the version 2 categories:

- USER_INPUT_MISSING: missing proposed evidence.
- ARCHIVE_EVIDENCE_MISSING: unavailable Archive candidate evidence; not a demand to edit the proposal.
- QUEUE_EVIDENCE_MISSING: unavailable Queue candidate evidence; not a demand to edit the proposal.
- ASSOCIATION_UNRESOLVED: source/SPW/reference cannot be safely linked.
- SCOPE_UNSUPPORTED: geometry, array/source mapping or branch applicability is outside scope.
- SOURCE_OR_SEARCH_INCOMPLETE: missing/failed/incomplete sources or unevaluated requested filters.
- METHOD_OR_DEPENDENCY: unapproved method or blocked calculation such as coarse resolution.
- UNCLASSIFIED: a reason not safely mapped by the selected consumer version; preserve its code and location.

Versions 2 and 3 classify Queue candidate-side missing quantities as
Queue evidence, position-scope unresolved reasons as scope limitations and Queue
resolution-coarser-than-planned as a method/dependency blocker. It reports
`REQUESTED_FILTERS_NOT_FULLY_EVALUATED` only for a `COMPLETED` source; the false
property value that necessarily accompanies `NOT_SELECTED`, `NOT_PROVIDED`,
`FAILED` or `INCOMPLETE` is not a second filter-completeness gap. Version 1 keeps
the prior category vocabulary and mappings unchanged.

Counts concern unevaluable evidence, including issues in otherwise false or true
branches. They are not counts of duplicate observations. Multiple reasons can
refer to one context; do not sum category totals as candidate totals. Shared
POS-SINGLE and ANGULAR count once per context, not once per pair. Distinct line
pairs and request-level diagnostics remain separate occurrences. Each group
reports unique affected contexts, unscoped occurrences and reason-code counts.
Source/filter gaps remain distinguishable through their original code/location.
Do not label every unresolved reason “missing user input”.

For pair gaps, v3 adds `pair_identity` with context, proposed window, pair index
and the original source-specific reference. Its `location` is a JSON Pointer to
the criterion in this exact report. Distinct SPWs must remain separate even if
they share the same reason. An unresolved reference can be null; do not invent
an association. Other location strings retain their existing convention. Report
indices are not cross-run identifiers. See the [inspection contract](report_inspection.md).

## First UI acceptance gate

Use the [pinned catalog](acceptance_cases.md). Compare the UI-exported report with
the backend report from the same run without dropping any fields. For separate
UI/CLI runs, exclude only the execution timestamp paths identified in the
[roadmap](roadmap.md#bounded-maintenance-increments).
Keep input/capture hashes, methods, associations, all retained contexts and outcomes
identical. The UI must demonstrate guide A/B, mixed intents, missing RMS, coarse
resolution blocking, multi-window pair expansion, source-not-provided and display
truncation. Add a Solar exemption check and explicit unsupported request handling.
No formula or independent aggregation implementation belongs in the browser.
Human review of actual proposal cases remains visibly separate from UI/CLI parity.
