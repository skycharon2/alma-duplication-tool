# Queue single-point rule evidence mapping

Status at PR #76: implementation-planning contract, not a new scientific method
or approval record. The [Queue CSV contract](queue_csv_contract.md) owns parsing
and units. [Status](status.md) owns capabilities; [roadmap](roadmap.md) owns order.
Existing source associations must be reused; no new values are inferred here.

## Association invariant

Retain snapshot/source identity, physical row identity, existing Queue association
and SPW slot. An analytical group is not permission to combine rows or pair each
source with every setup. Setup-level quantities require an explicit supported
setup interpretation. Row-level requested sensitivity is not automatically a
separate measurement for every SPW. Preserve raw tokens and derived provenance.

## Rule mapping

| Rule | CSV evidence and units/meaning | Required association | Current implementation | Missing/conflict behavior and remaining evidence | Acceptance |
| --- | --- | --- | --- | --- | --- |
| POS-SINGLE | RA/Dec, coordinate system, offsets and geometry; Ref.Frequency GHz; Use 7-m?/Use TP? array requirements | Same row and candidate-beam derivation | [Opt-in queue_pos_single_3](queue_common.md) for supported single arrays; legacy profile/v1 remains provisional | Unknown centre/frame/diameter/unsupported geometry stays unresolved. Zero-reference beam fallback is geometry-only; array flags do not identify processor. Version 3 uses inclusive comparison; version 1/search keeps its guard. Explicit row-bound 7M_ONLY/TP_ONLY declarations are supported; mixed remains deferred. | Existing [beam tests](../tests/integration/test_queue_candidate_beam.py) and [position tests](../tests/integration/test_position_single.py); remaining formal single-point positive/negative/boundary and candidate-side missing-basis cases |
| ANGULAR | Req. Ang. Res., arcsec, requested resolution expected upon completion | Same Queue row/context | Opt-in queue_angular_factor_4 reuses exact factor-two comparison in the adopted single-array common scope | Missing/conflicting candidate/request values block this condition. Retain requested versus Archive estimated semantics; define supported source interpretation. | Existing [angular tests](../tests/integration/test_rules_angular.py); remaining Queue approved-method and independent boundary cases |
| CONT-SETUP | Proposed request windows, not a candidate CSV substitute | Distinct proposed window IDs and setup completeness | Approved direct usable-width qualification exists; nominal conversion remains provisional | Continuum intent alone does not qualify bandwidth. Unknown widths/completeness cannot be silently filled from candidate CSV. | Existing [continuum tests](../tests/integration/test_confirmed_continuum.py) and [width tests](../tests/unit/test_rules_continuum_setup.py); preserve these as request-side regressions |
| CONT-FREQ | Ref.Frequency GHz is the requested-sensitivity reference; Freq SPW N GHz, Is Sky Freq?, velocity/frame/convention are separate evidence | Explicit candidate setup/frequency role from coherent row | Queue scientific comparison mapping not implemented | Do not reuse a beam weighted-frequency fallback automatically. Specify representative frequency, reference compatibility and zero sentinel behavior. No FDM/TDM dependency. | Remaining independent frequency-ratio boundary, zero reference, frame and role-conflict cases |
| CONT-RMS | Req.Sensitivity mJy, Ref.Frequency GHz, Ref.Freq.Width MHz; requested rather than achieved/Archive estimated sensitivity | Declared setup scope and sensitivity basis | Queue scientific RMS mapping not implemented | Do not append /beam or assume aggregate RMS. Establish beam/basis, reference width, contributing windows and conversion applicability. Missing candidate basis is not another user-input requirement. | Remaining direct/converted basis, deeper/equal/worse, overlap and missing-association cases |
| LINE-FDM | Cycle from project code; Polarization; Bandwidth SPW N MHz; Spec.Res. SPW N MHz; requested-array view also uses Use TP? | Exact raw row/SPW with catalog, profile and method versions | [Typed mode adapter](queue_mode_adapter.md) delivered; formal LINE-FDM integration pending | Missing or mixed interpretations stay UNKNOWN. Same-mode configuration ambiguity need not block consensus. Close supported configuration-space/profile applicability; unique processor ID only where needed. | Existing [v1 tests](../tests/unit/test_queue_mode.py), [processor tests](../tests/test_queue_processor_mode.py), [report tests](../tests/integration/test_queue_processor_census.py); [adapter regressions](../tests/unit/test_queue_mode_adapter.py) and [pinned acceptance](../tests/acceptance/test_queue_mode_adapter_snapshot.py); remaining formal LINE integration |
| LINE-COVERAGE | Freq SPW N GHz, Bandwidth SPW N MHz, sky/rest and velocity evidence; nominal versus usable coverage distinct | Same candidate slot as mode, resolution and RMS evidence | Normalized ingestion intervals exist; formal Queue line rule not implemented | Unknown frame/usable-width applicability blocks formal coverage. Do not use a TPS counterpart's fourfold bandwidth as original Queue coverage. No SPS-to-SPW invention. | Existing ingestion/profile normalization regressions; remaining centre endpoints, rest/sky conflict and crossed-SPW rejection |
| LINE-RESOLUTION-COMPATIBILITY | Spec.Res. SPW N MHz is spectral resolution; planned window resolution comes from request | Same proposed-window/candidate-SPW pair | Request preparation exists; Queue numerical rule not implemented | Establish comparison frequency/frame and supported smoothing interpretation. Resolution is not channel spacing or effective noise bandwidth. | Remaining equal/finer/coarser candidate, reference-frequency ambiguity and same-pair tests |
| LINE-RMS | Req.Sensitivity mJy, Ref.Frequency GHz and Ref.Freq.Width MHz; no per-SPW @10km/s Archive RMS field | Explicit sensitivity-to-window binding, same pair as resolution/coverage | Queue numerical rule not implemented | The [2026-09-24 decision](evidence/queue_common_decision_2026-09-24.md#common-rules) adopts shared line angular correction; do not copy Archive's @10km/s starting basis. Queue RMS implementation remains pending. Establish normalization/basis applicability first; incompatible resolution must block unsupported RMS calculation. | Remaining independent intermediate values, blocked calculations, incomplete evidence and cross-SPW borrowing cases |

## Tests versus scientific acceptance

The linked files test existing behavior only. A row marked "remaining" is not a
claim that a matching acceptance case already exists. In particular, existing
profile UNKNOWN tests do not by themselves close the historical IN-08 scenario
or approve its source interpretation. A future adapter must preserve branch-local
three-valued results, source completeness and unsupported-scope reasons.

No Queue continuum rule needs a line-mode classifier merely to begin development.
Likewise, resolving mode alone does not establish Queue RMS, frequency, position
or branch completeness. The experiment's 76 export cases and 14 all-family mapping
gaps remain explicitly scoped; see the [measurement](evidence/queue_processor_consensus_2026-09-23.md).
