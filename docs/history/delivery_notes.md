# Historical status and delivery notes

Archived on 2026-10-13 from the status and roadmap pages at PR #138.
These are snapshots of the previous documentation, including its stale baseline
and then-current next steps. Statements such as “now”, “current” and “next” below
belong to those historical notes; use [current status](../status.md) and the
[active roadmap](../roadmap.md) for present capabilities and priorities.

Dates, verification counts, scientific method versions and conclusions are
preserved. Relative links are adjusted for this history directory. No dated
scientific evidence, acceptance reference, fixture or catalog was changed.

## Former status page

# Current implementation status

Current merged implementation baseline: `1538c405c1604c08cfb54e6637155b7eb9223761` (PR #125).
PR #123 separates CAPTURED and LIVE catalog provenance while preserving captured
metadata and exact source binding. It introduces no runtime AQ acquisition.
This baseline includes the PR #117 Archive source-bound array evidence,
mixed-beam evaluation and TP D=12 POS-SINGLE follow-up, plus the explicit
browser live-source configuration/execution delivered in PR #119. PR #119 adds
no new scientific method or reviewed real-proposal scope; PR #117 retains its
historical scientific-method provenance.
The baseline also includes the independent LIVE-AQ-2 client in PR #124.
PR #125 includes LIVE-AQ-3 (`00923e1`) and LIVE-AQ-4 (`5090ae2`): post-TAP AQ
acquisition through the shared entry and explicit browser configuration.
This is the single capability summary;
[roadmap](../roadmap.md) owns remaining order. Contracts define exact behavior and
[rule inputs](../duplication_rule_inputs.md#7-scientific-decision-register) own approval scope.

| Capability | Archive | Queue |
| --- | --- | --- |
| Ingestion and association | Implemented TAP validation and coherent Source–SPW construction | Implemented CSV parsing, reconstruction and source snapshots |
| Candidate search | Implemented with explicit binding/completeness | Implemented with source-specific filters and conservative retention |
| Fixed single-point position | Approved within confirmed scope | [Versioned array/beam inference](../queue_common.md): operational standalone priority, fixed band/AR fallback, complete 7-m/12-m variants for MIX |
| Angular comparison | Approved wrapper in confirmed scope | Opt-in queue_angular_factor_7 approved for coherent single-field row scope; legacy method stays provisional |
| Continuum branch | Five conditions and three-valued context branch implemented | [Opt-in row-level continuum](../queue_continuum.md): five conditions and context branch; source-specific usable-union RMS |
| Line branch | Same-pair conditions, intermediate values and context-local aggregation implemented | [Same-row/SPW pairing and formal evaluation](../queue_line_pairing.md) implemented for fixed single-field regular-SPW Queue contexts; FDM, coverage, resolution, RMS and whole-pair aggregation remain source-bound |
| Mode diagnostics | Association-bound operational em_xel interpretation for confirmed LINE scope; not universal telemetry | PR #75 census and PR #76 processor experiment delivered; those diagnostic artifacts alone confer no formal mode pass |
| Derived Queue mode evidence | Existing Archive method unchanged | [Adapter](../queue_mode_adapter.md) returns scoped FDM/TDM/UNKNOWN and is integrated into Queue LINE-FDM; UNKNOWN supplies no formal pass |
| Acceptance | Formal same-request Archive+Queue continuum/LINE engineering acceptance, adversarial source/SPW isolation and source-state completeness matrix | Pinned numerical, real-capture engineering and failure/completeness cases; inspection v3 preserves distinct pair identities and the existing reason taxonomy without inventing a search-wide verdict |
| Reviewed real-proposal cases | 0; no genuine proposal input has been supplied | 0; no reviewed labels claimed |
| Shared application entry | [Implemented](../assessment_entry.md): validation, Solar exemption, lazy sources, search/evaluation and report assembly | Explicit Queue method options; configuration preflight before source access |
| Browser UI | Proposed form validation, explicit Archive replay/live TAP assessment, run-specific reports and complete JSON / inspection v3 / request exports | Queue CSV assessment with explicit Queue options in the same flow; source failures and provenance remain visible |

Completed correctness fixes: PR #91 preserves shared LINE exact decision operands
([contract](../line_precision.md)); PR #92 preserves inspection pair identities and
context-level common-condition counting ([contract](../report_inspection.md)).
The shared assessment entry is implemented; PR #100 validates search-plan
configuration before source access, including conflicting beam strategies.
The shared entry and CLI default to full report v4; new browser runs use
[matching-detail report v6](../matching_report.md). Evaluation version is 5 and
default inspection version is 3. Explicit inspection v1/v2 reproduce historical behavior.

Recorded pre-UI review on 2026-09-28 for `3f7f3156d450e5b6164053c34b17e873309989ef` (PR #100) (supplied local review,
not re-executed by this documentation-only change):

| Check | Recorded result and conditions |
| --- | --- |
| Full suite | 1405 passed, 9 skipped; Python 3.12.11 with a local Queue snapshot |
| Acceptance catalog | 15 cases PASS; `reviewed_real_proposal_cases=0` |
| Python tests CI | completed / success for the reviewed commit |
| Local Markdown paths | No missing paths reported; anchors and external links were not fully checked |
| Live TAP | Not run; skipped tests are not passes |

The supplied review locates acceptance output at
`/tmp/alma-pre-ui-review-3f7f315-20260928/summary.json`. This is a local review
artifact, not a checked-in file or a promise that another checkout contains it.
The review does not supply a snapshot digest; do not infer one from an older run.

Historical PR #92 verification: 1341 passed, 9 skipped with
`ALMA_QUEUE_CSV_SNAPSHOT`; inspection/acceptance targeted suite 41 passed,
Ruff F passed, acceptance 15 cases PASS, Live TAP not run. Its snapshot SHA-256
was `8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`,
and the retained local output was `reports/inspection-pair-identity-346402d/`.
These historical measurements and earlier counts describe their own code and
environment states, not the current baseline.


Solar exemption is implemented at request level without accessing either source.
Continuum and LINE are reported independently. A supported candidate branch
result is not a search-wide absence verdict; top-level NOT_AGGREGATED remains
intentional. Missing evidence, source failures and unsupported scope are not
negative duplication results. Display limits do not limit retained-context evaluation.

The existing NGC6240 same-request Archive+Queue replay remains an engineering
acquisition/replay baseline whose historical command does not enable the later
formal Queue continuum/LINE options. Formal dual-source engineering acceptance is
now delivered separately: supported Archive and Queue branches run against the
same request, source/SPW evidence remains isolated, and source failure,
incompleteness, completed-empty results and provenance remain distinct.

Independent review of a genuine proposal remains deferred because no genuine
proposal input has been supplied. That external validation gap does not create a
reviewed label and does not change the intentional absence of a search-wide
verdict.

## Queue experimental boundary

See the [diagnostic contract](../queue_mode_census.md),
[processor experiment](../experiments/queue_processor_consensus.md) and its
[dated measurement](../evidence/queue_processor_consensus_2026-09-23.md).
The experiment uses conditional user-facing TPS mappings, not independent native
configuration enumeration. Its formal_mode is UNKNOWN, enumeration_complete is
false and scientific_closure is NOT_ESTABLISHED. A compatibility-view success
percentage does not approve a method or establish general single-field coverage.
The separate [project decision](../evidence/queue_mode_evidence_decision_2026-09-23.md#accepted-scope)
now accepts a bounded mode adapter; it does not change those historical results.

The [Queue position method record](../pos_single.md) retains its original execution-version
notes for provenance. Current orchestration/report versions belong to
[rules](../rules.md) and [CLI/report](../evaluation_cli.md).

## Browser increments after the pinned baseline

The [continuum setup declaration](../continuum_setup_declaration.md) now permits
explicit researcher confirmation without detailed SPWs. Request model 3 / validator
7 and `continuum_setup_declaration_1` retain provenance and detect contradictory
complete lists; ordinary intent selection still does not establish qualification.

The proposed form supports validation/request download and an opt-in
[browser assessment flow](../ui_offline_assessment.md). Each execution calls the
shared entry with explicit Queue intent options and explicit Archive `NONE` /
replay / live TAP configuration, then renders and exports its retained report v4
and inspection v3. Replay and live TAP are mutually exclusive; the live client is
lazy, failures do not fall back to replay, and live TAP does not imply live AQ
acquisition. Reports from separate runs remain independent.
The [offline UI/CLI parity gate](../ui_offline_assessment.md#offline-uicli-parity-gate)
continues to compare complete reports and inspection documents with exact same-run
downloads. `tests/ui/test_live_source.py` separately covers live browser wiring
with real network access forbidden. Persistent multi-user storage remains
outstanding.

## Maintenance

Update affected contract behavior and this matrix when an implementation changes.
Keep measurement counts in dated evidence, versions in their owning contracts,
and remaining order in the roadmap. Historical reports retain original method
versions and approval states. No source-native mode or scientific approval may
be inferred merely from an implementation status.


## Queue beam inference delivered in PR #114 (2026-10-01)

The [new decision](../evidence/queue_array_beam_inference_decision_2026-10-01.md)
replaces the absent-column 12-m assumption with explicit D7/D12/MIX/unresolved
interpretations. MIX keeps both complete branch evaluations under one original
Queue candidate. Position method is now `queue_pos_single_6`; OR method is
`queue_beam_variant_or_1`. Report v4 adds optional nested beam evidence, consumed
by inspection v3 and the report browser. Observation-scope UI edits were
delivered in the same PR. Explicit live-source configuration and execution
feedback are now delivered as a subsequent browser increment; no new scientific
real-proposal review is claimed.

Recorded browser live-source verification on 2026-10-02: `13 passed` in
`tests/ui/test_live_source.py`, `102 passed` in `tests/ui`; Ruff F and
`git diff --check` PASS. Those regression tests forbid real network access.
A separate [live browser Archive smoke](../evidence/live_browser_archive_smoke_2026-10-02.md)
records a successful point-in-time production TAP and browser execution without
claiming scientific acceptance or future service availability.

Recorded local verification of that increment (2026-10-01): `1575 passed,
12 skipped`; all 15 offline acceptance catalog cases PASS; Ruff F and
`git diff --check` PASS. The existing Archive continuum replay was also compared
against the committed evaluator: report content was identical after excluding
`generated_at`. Browser review confirmed one MIX candidate with both diameter
sections. Skipped tests and live TAP were not claimed as passes.

## Archive array evidence review (PR #115, 2026-10-02)

Five [real array examples](../evidence/archive_array_review_2026-10-02.md) now have
original TAP replays and source-bound official AQ labels. QA2 reports confirm
7-m science observations for two non-solar mixed-name cases, with captured EB
identities. This distinguishes documentary confirmation from the current
TAP-only formal diameter gate. Regression tests preserve pure-family D results,
mixed-list insufficient information and request-level Solar exemption.

The initial evidence review changed no parser or scientific method. Its dated
verification is retained in the review record.

## Archive source-bound array adapter (PR #115, 2026-10-02)

The optional [adapter](../archive_array_evidence.md) now reads captured official AQ
source labels, requiring exact Member/source identity and capture integrity.
`archive_source_array_1`, `archive_pos_single_2` and
`archive_beam_variant_or_1` implement the project-adopted source binding, diameter
selection and complete-branch OR. Missing/conflicting bindings remain UNKNOWN;
there is no raw-name fallback under the new profile. TP is physically 12 m while
its scientific applicability remains unsupported. Legacy evaluation is unchanged
when the catalog is absent. CLI, shared entry and offline browser can supply the
catalog; report v4 and inspection v3 preserve its provenance and beam alternatives.
No automatic live AQ lookup or new reviewed real-proposal label is claimed.

Local verification on 2026-10-02: 1609 passed, 12 skipped; Ruff F passed.
The full suite includes the existing offline acceptance and UI export checks.
Skipped live/snapshot tests are not passes. Original captured evidence bytes and
historical acceptance labels remain unchanged.

## Archive TP D=12 position follow-up (PR #117, 2026-10-02)

The supervisor-confirmed TP position decision is implemented narrowly in the
source-bound Archive path. A bound `TP` component retains `TOTAL_POWER` identity
and uses physical `D = 12 m` for the existing POS-SINGLE half-power-beam
calculation, producing an evaluated geometric outcome when the other position
evidence is complete. The source-bound position method is
`archive_pos_single_3`; historical `archive_pos_single_2` reports retain their
original meaning.

Broader TP CONTINUUM/LINE applicability is unchanged in this increment and
remains INDETERMINATE rather than inheriting main-array 12-m semantics.

## Independent live AQ client (2026-10-04, PR #124)

[LIVE-AQ-2](../archive_aq_client.md) implements explicit Member acquisition,
complete-response validation, LIVE catalogs and per-query provenance, including
zero-hit queries. Failed acquisition returns no partial catalog. Offline tests
cover HTTP failures, discovery restrictions and source preservation. At PR #124
delivery, assessment/CLI/browser wiring was not implemented; scientific methods
and the existing captured evidence loader were unchanged.

Local verification on 2026-10-04: new fake-HTTP client tests `57 passed`;
full suite `1684 passed, 12 skipped`; Ruff F, `git diff --check` and affected
document relative paths passed. The client tests include unchanged official
response bytes replayed through fake HTTP. No live AQ request was made for this
verification; skipped tests are not passes.

## Post-TAP AQ assessment wiring (2026-10-05, PR #125)

[LIVE-AQ-3](../live_aq_assessment.md) adds an explicit lazy fetcher to the shared
entry. All retained linked Archive Members participate independently of display
limits. Failed/incomplete acquisition retains TAP candidates with unresolved
array evidence, never legacy TAP-array fallback, and does not change Queue
evaluation. Successful zero-hit queries, skips and acquisition failures are
distinct in report v4; inspection v3 exposes acquisition failures. No browser
control, CLI switch, scientific method or source-binding change is introduced.

Local verification on 2026-10-05: 25 new offline integration tests; focused
assessment/array regressions `63 passed`; full suite `1709 passed, 12 skipped`.
Ruff F and `git diff --check` passed. Tests use fake TAP/HTTP and retain existing
offline acceptance coverage. No live-service or real-proposal acceptance is
claimed; skipped tests are not passes.

## Explicit browser live AQ (2026-10-05, PR #125)

[LIVE-AQ-4](../ui_offline_assessment.md#explicit-live-aq-configuration) adds the
operator flag `ALMA_UI_LIVE_ARCHIVE_AQ`, requiring live TAP and excluding captured
AQ. A lazy callback creates the client only when the shared entry needs linked
Members after TAP. Report pages display stored AQ states and query provenance,
including zero hits, skips and failures. Refresh/downloads do not acquire sources;
separate executions retain independent results. No scientific rule, HTTP client
contract, report version or inspection version changes.

Local verification on 2026-10-05: 33 new offline browser tests; full suite
`1742 passed, 12 skipped`. Ruff F and `git diff --check` passed. Fake TAP/HTTP
tests cover lazy acquisition, configuration conflicts, stored report provenance,
shared-entry parity, immutable downloads and run isolation. The local browser
preview used a synthetic failed-AQ report. No live-service or real-proposal
acceptance is claimed; skipped tests are not passes.

## Live browser TAP and AQ verification (2026-10-05)

A [real-service browser smoke](../evidence/live_browser_aq_smoke_2026-10-05.md)
completed on the merged baseline: 4 retained/evaluated TAP contexts, one AQ
Member query and 4 returned source records. Exact target bindings supplied 7-m
array evidence to POS-SINGLE. Browser downloads were verified, including identical
report bytes after refresh and no additional observed source HTTP requests.
This one continuum engineering request does not establish reviewed scientific
acceptance, exhaustive search coverage or live LINE/Queue verification.

A subsequent [live LINE browser smoke](../evidence/live_browser_line_aq_smoke_2026-10-05.md)
completed with the same 4 candidate contexts: SPW 28 met the synthetic LINE
requirements and the other three SPWs did not. Exact source-bound 7-m evidence,
per-pair criteria, request/inspection exports and repeated report bytes were
verified. Neither live run establishes reviewed real-proposal acceptance or
exhaustive search coverage. No production code changed during these checks.

## Report presentation and AUTO retrieval (2026-10-05)

The report viewer now leads with independent branch counts, target/source/SPW
identities and readable comparison values. Technical evidence is expandable;
display rounding does not change stored operands or decisions. LINE RMS displays
the backend's comparable sensitivity where available. Legacy reports remain
readable and their downloads preserve original bytes.

[Automatic retrieval](../automatic_retrieval.md) is the browser default. Validator
8 and plan 4 resolve the versioned 7-m/35-GHz Archive centre envelope; Queue uses
all supplied rows before optional explicit scalar filters. Old explicit-radius
requests retain their selection semantics. The policy and limits are stored in
report v4. Overflow/incomplete source handling remains explicit, with no reduced
radius retry. Scientific position methods and inspection v3 are unchanged.

Verification: full suite `1773 passed, 12 skipped`; offline acceptance `15/15 PASS`;
Ruff F and diff whitespace checks passed. Browser interaction confirmed AUTO
validation without radius entry, separate missing-science diagnostics and saved
LINE report rendering. Desktop and 390-pixel report layouts were inspected; the
narrow page has no document-wide horizontal overflow (tables scroll locally).
AUTO acquisition tests use fake TAP/AQ; no live AUTO completeness or independent
real-proposal scientific acceptance is claimed.

## Proposed frequency input closure

[Shared REST/SKY preparation](../proposed_frequency.md) now serves LINE and both
Archive/Queue CONT-FREQ paths. Continuum accepts REST + explicit redshift; the
browser exposes one shared redshift and reports retain the conversion operands.
This adds engineering regression coverage, not a new live scientific acceptance case.

## Former roadmap page

# Engineering delivery roadmap

The reviewed implementation baseline and current verification conditions are
maintained in [status](../status.md).
Archive and supported Queue continuum/LINE dual-source engineering acceptance is
delivered in the supported fixed single-field scope. No independently reviewed
real-proposal case is claimed.
This is the sole owner of remaining engineering order and exit gates.
[Status](../status.md) owns the capability matrix; [rule inputs](../duplication_rule_inputs.md)
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
implemented (PR #100). The thin browser interface, offline UI/CLI parity gate
and explicit live-source configuration/execution feedback are delivered.

| Commit | Scope | Exit gate |
| --- | --- | --- |
| DOC-BASE — delivered in PR #93 | Align architecture, current status, interface versions and this order | Current vs historical state is explicit; relative links resolve; no runtime change or new test required |
| LINE-HELPERS — delivered | Extract shared rational display and explicit unit conversion into numerical helpers, criterion truth into aggregation | First verify equivalent behavior; boundary tests and acceptance retain numbers, reasons, methods and outcomes; keep source-specific result/evidence/RMS implementations |
| GEOMETRY — delivered (3A) | Extract pure separation and beam formulas | Preserve spherical/offset/placeholder and boundary behavior; keep legacy boundary conventions in strategies; do not claim all cycles removed yet |
| SPATIAL-EVIDENCE — delivered (3B) | Separate spatial evidence adaptation from strategy dispatch | Queue strategy depends on adaptation rather than dispatch; remove target reverse imports; preserve retention, formal POS and explicit legacy paths, with compatibility exports where needed |
| MODE-REFERENCE — delivered | Separate reference configurations/mappings from experiment report generation | Formal adapter no longer consumes experiment report dictionaries; configuration IDs, matches, N16 allowance, mode results and historical CLIs unchanged |
| APP-ENTRY — backend entry delivered | Shared application orchestration used by CLI and directly callable by frontends | Offline direct-call/CLI report agreement delivered here; browser integration and parity are now delivered separately |

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
hashes intact; retain the recorded baseline described in [status](../status.md).

## Current browser increment

Explicit researcher confirmation of continuum setup qualification is implemented
as a [separate evidence route](../continuum_setup_declaration.md), including backend
conflict handling and CLI/browser scientific-result parity for the new path.

The [browser form-to-report flow](../ui_offline_assessment.md) is implemented:
current input, explicit Queue methods, shared assessment entry, independent run
identity, original report/inspection downloads and explicit Archive replay/live
TAP configuration. The
[offline UI/CLI parity gate](../ui_offline_assessment.md#offline-uicli-parity-gate)
remains the deterministic parity gate; live browser wiring has separate no-network
regressions for configuration, laziness and provenance boundaries. The local
in-memory lifecycle is not a multi-user service.

## Remaining delivery order

| Increment | Work | Exit gate |
| --- | --- | --- |
| QUEUE-COMMON — coherent single-field row scope delivered | Scoped single-point position and angular-resolution evidence | Supported geometry/frame/array interpretation, boundaries and missing/conflict behavior explicit; independent numerical cases and method status recorded |
| QUEUE-CONTINUUM — coherent single-field row scope delivered | Queue frequency/RMS mappings and independent continuum branch | Same-context/setup evidence, positive/negative/boundary/unknown cases; source-specific sensitivity semantics; no FDM/TDM prerequisite |
| QUEUE-LINE — fixed single-field regular-SPW scope delivered | Mode applicability, coherent same-window coverage/resolution/RMS and pair reports | Supported configuration/profile evidence; no cross-SPW borrowing; coarse-resolution blocking; independent intermediate-value and pair aggregation acceptance |
| Thin browser interface — delivered | Input, candidates, independent branches, pair evidence and export using the backend report | UI/CLI agreement, no duplicate formulas, no UNKNOWN/empty-source-to-negative conversion |
| LIVE-SOURCE — delivered | Explicit live-source configuration and execution feedback through the shared application entry | Live versus replay configuration is explicit; source failures/provenance remain visible; no implicit fallback, live AQ acquisition or new scientific scope |
| Broader modes — deferred | Mosaic, moving targets, TP scientific evaluation, mixed setups and broader conversions | Separate scope, evidence and acceptance decisions |

The [first Queue common increment](../queue_common.md) supplies opt-in coherent
single-field row-beam position, including the supported 7 m/12 m
`standAlone_ACA` interpretation, and separately scoped angular criteria. [Queue continuum](../queue_continuum.md)
and [Queue LINE](../queue_line_pairing.md) now complete the supported fixed
single-field branches. Formal same-request Archive+Queue continuum/LINE
acceptance, cross-source/SPW isolation and source-state completeness are also
delivered. The bounded preparatory increments, thin browser interface and
explicit live-source execution are complete. Persistent multi-user lifecycle and
broader component-specific or mixed-array interpretations remain separate
extensions.

Independent review of an actual proposal remains an external validation gate.
No genuine proposal input is currently available, so
`reviewed_real_proposal_cases` remains zero. Do not synthesize or relabel a case
to satisfy that gate.

These are engineering increment IDs, not scientific Q1–Q8 question IDs. The
[mapping table](../queue_single_point_mapping.md) owns detailed fields, units,
associations and evidence gaps; this table owns order and exit gates only.

Queue mode work must resolve applicability and alternative interpretations within
the supported scope. Exact processor identity is required only where the method
needs it; exact configuration uniqueness is not the same as mode consensus.
The [mode evidence adapter](../queue_mode_adapter.md) supplies source-bound
exact-first classification and the reviewed N16 allowance to formal Queue LINE.
Geometry/array applicability remains independently scoped, and broader array or
mode interpretation remains a separate extension.
The 76 export signatures and 14 all-family TP mapping gaps are tracked in the
[dated experiment results](../evidence/queue_processor_consensus_2026-09-23.md).
Do not make all-family experimental closure a blanket prerequisite for Queue continuum.

## Thin UI delivery increments

The [Archive array evidence review](../evidence/archive_array_review_2026-10-02.md)
added five real replay examples before live browser integration. The optional
[source-bound adapter](../archive_array_evidence.md) now consumes captured official
AQ labels, confirming the two 7-m science targets and evaluating complete D7/D12
alternatives for explicitly mixed labels. TP retains its 12-m physical aperture;
POS-SINGLE is evaluated with D=12 m, while broader CONTINUUM/LINE scientific
applicability remains unresolved. The independent
[LIVE-AQ-2 HTTP client](../archive_aq_client.md) is delivered in PR #124.
[LIVE-AQ-3](../live_aq_assessment.md) now connects retained TAP Members to acquisition,
structured failure handling and report/inspection provenance in PR #125.
LIVE-AQ-4 adds explicit operator configuration and report state display in the
same PR, with offline lifecycle and parity tests. A bounded live TAP+AQ browser
continuum smoke is [recorded](../evidence/live_browser_aq_smoke_2026-10-05.md).
A [scoped live LINE request](../evidence/live_browser_line_aq_smoke_2026-10-05.md)
also completed. Report summaries, candidate identities and comparison displays are implemented.
The browser now defaults to the bounded [AUTO retrieval policy](../automatic_retrieval.md).
Next, run a separate live AUTO smoke and review retrieval completeness and
report usability on representative public targets.
Independent real-proposal acceptance remains separate. Capture freshness and
component-specific product evidence remain separate work. Live
execution must continue to show unresolved candidates explicitly.

1. Report display and export — implemented as a [read-only viewer](../ui_report_browser.md): consume existing acceptance reports; show each
   source status, independent continuum/LINE branches and context/window/SPW
   evidence. Export the same complete report, optionally with inspection v3.
2. Minimal form — validation and offline execution implemented at `/proposed`:
   one fixed single-point setup, multiple windows, both intents and explicit units.
   Configured Archive replay and Queue CSV providers call the shared entry with
   explicit AssessmentOptions. Missing/invalid input, execution errors and usable
   partial-source reports remain distinct. Solar is supported by the execution
   adapter and report viewer. The form now exposes target type and geometry with
   support notices and server-side execution guards. Moving/Mosaic and Sun
   selections support validation/export only; dedicated scientific inputs and
   broader execution remain separate increments.
3. Browser/CLI agreement — implemented in `tests/ui/test_cli_parity.py`: catalog
   inputs cover mixed intents, missing RMS, coarse resolution, multiple pairs and
   source failure/missing/empty results. Additional cases cover declarations,
   conflicting evidence, equivalent units, pagination/display truncation and the
   Solar adapter/viewer boundary. Same-run downloads preserve original bytes.
   Separate runs compare complete reports and inspection v3. Only four execution
   timestamps are normalized; the CLI input-file hash and absent form-file hash
   are separately asserted. See the [gate contract](../ui_offline_assessment.md#offline-uicli-parity-gate)
   for configuration and provenance boundaries.
4. Explicit live Archive source — implemented in `tests/ui/test_live_source.py`
   and `ui/runs.py`: `ALMA_UI_LIVE_ARCHIVE` selects live TAP, mutually exclusive
   with Archive replay. Client construction stays lazy and source-selected; failed
   live execution does not fall back to replay. Captured AQ array evidence remains
   a separate configured artifact and is never auto-refreshed by live TAP. The
   regression suite forbids real network access, so service availability is not a
   delivery claim.

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
