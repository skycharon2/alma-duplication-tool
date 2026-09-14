# Criterion result contract

The [rules package](../src/alma_duplicate/rules/) contains independent ANGULAR
and CONT-SETUP functions. Candidate search does not invoke them automatically.
CONT-SETUP qualifies the proposed setup; it does not compare a candidate or
produce a duplicate verdict. Both implemented methods remain PROVISIONAL.

## Separate result dimensions (schema 2)

The authoritative definitions are in [model.py](../src/alma_duplicate/rules/model.py).

| Field / Python enum | Values and meaning |
| --- | --- |
| `evaluation` / `EvaluationStatus` | EVALUATED, INSUFFICIENT_INFORMATION, NOT_APPLICABLE, NOT_EVALUATED: whether computation produced a condition result, lacks required evidence, is outside method scope, or has not run |
| `outcome` / `CriterionOutcome` | SATISFIED or NOT_SATISFIED only when EVALUATED; otherwise `None` (JSON null) |
| `applicability` / `MethodApplicability` | APPLICABLE, UNRESOLVED, NOT_APPLICABLE: whether the implemented method can operate on the supplied evidence within its input scope |
| `approval` / `MethodApproval` | PROVISIONAL or APPROVED: scientific confirmation status, independent of successful computation |
| `issues` | All retained `CriterionIssue` records: side, code, path and message; multiple sides may be present |
| `criterion_id`, `policy_ref`, `method_version`, `numeric_method`, `result_version` | Criterion identity, policy and versioned execution semantics |
| `context_id`, `proposed`, `candidate` | Context association and values with units, source fields and semantics; retain the original context alongside this result for raw/component references |
| `derived`, `details`, `reasons`, `decision_refs` | Calculated summaries, per-window/exact-ratio details, explanations and interpretation references |

Constructors reject contradictory computed-state/outcome combinations. A computed
outcome requires APPLICABLE. APPROVED requires a decision reference; a reference
by itself does not confer approval. The two evaluators never upgrade approval.

`has_computed_outcome` describes calculation only.
`eligible_for_formal_aggregation` additionally requires APPLICABLE and APPROVED.
This is a necessary per-criterion gate, not a complete aggregation algorithm:
future aggregation must still respect coherent contexts, branch scope, other
criteria and source/search completeness. Formal aggregation is not implemented.

Issues preserve evidence limitations, not a universal veto. For example, two
known qualifying windows establish the existential CONT-SETUP condition even
when another window is unresolved or enumeration is incomplete. Those issues
remain visible. A negative result requires complete, resolved enumeration.

## Numeric contract and implemented methods

[Numeric helpers](../src/alma_duplicate/rules/numeric.py) compare the exact decimal
spellings of finite positive **canonical** scalars using rational arithmetic
(`canonical_decimal_exact_1`). There is no epsilon or threshold snapping.
This contract neither recovers precision lost during normalization (including
interval-span construction) nor interprets measurement uncertainty. If a future
method needs uncertainty bounds, it must define and version them explicitly.

| Criterion | Method version | Behavior |
| --- | --- | --- |
| ANGULAR | `angular_factor_2` | Symmetric max/min <= 2, inclusive. Uses Archive `spatial_resolution` estimates or Queue requested angular resolution, canonical arcsec. Missing/invalid/unit-unsafe evidence on both sides is retained. |
| CONT-SETUP | `continuum_setup_2` | At least two distinct proposed windows with USABLE width strictly > 1.8 GHz. Exactly 1.8 does not qualify; 1.8000000005 does. UNKNOWN width semantics remain unresolved, including narrow widths. |

For ANGULAR, 2.000000001 exceeds the limit. The exact factor is saved in details;
if its display float overflows, `derived.factor` is null without changing the
exact condition result.

A NOMINAL width <= 1.8 GHz bounds its usable width and cannot qualify under this
provisional interpretation. Larger nominal widths require usable evidence or
explicit `nominal_conversion="PORTAL_SCRIPT_V1"`. This existing opt-in mapping
is recorded, remains provisional, and is not automatically applied to Archive
windows. Its source-specific applicability still requires confirmation.
See the [scientific decision record](evidence/scientific_feedback.md).

## Caller migration from schema 1

This is an intentional rule-result API change; no legacy five-state wrapper is
provided. Request, ingestion and search-result schemas are unchanged.

| Previous access | Schema 2 replacement |
| --- | --- |
| `outcome == INSUFFICIENT_INFORMATION` (or NOT_APPLICABLE / NOT_EVALUATED) | Inspect `evaluation`; `outcome` is null |
| `missing_side` | Iterate `issues`; `issue_sides` provides a distinct-side summary |
| `is_definite` for numerical status | `has_computed_outcome` |
| `is_definite` for formal use | `eligible_for_formal_aggregation`, then the future branch/context/completeness gates |
| Positional `CriterionResult(...)` | Named arguments with explicit evaluation, applicability and approval |

Historical reports retain their original method/schema versions. New results
must not be relabelled as old ones. The next delivery is a per-context evaluation
flow that computes CONT-SETUP once per request and ANGULAR per coherent context,
retains all issues, and leaves the overall duplication assessment unevaluated.
