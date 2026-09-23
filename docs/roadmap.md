# Engineering delivery roadmap

Reviewed implementation baseline: `13c41d5b5cef9ebabce803dad16101a650c8c087` (PR #76 merged).
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

## Remaining delivery order

| Increment | Work | Exit gate |
| --- | --- | --- |
| Queue single-point evidence and rules — current focus | Use the [mapping table](queue_single_point_mapping.md) to close source-specific position, angle, continuum and line evidence. Continuum need not wait for FDM/TDM closure. | Exact row/setup/SPW links, explicit missing/conflict reasons, independently calculated positive/negative/boundary cases; supported scope and method status recorded |
| Dual-source acceptance | Exercise Archive and supported Queue branches on the same request; acquire actual proposal cases with independent review | Source failures, incomplete retrieval, unsupported geometry and display truncation remain visible; no invented scientific labels |
| Thin browser interface | Input, candidates, independent branches, pair evidence and export using the backend report | UI/CLI agreement, no duplicate formulas, no UNKNOWN/empty-source-to-negative conversion |
| Broader modes — deferred | Mosaic, moving targets, TP scientific evaluation, mixed setups and broader conversions | Separate scope, evidence and acceptance decisions |

Queue mode work must resolve applicability and alternative interpretations within
the supported scope. Exact processor identity is required only where the method
needs it; exact configuration uniqueness is not the same as mode consensus.
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
