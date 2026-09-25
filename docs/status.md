# Current implementation status

Reviewed implementation baseline: `78ed45d` (PR #88 merged). This is the single capability summary;
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
| Mode diagnostics | Association-bound operational em_xel interpretation for confirmed LINE scope; not universal telemetry | PR #75 census and PR #76 processor experiment delivered; formal mode UNKNOWN |
| Derived Queue mode evidence | Existing Archive method unchanged | [Adapter](queue_mode_adapter.md) returns scoped FDM/TDM/UNKNOWN and is integrated into Queue LINE-FDM; UNKNOWN supplies no formal pass |
| Acceptance | Pinned numerical and real-capture engineering cases | Pairing/evaluator acceptance includes strict JSON, cross-SPW rejection, incomplete enumeration, Queue RMS normalization and full-suite regression |
| Reviewed real-proposal cases | No reviewed labels claimed by the delivered catalog | No reviewed labels claimed |
| Browser UI | Not implemented | Not implemented |
Validation on 2026-09-25: Queue LINE targeted tests 21 passed; integration 649 passed; full suite 1300 passed, 9 skipped; `compileall` and `git diff --check` succeeded.

Solar exemption is implemented at request level without accessing either source.
Continuum and LINE are reported independently. A supported candidate branch
result is not a search-wide absence verdict; top-level NOT_AGGREGATED remains
intentional. Missing evidence, source failures and unsupported scope are not
negative duplication results. Display limits do not limit retained-context evaluation.

The existing NGC6240 same-request Archive+Queue replay remains an engineering
acquisition/replay baseline whose historical command does not enable the later
formal Queue continuum/LINE options. Formal DUAL-SOURCE-ACCEPTANCE remains the
next delivery gate: it must exercise supported Archive and Queue formal branches
on the same request while preserving source failure, completeness and provenance
independently.

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
