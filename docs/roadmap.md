# Engineering delivery roadmap

Reviewed implementation baseline: `f28e24f` (PR #92).
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
rearchitecture phase. Complete DOC-BASE and LINE-HELPERS first, then start UI.
The remaining extractions may proceed alongside UI work, independently.

| Commit | Scope | Exit gate |
| --- | --- | --- |
| DOC-BASE — this documentation increment | Align architecture, current status, interface versions and this order | Current vs historical state is explicit; relative links resolve; no runtime change or new test required |
| LINE-HELPERS — next | Extract shared rational display and explicit unit conversion into numerical helpers, criterion truth into aggregation | First verify equivalent behavior; boundary tests and acceptance retain numbers, reasons, methods and outcomes; keep source-specific result/evidence/RMS implementations |
| GEOMETRY | Extract pure separation and beam formulas | Preserve spherical/offset/placeholder and boundary behavior; keep legacy boundary conventions in strategies; do not claim all cycles removed yet |
| SPATIAL-EVIDENCE | Separate spatial evidence adaptation from strategy dispatch | Queue strategy depends on adaptation rather than dispatch; remove target reverse imports; preserve retention, formal POS and explicit legacy paths, with compatibility exports where needed |
| MODE-REFERENCE | Separate reference configurations/mappings from experiment report generation | Formal adapter no longer consumes experiment report dictionaries; configuration IDs, matches, N16 allowance, mode results and historical CLIs unchanged |
| APP-ENTRY — with first UI | Extract genuine shared CLI/UI orchestration | One validation/Solar/method-selection flow with injected clients/loaders; same effective configuration, science, source states and report for identical inputs |

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

The [first Queue common increment](queue_common.md) supplies opt-in main-12m
row-beam position and separately scoped angular criteria. [Queue continuum](queue_continuum.md)
and [Queue LINE](queue_line_pairing.md) now complete the supported fixed
single-field branches. Formal same-request Archive+Queue continuum/LINE
acceptance, cross-source/SPW isolation and source-state completeness are also
delivered. After the two bounded preparatory increments above, the next product
delivery is the thin browser interface;
source-bound 7-m/mixed-array interpretation remains a separate extension.

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

## Weekly report measures

Record retained/assessed contexts by source; evaluable/pass/fail/unknown counts;
blocking reasons; independent numerical versus reviewed real cases; source and
retrieval completeness; and method versions. More passing tests alone do not
establish scientific acceptance.

## Earlier plan

The [pre-cleanup plan](https://github.com/skycharon2/alma-duplication-tool/blob/13c41d5b5cef9ebabce803dad16101a650c8c087/docs/pr_plan_2026-09-21.md)
retains the original delivery gates and dated measurements. Historical Q1–Q8
question IDs are distinct from the old engineering Q0/Q1 increment labels.
