# Criterion result contract

The [rules package](../src/alma_duplicate/rules/) contains independent ANGULAR, CONT-SETUP
and [Queue POS-SINGLE](pos_single.md) functions. The explicit `evaluate_candidate_search` entry point
connects them to a finished search; candidate search itself does not invoke them.
CONT-SETUP qualifies the proposed setup; it does not compare a candidate or
produce a duplicate verdict. All implemented methods remain PROVISIONAL.

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
| POS-SINGLE | `queue_pos_single_1` | [Queue candidate-side coverage](pos_single.md); structured issues identify proposed, candidate or method limitations. |
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
must not be relabelled as old ones.

## Explicit evaluation of a finished search

```python
from alma_duplicate.rules.evaluation import evaluate_candidate_search

report = evaluate_candidate_search(search_result)
```

The [entry point](../src/alma_duplicate/rules/evaluation.py) accepts a
`CandidateSearchResult` and takes the request exclusively from
`search_result.plan.validation.request`. It accepts no replacement request,
performs no network access, and does not rerun search filters. It expects the
unchanged result of the search service; its consistency checks do not provide a
cryptographic binding against manually replaced plan contents.

CONT-SETUP runs once per report, even for zero candidates. ANGULAR and POS-SINGLE run separately
for every row in `archive.retained_rows` and `queue.retained_rows`, in that order.
Both MATCHED_FILTERS and RETAINED_UNEVALUATED are eligible for this attempt.
EXCLUDED rows remain only in the retained original search audit. Neither a
negative CONT-SETUP result nor an unresolved spatial filter short-circuits candidate criteria.

Do not iterate only `search_result.candidates`: it may be display-limited.
Evaluation uses the complete retained source-row lists, preserving display
omissions in the original result. This does not recover remote truncation or
expand the executed search scope. Duplicate `(source, context_id)` identities,
wrong source provenance, inconsistent counts, and unfinished/invalid input are
rejected. Failed/incomplete sources follow the existing strict no-typed-rows
contract, while the other source can still contribute candidates.

[Evaluation models](../src/alma_duplicate/rules/evaluation_model.py) store the
original search result, a tuple of request-level criteria and one
`ContextEvaluation` per retained candidate. Each context evaluation retains its
original `CandidateRecord`; context references, alternatives, source dates,
filter records and scientific values are not flattened or combined. Rule results
must refer to that candidate's context ID. Programming errors propagate rather
than being converted to scientific missing-evidence results.

`evaluation_version="2"` versions orchestration; rule-result schema remains 2.
Report `execution="FINISHED"` means the requested criterion calls completed.
`assessment="NOT_AGGREGATED"` means no overall duplication decision was made.
The nested search result keeps its original `assessment="NOT_EVALUATED"`, which
belongs to the search stage. Every current rule remains PROVISIONAL; no approval
upgrade or negative duplication conclusion is inferred from source failure,
empty results, filter exclusion or criterion failure.

The optional `nominal_conversion` argument is forwarded only to CONT-SETUP. Its
existing explicit, provisional interpretation is unchanged and recorded by that
rule. This entry point does not infer conversions for candidates.

Run the offline example:

```bash
PYTHONPATH=src python examples/evaluate_candidate_rules.py
```

The example uses the repository Queue fixture, does not invent position
interpretations, and reports Archive as NOT_PROVIDED. Its retained unevaluated
candidates are not confirmed spatial matches. Regression coverage is in
[the connection tests](../tests/integration/test_context_rule_evaluation.py).
