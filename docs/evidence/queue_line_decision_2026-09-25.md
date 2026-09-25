# Queue LINE evaluation decision — 2026-09-25

## Scope

This implementation is limited to current-cycle Queue CSV evidence for fixed celestial targets, single-field/single-pointing interferometric comparison contexts, and regular numbered SPWs. Mosaic, moving-target, Solar, spectral-scan scientific LINE evaluation, and formal TP-only/mixed-array scientific aggregation remain outside this method.

`Use TP? = True` is not, by itself, a pair-level blanket blocker. Formal Queue common-scope/beam evidence remains responsible for deciding whether the retained context has supported interferometric position/angular evidence.

## Same-pair invariant

For every proposed line window and candidate Queue SPW, LINE-FDM, LINE-COVERAGE, LINE-RESOLUTION-COMPATIBILITY, and LINE-RMS are evaluated from that exact physical Queue row and exact SPW. Whole-pair results are ORed. Conditions from different SPWs or rows must never be combined into a passing result.

## Queue-specific line methods

- Candidate mode: existing `queue_mode_evidence_adapter_2`, bound to the exact row/SPW.
- Candidate frequency: existing Queue SPW sky-frequency derivation and versioned usable interval.
- Coverage: proposed prepared SKY centre lies inclusively inside that same SPW's usable sky interval.
- Resolution: Queue `Spec.Res. SPW N` must be equal to or finer than the proposal target frequency width derived from the proposed SKY centre and planned velocity resolution.
- RMS basis: Queue `Req.Sensitivity` at `Ref.Freq.Width`, from the same physical row.
- Spectral normalization: `sigma_q_spectral = sigma_q_ref * sqrt(B_ref / Delta_nu_plan)`.
- Angular correction: `sigma_q_comp = sigma_q_spectral * (theta_plan / theta_queue)^2`.
- Final comparison: `sigma_q_comp <= 2 * sigma_plan`, inclusive.

The Archive `sensitivity_10kms` starting basis is not reused for Queue. Queue `Ref.Frequency` is retained as provenance but is not an operand of the adopted LINE-RMS formula.

The Portal-helper per-SPW projection is a derived estimate and retains the limitation that SPW-dependent Tsys variation is not modelled.

## Aggregation and completeness

Three-valued logic is retained. A definite false condition settles a pair conjunction even when another independent condition is unknown. A true pair settles the context existential result. A negative context result is permitted only when enumerations required by the pairing result are complete; otherwise the context remains indeterminate.
