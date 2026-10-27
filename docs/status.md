# Current implementation status

Implementation reviewed on 2026-10-27: merged PR #178,
`f194fa50755204d54397b427810c23157b7759f5` (2026-10-26).
This identifies the code reviewed, not a claim that every historical test or
live-service check was rerun on this commit. Verification scopes are listed below.

This page owns the current capability summary and reviewed implementation
baseline. The [roadmap](roadmap.md) owns remaining order; contracts own behavior;
[rule inputs](duplication_rule_inputs.md#7-scientific-decision-register) own
scientific approval scope. The project plan describes long-term design.

## Supported workflow

| Capability | Archive | Queue |
| --- | --- | --- |
| Source access | Configured live TAP or offline replay; optional post-TAP live AQ or captured source-bound array evidence | Operator-configured CSV snapshot with source provenance; no claim that the snapshot is the current queue |
| Retrieval | Browser defaults to bounded AUTO scope; explicit-radius requests remain supported; incomplete retrieval stays visible | All supplied rows enter AUTO retrieval before optional filters; unsupported or unresolved evidence is not silently discarded |
| Single-point position and angular comparison | Implemented within the confirmed fixed-target scope; array evidence is bound to the exact source | Versioned row/array interpretation, supported blank-Mosaic offsets and complete 7-m/12-m beam alternatives |
| CONTINUUM | Proposed setup qualification, candidate position, angular resolution, representative frequency and aggregate RMS | Same branch structure with Queue-specific usable-bandwidth and sensitivity mappings |
| LINE | Coherent proposed-window/candidate-SPW FDM, coverage, resolution and RMS checks, plus common conditions | Same-row/SPW pairing with scoped mode evidence, unit preparation and comparable RMS |
| Evidence and results | Independent source states, method versions, missing reasons and exact associations | Independent source states and snapshot identity; no cross-source or cross-SPW borrowing |

Exact scientific scope belongs to [Archive array evidence](archive_array_evidence.md),
[Queue common](queue_common.md), [Queue continuum](queue_continuum.md),
[Queue LINE](queue_line_pairing.md), [rules](rules.md) and
[shared LINE precision](line_precision.md). Older provisional paths remain distinct.

## Archive Mosaic backend

Fixed-target Mosaic requests can import complete ICRS OT pointings and run against
Archive metadata through the shared assessment entry. Each comparison context uses
its own `s_region` for position and the existing Archive angular, continuum and
LINE rules for the remaining conditions. Auxiliary products and reconstructed
pointings are not required by the default path.

The [region contract](mosaic_s_region_position.md) owns geometry, boundary handling,
TP scope and result semantics. [Discovery](mosaic_candidate_discovery.md) retains
query completeness and candidate identity. Explicit reconstruction remains available
for research replay. Fixed-target Archive Mosaic execution is also available in
the browser; Queue Mosaic remains unsupported.

## Browser and report capabilities

- The [proposed form](ui_proposed_form.md) validates input and calls the
  [shared assessment entry](assessment_entry.md) with explicit source/method
  options. LINE and CONTINUUM can both be selected. Shared
  [REST/SKY preparation](proposed_frequency.md) supports explicit redshift;
  [continuum setup confirmation](continuum_setup_declaration.md) is a separate
  evidence route with conflict handling.
- [Live AQ](live_aq_assessment.md) is implemented when explicitly configured.
  It runs after TAP over retained linked Members, independently of display
  limits. Failed/incomplete acquisition retains TAP candidates with unresolved
  array evidence; the live-AQ path does not fall back to TAP antenna names.
- [Reports](ui_report_browser.md) lead with matching comparisons grouped by
  Member, preserving target, execution, SPW and beam identities. Technical
  records are optional. Original report, request and inspection exports remain
  available. New non-solar single-pointing browser assessments use [report v6](matching_report.md);
  the shared entry/CLI default remains full v4, and Solar exemptions retain v4.
  Inspection v3 reads v4/v5/v6; historical inspection versions remain explicit.
- The [single-pointing explorer](ui_report_browser.md#single-pointing-report-explorer)
  links spatial and frequency panels to the same saved comparison. It draws
  recorded position/beam evidence and LINE intervals or CONTINUUM frequency
  markers. It does not query sources or recompute scientific decisions.
- [Execution progress and storage](ui_offline_assessment.md) use process-local
  progress/index state and temporary disk artifacts. Measured counts describe
  individual stages. Reports have expiry, count and disk budgets; reads and
  downloads do not repeat assessment. This is not a persistent multi-user service.

## Known limits and scientific interpretation

The form executes supported fixed-target single-pointing and live Archive Mosaic
requests. Mosaic imports OT pointings and retains backend v2 reports with
per-context coverage, shared criteria and Member navigation. Member grouping does
not create a Member-wide scientific verdict. Captured Mosaic replay remains a CLI
workflow; live browser acceptance should cover source failures as well as matching cases.
Queue Mosaic and moving-target assessment remain unsupported. Sun is
selectable for validation/export; the shared backend has a no-source Solar
exemption, rather than a duplication assessment.

In the supported fixed SINGLE_POINTING workflow, TP is retained as provenance
but never supplies a position/beam diameter. Genuine 7m and 12m components remain
eligible when TP is present; mixed interferometric components are evaluated as
complete independent branches. Unexpected TP-only or conflicting array evidence
remains unresolved, never a successful non-duplication result. See the
[supervisor clarification](evidence/single_point_tp_exclusion_decision_2026-10-16.md),
[Archive array contract](archive_array_evidence.md) and
[Queue evidence rules](queue_common.md).

Continuum and LINE branches are reported independently. A matching SPW or pair
is not a whole-Member verdict. Missing evidence, failed sources, unsupported
scope and completed-empty retrieval are not “no duplication”. AUTO is bounded;
no search-wide absence claim is made. Display and plot limits do not reduce
retained-context evaluation.

Reviewed genuine proposal cases remain **0** in the recorded acceptance evidence.
Public-target self-retrieval and engineering examples do not supply independent
scientific labels. Queue freshness, source availability and runtime depend on
the configured data and service conditions.

## Verification register

These records describe different baselines and must not be merged into a single
“all verified on current main” claim. No tests or live queries were rerun for
this documentation-only sync.

| Verification | Recorded baseline / scope | Evidence |
| --- | --- | --- |
| Archive Mosaic regression | PR #178 development validation: 2683 passed, 12 skipped; final affected tests and Pyflakes checks passed | [Region contract](mosaic_s_region_position.md), [capture fixtures](../tests/fixtures/archive/s_region_acceptance_2026_10_26/README.md) |
| Archive Mosaic live and replay | 2026-10-26: 214 discovered candidates; selected four continuum and two line candidates, including an earlier no-auxiliary case; exact per-context replay parity | [Captured acceptance](../tests/fixtures/archive/s_region_acceptance_2026_10_26/README.md); engineering inputs, not independent proposal labels |
| Earlier recorded full regression | 2026-10-12 retrieval-first work: `a920761` plus the documented local changes; 1932 passed, 12 skipped | [Measurement and limits](evidence/tap_retrieval_first_2026-10-12.md) |
| Four browser workflows | Merged PR #134: live Archive and snapshot Queue, each CONTINUUM and LINE; self-retrieval, original downloads, AUTO provenance and timing | [Browser regression](evidence/browser_regression_pr134_2026-10-12.md) |
| Single-pointing visualization | PR #138 implementation: 271 UI tests; saved Archive LINE/CONTINUUM and synthetic Queue browser checks; no new source acquisition | [Explorer verification](ui_report_browser.md#single-pointing-report-explorer) |
| Deterministic scientific engineering acceptance | Pinned 15-case catalog and references; source/SPW isolation and incomplete-source cases | [Acceptance contract](acceptance_cases.md), [UI/CLI parity](ui_offline_assessment.md#offline-uicli-parity-gate) |

The [2026-10-13 browser-to-explorer acceptance](evidence/browser_explorer_acceptance_2026-10-13.md)
ran on merged PR #139 (`f3e15f5`): four newly entered Archive/Queue
CONTINUUM/LINE cases, plot-to-report operand checks and 271 UI tests passed.
The evidence records the fixed Queue snapshot, timings, lifecycle coverage and
one non-blocking Queue SPW-label clarification. It is engineering verification,
not independent supervisor scientific acceptance.

## Queue experimental boundary

The [processor experiment](experiments/queue_processor_consensus.md) is conditional
and does not establish native configuration enumeration or general formal mode
coverage. The separate [accepted adapter scope](queue_mode_adapter.md) supplies
bounded formal evidence. Historical experiment outputs and provisional methods
retain their original meaning.

## History and maintenance

[Previous status and delivery notes](history/delivery_notes.md) preserve the
prior PR-by-PR narrative and measurements. Dated evidence, historical report
versions and acceptance-reference hashes remain unchanged.

Update current capabilities here and remaining tasks in the roadmap. Link to
owning contracts instead of duplicating formula tables or version lists. Record
new verification with its actual baseline, input provenance and limitations;
never replace an older measurement with a newer test count.
