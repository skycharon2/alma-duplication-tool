# Appendix A criteria

CONT-SETUP describes whether the continuum condition applies to the proposal;
its SATISFIED outcome is applicability, not a duplicate.

Package: [`alma_duplicate.rules`](../src/alma_duplicate/rules/). Each criterion is an
independent function returning one `CriterionResult` for one proposed request and,
where the criterion compares observations, one coherent candidate context. No
function in this package issues an overall duplication verdict; aggregation across
criteria remains planned.

## Result model

| Field | Meaning |
| --- | --- |
| `criterion_id`, `policy_ref` | Criterion name and the cited Appendix A heading |
| `method_version`, `approval` | Implemented method and its status (`PROVISIONAL` until written confirmation, then `APPROVED`) |
| `outcome` | `SATISFIED`, `NOT_SATISFIED`, `INSUFFICIENT_INFORMATION`, `NOT_APPLICABLE`, `NOT_EVALUATED` |
| `proposed`, `candidate` | Value, unit, source field and semantics on each side |
| `derived` | Named derived numbers, e.g. the factor |
| `reasons`, `missing_side`, `decision_refs` | Explanation, the side lacking evidence, and the decision records relied on |

Missing, invalid or unit-incompatible evidence yields `INSUFFICIENT_INFORMATION`
with `missing_side`, never `NOT_SATISFIED`.

## Implemented criteria

| ID | Policy text (Appendix A) | Method | Status |
| --- | --- | --- | --- |
| ANGULAR | "The proposed angular resolution differs by a factor of <=2 from the other observation." | `angular_factor_1`: symmetric factor max/min <= 2, inclusive boundary with a 1e-9 relative band; Archive `spatial_resolution` (estimate), Queue `Req. Ang. Res.` (request) | PROVISIONAL: field mapping from week 1 feedback |
| CONT-SETUP | "the proposed correlator setup must contain 2 or more windows with a bandwidth > 1.8 GHz" | `continuum_setup_1`, proposal only: USABLE widths compared strictly (1e-9 GHz equality band); NOMINAL/UNKNOWN widths <= 1.8 GHz cannot qualify, wider ones are unresolved unless `nominal_conversion="PORTAL_SCRIPT_V1"` is chosen; two distinct qualifying windows satisfy it even for an incomplete list | PROVISIONAL: Q2 reported feedback; follows the prepared acceptance table |

Planned next: CONT-FREQ (Q3) and POS-SINGLE (Q1). RMS and line
criteria wait for Q4-Q6; see the [rule inputs](duplication_rule_inputs.md).
