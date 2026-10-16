# Engineering delivery roadmap

[Status](status.md) owns the reviewed implementation baseline, supported scope
and verification register. This page owns remaining engineering order and exit
gates. The project plan remains the long-term design; scientific decisions belong
to [rule inputs](duplication_rule_inputs.md).

## Completed increments

- Supported Archive/Queue single-pointing CONTINUUM and LINE evaluation,
  coherent pair binding and dual-source engineering acceptance.
- Shared assessment entry, input validation, REST/SKY preparation, explicit
  continuum setup confirmation and supported unit/bandwidth mappings.
- Browser form-to-report execution, live TAP with optional post-TAP AQ,
  configured Queue snapshots, source-state visibility and offline UI/CLI parity.
- Bounded AUTO retrieval, stage progress, matching-detail v6 reports and indexed
  temporary disk storage. Live AUTO and four-workflow browser checks are already
  [recorded](evidence/browser_regression_pr134_2026-10-12.md).
- Readable Member-grouped reports and the independent
  [single-pointing explorer](ui_report_browser.md#single-pointing-report-explorer).
- Fresh four-workflow [browser-to-explorer acceptance](evidence/browser_explorer_acceptance_2026-10-13.md)
  on merged PR #139: self-retrieval, scientific plot operands, linked selection,
  sequential runs, pagination and unchanged exports. The evidence records the
  Queue snapshot date and one non-blocking SPW-label clarification.

Earlier increment IDs, test counts and extraction records are retained in
[delivery history](history/delivery_notes.md). They are not an active task list.

## Remaining delivery order

| Step | Work | Exit gate |
| --- | --- | --- |
| 1. Prepare a restricted supervisor preview | Define intended users, hosting, access control, source configuration, Queue snapshot freshness and temporary report retention. Clarify the recorded Queue SPW label; document and test the chosen runtime. | An authorized supervisor can submit a case and review results; access boundaries, concurrent progress polling, expiry/restart behavior, source failures and data removal are tested. No public Flask development-server deployment. |
| 2. Review supervisor cases | Collect actual proposals and expected judgments, distinguish self-retrieval from independent scientific review, and investigate discrepancies. | Record input provenance, reviewed labels, criterion-level explanations and known gaps; fix each confirmed defect in a bounded change with regression coverage. |

The new form-to-explorer path has been verified for the four recorded cases.
Repeat affected workflow checks after runtime or source-configuration changes;
saved-report checks alone do not verify a changed acquisition path.

A restricted preview does not automatically require a database or a general
multi-user platform. The current progress/index state is process-local and report
artifacts are on temporary disk. A single serving process needs concurrent
request handling so progress polls can run alongside assessment. Multiple
processes or persistent reports require a separate shared-state design and tests.
Operational requirements should determine that scope before deployment.

## Deferred extensions

- Mosaic and moving-target scientific inputs, methods and acceptance.
- Component-specific products or broader observing-mode interpretations require
  separate scientific evidence and approval. The current fixed-single-point
  policy ignores TP and preserves genuine 7m/12m branches; TP-only is not a valid
  normal proposal configuration or a planned supported branch. See the
  [current decision](evidence/single_point_tp_exclusion_decision_2026-10-16.md).
- Additional observation/configuration scope and source evidence outside the
  current confirmed contracts.
- Persistent multi-user report storage and shared execution state, if needed.
- Richer sky layers, spectral products and visualization exports after the
  first explorer has received user feedback.

Directory migration and module extraction are optional maintenance decisions,
not prerequisites for supervisor testing. A long Python file alone is not a
reason to split a scientifically tested path.

## Change and verification gates

For documentation-only changes, check current claims against their contracts,
relative paths/anchors and diff whitespace. Preserve dated evidence and pinned
reference bytes. Run the acceptance checks if their references are affected.

For runtime changes, run affected tests and the applicable acceptance/parity
gates. Scientific refactoring must preserve values, reasons, methods,
associations and outcomes; code relocation alone does not change a scientific
method version. The [UI/CLI parity contract](ui_offline_assessment.md#offline-uicli-parity-gate)
specifies permitted execution-time normalization and input-hash handling.
Keep source acquisitions opt-in and distinguish fake-source tests from live checks.

## Weekly report measures

Record retained/assessed contexts by source; evaluable/pass/fail/unknown counts;
blocking reasons; independent numerical versus reviewed real cases; source and
retrieval completeness; and method versions. Record data freshness and stage
runtime separately. More passing tests alone do not establish scientific acceptance.
