# Engineering delivery roadmap

The reviewed implementation baseline and current verification conditions are
maintained in [status](status.md).
Archive and supported Queue continuum/LINE dual-source engineering acceptance is
delivered in the supported fixed single-field scope. No independently reviewed
real-proposal case is claimed.
This is the sole owner of remaining engineering order and exit gates.
[Status](status.md) owns the capability matrix; [rule inputs](duplication_rule_inputs.md)
own scientific decisions. An experiment being delivered does not approve its method.

## Completed increments

| Delivery | Scope | Boundary |
| --- | --- | --- |
| PR #70 | Archive continuum and branch aggregation | Confirmed fixed-target, single-point scope |
| PR #71 | Continuum input/report closure and Solar exemption | No retrospective approval of older reports |
| PR #72 | Archive line request preparation, mode evidence and pair builder | Exact Source–SPW associations |
| PR #73 | Archive line numerical rules and pair/branch reports | No search-wide absence verdict |
| PR #74 | Reproducible acceptance catalog and thin-interface contract | No independently reviewed real-proposal labels claimed |
| PR #75 | Queue mode/configuration census v1 | Conditional diagnostic, not formal LINE-FDM |
| PR #76 | Queue processor-equivalence experiment | Conditional TPS mapping; incomplete enumeration; formal mode UNKNOWN |
| PR #77 | Documentation ownership and Queue mapping table | No runtime or scientific approval change |
| PR #91 | Shared LINE precision contract and both-source boundary regression | Exact decision operands; no global epsilon |
| PR #92 | Inspection v3 pair identities and common-condition deduplication | Report consumer only; explicit historical v1/v2 retained |

## Bounded maintenance increments

These small commits support the thin UI; they are not a new prerequisite
rearchitecture phase. DOC-BASE, LINE-HELPERS, GEOMETRY, SPATIAL-EVIDENCE,
MODE-REFERENCE and APP-ENTRY are delivered. Configuration preflight is also
implemented (PR #100). The next product delivery is the thin browser interface.

| Commit | Scope | Exit gate |
| --- | --- | --- |
| DOC-BASE — delivered in PR #93 | Align architecture, current status, interface versions and this order | Current vs historical state is explicit; relative links resolve; no runtime change or new test required |
| LINE-HELPERS — delivered | Extract shared rational display and explicit unit conversion into numerical helpers, criterion truth into aggregation | First verify equivalent behavior; boundary tests and acceptance retain numbers, reasons, methods and outcomes; keep source-specific result/evidence/RMS implementations |
| GEOMETRY — delivered (3A) | Extract pure separation and beam formulas | Preserve spherical/offset/placeholder and boundary behavior; keep legacy boundary conventions in strategies; do not claim all cycles removed yet |
| SPATIAL-EVIDENCE — delivered (3B) | Separate spatial evidence adaptation from strategy dispatch | Queue strategy depends on adaptation rather than dispatch; remove target reverse imports; preserve retention, formal POS and explicit legacy paths, with compatibility exports where needed |
| MODE-REFERENCE — delivered | Separate reference configurations/mappings from experiment report generation | Formal adapter no longer consumes experiment report dictionaries; configuration IDs, matches, N16 allowance, mode results and historical CLIs unchanged |
| APP-ENTRY — backend entry delivered; browser integration next | Shared application orchestration used by CLI and directly callable by frontends | Offline direct-call/CLI report agreement; browser UI agreement remains required at UI delivery |

LINE-HELPERS verification on 2026-09-28: 29 helper contract cases plus 116
existing LINE regressions passed; full suite with the pinned Queue snapshot was
1370 passed, 9 skipped; Ruff F passed. Before/after acceptance each passed all
15 cases. Full report comparison differed only at `generated_at`,
`search_started_at`, `search_finished_at` and Queue snapshot `parsed_at`;
all 15 inspection documents were identical. No scientific version or pinned
catalog/reference changed. Live TAP was not run.

GEOMETRY verification on 2026-09-28: 267 targeted tests passed (including
9 new pure-helper/import checks); full suite with pinned Queue snapshot was
1379 passed, 9 skipped; Ruff F passed. The extracted function bodies were checked
against the baseline AST. Before/after acceptance each passed 15 cases; report
comparison excluded only the same four execution timestamp paths listed above,
and all inspection documents were identical. No method or report versions
changed. Source adaptation remains a separate 3B increment; UI need not wait.
Live TAP was not run.

SPATIAL-EVIDENCE verification on 2026-09-28: 300 targeted tests passed,
including 10 compatibility/import-boundary cases. Full suite with pinned Queue
snapshot was 1389 passed, 9 skipped; Ruff F passed. The five moved functions and
retained dispatcher are AST-identical to the baseline. Before/after acceptance
passed all 15 cases; complete reports differed only at the four execution
timestamp paths above and all inspections were identical. No scientific method,
report, evidence schema or fixed reference changed. Live TAP was not run.

MODE-REFERENCE verification on 2026-09-28: full suite with pinned Queue
snapshot passed 1393 tests, with 9 skipped; Ruff F passed. All 3498 reference
configuration records and their formal/experimental outputs were byte-identical.
The adapter, processor census and original mode census produced byte-identical
artifacts for all 16216 snapshot SPWs. Before/after acceptance passed 15 cases;
reports differed only at the four timestamp paths above, inspections were
identical. No scientific method, N16 allowance, catalog or report version changed.
Live TAP was not run.

APP-ENTRY verification on 2026-09-28: 11 direct-entry regressions cover
CLI/application report agreement, Solar/invalid-request no-source access,
configuration checks and failed-source reporting. Full suite with pinned Queue
snapshot passed 1404 tests, with 9 skipped; Ruff F passed. Before/after acceptance
passed all 15 cases; only the same four execution timestamps differed and all
inspection documents were identical. Browser rendering and UI-specific method
selection remain to be delivered. Live TAP was not run.

Each code increment runs affected tests and the pinned acceptance catalog, then
full regression before merge. Compare reports allowing only identified dynamic
execution fields, never ignoring methods, reasons, associations or outcomes.
Function relocation alone does not bump scientific method versions. Record and
fix discovered behavior defects separately. Keep dated reports and reference
hashes intact; retain the recorded baseline described in [status](status.md).

## Remaining delivery order

| Increment | Work | Exit gate |
| --- | --- | --- |
| QUEUE-COMMON — coherent single-field row scope delivered | Scoped single-point position and angular-resolution evidence | Supported geometry/frame/array interpretation, boundaries and missing/conflict behavior explicit; independent numerical cases and method status recorded |
| QUEUE-CONTINUUM — coherent single-field row scope delivered | Queue frequency/RMS mappings and independent continuum branch | Same-context/setup evidence, positive/negative/boundary/unknown cases; source-specific sensitivity semantics; no FDM/TDM prerequisite |
| QUEUE-LINE — fixed single-field regular-SPW scope delivered | Mode applicability, coherent same-window coverage/resolution/RMS and pair reports | Supported configuration/profile evidence; no cross-SPW borrowing; coarse-resolution blocking; independent intermediate-value and pair aggregation acceptance |
| Thin browser interface | Input, candidates, independent branches, pair evidence and export using the backend report | UI/CLI agreement, no duplicate formulas, no UNKNOWN/empty-source-to-negative conversion |
| Broader modes — deferred | Mosaic, moving targets, TP scientific evaluation, mixed setups and broader conversions | Separate scope, evidence and acceptance decisions |

The [first Queue common increment](queue_common.md) supplies opt-in coherent
single-field row-beam position, including the supported 7 m/12 m
`standAlone_ACA` interpretation, and separately scoped angular criteria. [Queue continuum](queue_continuum.md)
and [Queue LINE](queue_line_pairing.md) now complete the supported fixed
single-field branches. Formal same-request Archive+Queue continuum/LINE
acceptance, cross-source/SPW isolation and source-state completeness are also
delivered. The bounded preparatory increments above are complete; the next
product delivery is the thin browser interface. Broader component-specific and
mixed-array interpretations beyond the supported row-level scope remain separate
extensions.

Independent review of an actual proposal remains an external validation gate.
No genuine proposal input is currently available, so
`reviewed_real_proposal_cases` remains zero. Do not synthesize or relabel a case
to satisfy that gate.

These are engineering increment IDs, not scientific Q1–Q8 question IDs. The
[mapping table](queue_single_point_mapping.md) owns detailed fields, units,
associations and evidence gaps; this table owns order and exit gates only.

Queue mode work must resolve applicability and alternative interpretations within
the supported scope. Exact processor identity is required only where the method
needs it; exact configuration uniqueness is not the same as mode consensus.
The [mode evidence adapter](queue_mode_adapter.md) supplies source-bound
exact-first classification and the reviewed N16 allowance to formal Queue LINE.
Geometry/array applicability remains independently scoped, and broader array or
mode interpretation remains a separate extension.
The 76 export signatures and 14 all-family TP mapping gaps are tracked in the
[dated experiment results](evidence/queue_processor_consensus_2026-09-23.md).
Do not make all-family experimental closure a blanket prerequisite for Queue continuum.

## Thin UI delivery increments

1. Report display and export — implemented as a [read-only viewer](ui_report_browser.md): consume existing acceptance reports; show each
   source status, independent continuum/LINE branches and context/window/SPW
   evidence. Export the same complete report, optionally with inspection v3.
2. Minimal form: one setup, multiple windows, both intents, explicit units and
   a controlled Queue snapshot. Construct explicit AssessmentOptions before
   calling the shared entry. Distinguish missing from invalid input, no-document
   validation results, propagated execution exceptions and usable partial-source
   reports. Preserve Solar exemption and unsupported-scope explanations.
3. Browser/CLI agreement: reuse the catalog for mixed intents, missing RMS,
   coarse resolution, multiple pairs, source failure/missing/empty results and
   display truncation; include Solar. A same-run download preserves the original
   report. Separate-run comparison may ignore only the four execution timestamp
   paths recorded above, never methods, provenance, associations or outcomes.

Independent real-proposal review continues separately; broader modes do not
become a blanket prerequisite for these UI increments.

## Weekly report measures

Record retained/assessed contexts by source; evaluable/pass/fail/unknown counts;
blocking reasons; independent numerical versus reviewed real cases; source and
retrieval completeness; and method versions. More passing tests alone do not
establish scientific acceptance.

## Earlier plan

The [pre-cleanup plan](https://github.com/skycharon2/alma-duplication-tool/blob/13c41d5b5cef9ebabce803dad16101a650c8c087/docs/pr_plan_2026-09-21.md)
retains the original delivery gates and dated measurements. Historical Q1–Q8
question IDs are distinct from the old engineering Q0/Q1 increment labels.
