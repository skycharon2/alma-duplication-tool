# Appendix A criteria

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

Planned next: CONT-SETUP (Q2), CONT-FREQ (Q3), POS-SINGLE (Q1). RMS and line
criteria wait for Q4-Q6; see the [rule inputs](duplication_rule_inputs.md).
