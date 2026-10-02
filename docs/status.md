# Current implementation status

Current merged implementation baseline: `610118cf2b216fcd56c00f484e325dbba5ed33cb` (PR #119).
This baseline includes the PR #117 Archive source-bound array evidence,
mixed-beam evaluation and TP D=12 POS-SINGLE follow-up, plus the explicit
browser live-source configuration/execution delivered in PR #119. PR #119 adds
no new scientific method or reviewed real-proposal scope; PR #117 retains its
historical scientific-method provenance.
This is the single capability summary;
[roadmap](roadmap.md) owns remaining order. Contracts define exact behavior and
[rule inputs](duplication_rule_inputs.md#7-scientific-decision-register) own approval scope.

| Capability | Archive | Queue |
| --- | --- | --- |
| Ingestion and association | Implemented TAP validation and coherent Source–SPW construction | Implemented CSV parsing, reconstruction and source snapshots |
| Candidate search | Implemented with explicit binding/completeness | Implemented with source-specific filters and conservative retention |
| Fixed single-point position | Approved within confirmed scope | [Versioned array/beam inference](queue_common.md): operational standalone priority, fixed band/AR fallback, complete 7-m/12-m variants for MIX |
| Angular comparison | Approved wrapper in confirmed scope | Opt-in queue_angular_factor_7 approved for coherent single-field row scope; legacy method stays provisional |
| Continuum branch | Five conditions and three-valued context branch implemented | [Opt-in row-level continuum](queue_continuum.md): five conditions and context branch; source-specific usable-union RMS |
| Line branch | Same-pair conditions, intermediate values and context-local aggregation implemented | [Same-row/SPW pairing and formal evaluation](queue_line_pairing.md) implemented for fixed single-field regular-SPW Queue contexts; FDM, coverage, resolution, RMS and whole-pair aggregation remain source-bound |
| Mode diagnostics | Association-bound operational em_xel interpretation for confirmed LINE scope; not universal telemetry | PR #75 census and PR #76 processor experiment delivered; those diagnostic artifacts alone confer no formal mode pass |
| Derived Queue mode evidence | Existing Archive method unchanged | [Adapter](queue_mode_adapter.md) returns scoped FDM/TDM/UNKNOWN and is integrated into Queue LINE-FDM; UNKNOWN supplies no formal pass |
| Acceptance | Formal same-request Archive+Queue continuum/LINE engineering acceptance, adversarial source/SPW isolation and source-state completeness matrix | Pinned numerical, real-capture engineering and failure/completeness cases; inspection v3 preserves distinct pair identities and the existing reason taxonomy without inventing a search-wide verdict |
| Reviewed real-proposal cases | 0; no genuine proposal input has been supplied | 0; no reviewed labels claimed |
| Shared application entry | [Implemented](assessment_entry.md): validation, Solar exemption, lazy sources, search/evaluation and report assembly | Explicit Queue method options; configuration preflight before source access |
| Browser UI | Proposed form validation, explicit Archive replay/live TAP assessment, run-specific reports and complete JSON / inspection v3 / request exports | Queue CSV assessment with explicit Queue options in the same flow; source failures and provenance remain visible |

Completed correctness fixes: PR #91 preserves shared LINE exact decision operands
([contract](line_precision.md)); PR #92 preserves inspection pair identities and
context-level common-condition counting ([contract](report_inspection.md)).
The shared assessment entry is implemented; PR #100 validates search-plan
configuration before source access, including conflicting beam strategies.
Current report version is 4, evaluation version is 5 and default inspection
version is 3. Explicit inspection v1/v2 reproduce historical behavior.

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

See the [diagnostic contract](queue_mode_census.md),
[processor experiment](experiments/queue_processor_consensus.md) and its
[dated measurement](evidence/queue_processor_consensus_2026-09-23.md).
The experiment uses conditional user-facing TPS mappings, not independent native
configuration enumeration. Its formal_mode is UNKNOWN, enumeration_complete is
false and scientific_closure is NOT_ESTABLISHED. A compatibility-view success
percentage does not approve a method or establish general single-field coverage.
The separate [project decision](evidence/queue_mode_evidence_decision_2026-09-23.md#accepted-scope)
now accepts a bounded mode adapter; it does not change those historical results.

The [Queue position method record](pos_single.md) retains its original execution-version
notes for provenance. Current orchestration/report versions belong to
[rules](rules.md) and [CLI/report](evaluation_cli.md).

## Browser increments after the pinned baseline

The [continuum setup declaration](continuum_setup_declaration.md) now permits
explicit researcher confirmation without detailed SPWs. Request model 3 / validator
7 and `continuum_setup_declaration_1` retain provenance and detect contradictory
complete lists; ordinary intent selection still does not establish qualification.

The proposed form supports validation/request download and an opt-in
[browser assessment flow](ui_offline_assessment.md). Each execution calls the
shared entry with explicit Queue intent options and explicit Archive `NONE` /
replay / live TAP configuration, then renders and exports its retained report v4
and inspection v3. Replay and live TAP are mutually exclusive; the live client is
lazy, failures do not fall back to replay, and live TAP does not imply live AQ
acquisition. Reports from separate runs remain independent.
The [offline UI/CLI parity gate](ui_offline_assessment.md#offline-uicli-parity-gate)
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

The [new decision](evidence/queue_array_beam_inference_decision_2026-10-01.md)
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
A separate [live browser Archive smoke](evidence/live_browser_archive_smoke_2026-10-02.md)
records a successful point-in-time production TAP and browser execution without
claiming scientific acceptance or future service availability.

Recorded local verification of that increment (2026-10-01): `1575 passed,
12 skipped`; all 15 offline acceptance catalog cases PASS; Ruff F and
`git diff --check` PASS. The existing Archive continuum replay was also compared
against the committed evaluator: report content was identical after excluding
`generated_at`. Browser review confirmed one MIX candidate with both diameter
sections. Skipped tests and live TAP were not claimed as passes.

## Archive array evidence review (PR #115, 2026-10-02)

Five [real array examples](evidence/archive_array_review_2026-10-02.md) now have
original TAP replays and source-bound official AQ labels. QA2 reports confirm
7-m science observations for two non-solar mixed-name cases, with captured EB
identities. This distinguishes documentary confirmation from the current
TAP-only formal diameter gate. Regression tests preserve pure-family D results,
mixed-list insufficient information and request-level Solar exemption.

The initial evidence review changed no parser or scientific method. Its dated
verification is retained in the review record.

## Archive source-bound array adapter (PR #115, 2026-10-02)

The optional [adapter](archive_array_evidence.md) now reads captured official AQ
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
