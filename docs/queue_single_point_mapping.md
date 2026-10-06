# Queue single-point rule evidence mapping

Blank Mosaic with nonzero offsets now has an explicit [formal pointing interpretation](queue_blank_mosaic.md), with scoped position v7/angular v8 method identities. The underlying parser and historical records are unchanged.

Current mapping includes the scoped Queue continuum and fixed single-field regular-SPW Queue LINE increments. This is a
contract index, not a new scientific approval record. The [Queue CSV contract](queue_csv_contract.md) owns parsing
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
| POS-SINGLE | RA/Dec, coordinate system, offsets and geometry; Ref.Frequency GHz; Use 7-m?/Use TP? array requirements | Same row and candidate-beam derivation | [Opt-in queue_pos_single_6](queue_common.md) with Portal row-beam interpretation; legacy profile/v1 remains provisional | Unknown centre/frame/diameter/unsupported geometry stays unresolved. Zero-reference beam fallback is geometry-only; array flags do not identify processor. Version 6 uses operational standalone priority, auxiliary flags and fixed band/AR inference for absent columns; MIX evaluates complete 7-m and 12-m variants with OR aggregation. Auxiliary flags no longer block row position; row-level continuum uses the same observation interpretation. | [Common-rule tests](../tests/integration/test_queue_common.py) cover inside/outside, inclusive boundary and missing beam evidence; [row-beam tests](../tests/integration/test_queue_row_beam.py) cover standalone flags, absent/invalid columns and scope blockers. Legacy beam/position tests remain regressions |
| ANGULAR | Req. Ang. Res., arcsec, requested resolution expected upon completion | Same Queue row/context | Opt-in queue_angular_factor_7 reuses exact factor-two comparison in the adopted coherent row scope | Missing/conflicting candidate/request values block this condition. Retain requested versus Archive estimated semantics; define supported source interpretation. | [Common-rule tests](../tests/integration/test_queue_common.py) cover approved Queue angular results, symmetric exact limits and missing proposed angular evidence; [angular tests](../tests/integration/test_rules_angular.py) retain generic regressions |
| CONT-SETUP | Proposed request windows, not a candidate CSV substitute | Distinct proposed window IDs and setup completeness | Approved direct usable-width qualification exists; nominal conversion remains provisional | Continuum intent alone does not qualify bandwidth. Unknown widths/completeness cannot be silently filled from candidate CSV. | Existing [continuum tests](../tests/integration/test_confirmed_continuum.py) and [width tests](../tests/unit/test_rules_continuum_setup.py); preserve these as request-side regressions |
| CONT-FREQ | Ref.Frequency GHz is the requested-sensitivity reference; Freq SPW N GHz, Is Sky Freq?, velocity/frame/convention are separate evidence | Explicit candidate setup/frequency role from coherent row | [queue_cont_freq_2](queue_continuum.md): positive reference SKY frequency, inclusive symmetric factor 1.3 | Do not reuse a beam weighted-frequency fallback automatically. The adopted contract specifies representative frequency and zero sentinel behavior. No FDM/TDM dependency. | [Continuum regressions](../tests/integration/test_queue_continuum.py): ratio boundary, zero reference and unsupported scope |
| CONT-RMS | Req.Sensitivity mJy, Ref.Frequency GHz, Ref.Freq.Width MHz; requested rather than achieved/Archive estimated sensitivity | Declared setup scope and sensitivity basis | [queue_cont_rms_portal_2](queue_continuum.md): same-row usable-union conversion, single-field row scope | Do not append /beam or assume aggregate RMS. The project decision adopts the limited requested RMS/reference-width interpretation and records contributing SPWs. Missing candidate basis is not another user-input requirement. | [Continuum regressions](../tests/integration/test_queue_continuum.py): width conversion, deeper/equal/worse, overlap, unknown and context isolation |
| LINE-FDM | Cycle from project code; Polarization; Bandwidth SPW N MHz; Spec.Res. SPW N MHz; requested-array view also uses Use TP? | Exact raw row/SPW with catalog, profile and method versions | [Typed mode adapter](queue_mode_adapter.md) is integrated into formal Queue LINE as `queue_line_fdm_1` | Missing or mixed interpretations stay UNKNOWN. Same-mode configuration ambiguity need not block consensus. Supported profile/configuration applicability remains source-bound; unique processor identity is required only where the adopted method needs it. | Existing mode/adapter tests plus [formal Queue LINE evaluator regressions](../tests/integration/test_queue_line_evaluation.py); same-pair aggregation prevents mode evidence from being borrowed across SPWs |
| LINE-COVERAGE | Freq SPW N GHz, Bandwidth SPW N MHz, sky/rest and velocity evidence; nominal versus usable coverage distinct | Same candidate slot as mode, resolution and RMS evidence | `queue_line_coverage_2` evaluates the prepared proposed SKY centre against the same SPW's versioned usable interval with inclusive endpoints | Unknown frame or unavailable usable-width evidence blocks formal coverage. Do not use a TPS counterpart's fourfold bandwidth as original Queue coverage. No SPS-to-SPW invention and no cross-SPW borrowing. | Existing ingestion/pairing regressions plus [formal Queue LINE evaluator regressions](../tests/integration/test_queue_line_evaluation.py); retain explicit endpoint and malformed-evidence boundary coverage as acceptance requirements |
| LINE-RESOLUTION-COMPATIBILITY | Spec.Res. SPW N MHz is spectral resolution; planned window resolution comes from request | Same proposed-window/candidate-SPW pair | `queue_line_resolution_compatibility_2` is implemented; Queue `Spec.Res.` must be equal or finer than the proposed common spectral width | Resolution remains distinct from channel spacing and effective noise bandwidth. Missing required evidence stays unresolved; a coarser Queue resolution is a definite incompatibility and blocks the dependent RMS calculation. | [Formal Queue LINE evaluator regressions](../tests/integration/test_queue_line_evaluation.py) preserve same-pair resolution binding; [precision regressions](../tests/integration/test_line_precision.py) cover equal/finer/coarser resolution boundaries |
| LINE-RMS | Req.Sensitivity mJy, Ref.Frequency GHz and Ref.Freq.Width MHz; no per-SPW @10km/s Archive RMS field | Explicit same-row sensitivity basis and the same proposed-window/candidate-SPW pair as resolution/coverage | `queue_line_rms_portal_2` is implemented: `Req.Sensitivity @ Ref.Freq.Width` is normalized to the proposed spectral width, then the shared line angular correction is applied before the one-sided factor-two comparison | The adopted Queue method does not copy Archive's @10km/s starting basis. Portal-helper per-SPW scaling and its Tsys limitation remain explicit provenance. Missing basis stays unresolved; incompatible resolution blocks RMS calculation. | [Formal Queue LINE evaluator regressions](../tests/integration/test_queue_line_evaluation.py) cover Queue-specific RMS behavior, incomplete enumeration and cross-SPW rejection; detailed method evidence is recorded in [the Queue LINE decision](evidence/queue_line_decision_2026-09-25.md) |

Coverage, resolution compatibility and RMS use `exact_prepared_line_rationals_2`;
FDM and pair/context aggregation retain version 1. The
[precision contract](line_precision.md) owns operand and migration details.

## Tests versus scientific acceptance

The linked files test implemented behavior; the [catalog](acceptance_cases.md)
separately records numerical, source-isolation and completeness acceptance.
[LINE precision tests](../tests/integration/test_line_precision.py) cover both
sources at and around the resolution boundary and equivalent input units.
These engineering checks do not complete real-proposal review or broaden scope.
In particular, existing
profile UNKNOWN tests do not by themselves close the historical IN-08 scenario
or approve its source interpretation. The delivered adapter and formal evaluator preserve branch-local
three-valued results, source completeness and unsupported-scope reasons.

Queue continuum remains independent of Queue LINE mode classification.
Likewise, formal Queue LINE mode evidence alone does not establish RMS, frequency, position
or branch completeness. The experiment's 76 export cases and 14 all-family mapping
gaps remain explicitly scoped; see the [measurement](evidence/queue_processor_consensus_2026-09-23.md).
