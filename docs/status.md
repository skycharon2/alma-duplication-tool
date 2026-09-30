# Current implementation status

Reviewed implementation baseline: `3f7f3156d450e5b6164053c34b17e873309989ef` (PR #100, 2026-09-28). This is the single capability summary;
[roadmap](roadmap.md) owns remaining order. Contracts define exact behavior and
[rule inputs](duplication_rule_inputs.md#7-scientific-decision-register) own approval scope.

| Capability | Archive | Queue |
| --- | --- | --- |
| Ingestion and association | Implemented TAP validation and coherent Source–SPW construction | Implemented CSV parsing, reconstruction and source snapshots |
| Candidate search | Implemented with explicit binding/completeness | Implemented with source-specific filters and conservative retention |
| Fixed single-point position | Approved within confirmed scope | [Opt-in Portal row-beam method](queue_common.md): standalone True/False or explicit missing-column assumption; requested components separate |
| Angular comparison | Approved wrapper in confirmed scope | Opt-in queue_angular_factor_7 approved for coherent single-field row scope; legacy method stays provisional |
| Continuum branch | Five conditions and three-valued context branch implemented | [Opt-in row-level continuum](queue_continuum.md): five conditions and context branch; source-specific usable-union RMS |
| Line branch | Same-pair conditions, intermediate values and context-local aggregation implemented | [Same-row/SPW pairing and formal evaluation](queue_line_pairing.md) implemented for fixed single-field regular-SPW Queue contexts; FDM, coverage, resolution, RMS and whole-pair aggregation remain source-bound |
| Mode diagnostics | Association-bound operational em_xel interpretation for confirmed LINE scope; not universal telemetry | PR #75 census and PR #76 processor experiment delivered; those diagnostic artifacts alone confer no formal mode pass |
| Derived Queue mode evidence | Existing Archive method unchanged | [Adapter](queue_mode_adapter.md) returns scoped FDM/TDM/UNKNOWN and is integrated into Queue LINE-FDM; UNKNOWN supplies no formal pass |
| Acceptance | Formal same-request Archive+Queue continuum/LINE engineering acceptance, adversarial source/SPW isolation and source-state completeness matrix | Pinned numerical, real-capture engineering and failure/completeness cases; inspection v3 preserves distinct pair identities and the existing reason taxonomy without inventing a search-wide verdict |
| Reviewed real-proposal cases | 0; no genuine proposal input has been supplied | 0; no reviewed labels claimed |
| Shared application entry | [Implemented](assessment_entry.md): validation, Solar exemption, lazy sources, search/evaluation and report assembly | Explicit Queue method options; configuration preflight before source access |
| Browser UI | Read-only backend report display and original JSON / inspection v3 exports; proposed form validation and request export | Same viewer and validator; live form assessment not connected |

Completed correctness fixes: PR #91 preserves shared LINE exact decision operands
([contract](line_precision.md)); PR #92 preserves inspection pair identities and
context-level common-condition counting ([contract](report_inspection.md)).
The shared assessment entry is implemented; PR #100 validates search-plan
configuration before source access, including conflicting beam strategies.
Current report version is 4, evaluation version is 5 and default inspection
version is 3. Explicit inspection v1/v2 reproduce historical behavior.

Recorded pre-UI review on 2026-09-28 for this baseline (supplied local review,
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

## Maintenance

Update affected contract behavior and this matrix when an implementation changes.
Keep measurement counts in dated evidence, versions in their owning contracts,
and remaining order in the roadmap. Historical reports retain original method
versions and approval states. No source-native mode or scientific approval may
be inferred merely from an implementation status.
