# Criterion result contract

The [rules package](../src/alma_duplicate/rules/) implements the confirmed
Archive fixed-target, single-point continuum branch: POS-SINGLE, ANGULAR,
CONT-SETUP, CONT-FREQ and CONT-RMS. `intents` selects execution. Each coherent
retained context gets a three-valued continuum assessment. Queue methods retain
their independent provisional status. Archive LINE implements reference-bound
FDM, coverage, resolution compatibility and RMS criteria, pair AND and context-local pair OR. No search-wide absence verdict is produced.

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
by itself does not confer approval. Confirmed wrappers select new approved method versions with the confirmation reference; legacy results are not relabelled.

`has_computed_outcome` describes calculation only.
`eligible_for_formal_aggregation` additionally requires APPLICABLE and APPROVED.
This is a necessary per-criterion gate, not a complete aggregation algorithm:
both implemented branch aggregators also check coherent contexts and branch scope.
It returns CRITERIA_MET, CRITERIA_NOT_MET or INDETERMINATE. Search completeness
remains separate; a branch result does not establish a search-wide conclusion.

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
| ANGULAR | `archive_angular_factor_3` (approved Archive); `angular_factor_2` (legacy) | Symmetric max/min <= 2, inclusive. Uses Archive `spatial_resolution` estimates or Queue requested angular resolution, canonical arcsec. Missing/invalid/unit-unsafe evidence on both sides is retained. |
| POS-SINGLE | `queue_pos_single_1` | [Queue candidate-side coverage](pos_single.md); structured issues identify proposed, candidate or method limitations. |
| CONT-SETUP | `continuum_setup_3` (approved without nominal conversion); `continuum_setup_2` (legacy) | At least two distinct proposed windows with USABLE width strictly > 1.8 GHz. Exactly 1.8 does not qualify; 1.8000000005 does. UNKNOWN width semantics remain unresolved, including narrow widths. |
| Archive POS-SINGLE | `archive_pos_single_1` | Candidate `frequency`, unambiguous interferometric diameter, spherical separation <= half-power radius; inclusive float64 boundary. |
| CONT-FREQ | `archive_cont_freq_1` | User representative SKY frequency versus Archive `frequency`: symmetric factor <= 1.3. No SPW-mean fallback. |
| CONT-RMS | `archive_cont_rms_2` | One direct setup aggregate RMS: Archive estimate <= 2 × proposal RMS. Optional contributing IDs must uniquely reference this setup's windows; subsets are allowed. No bandwidth or angular scaling. |

Version 2 of CONT-RMS accepts legal contribution references and records them in
`details`; version 1 remains the identity of historical reports. Rule-result
schema remains 2. Solar CLI exemption uses `solar_exemption_1` without candidates.

For ANGULAR, 2.000000001 exceeds the limit. The exact factor is saved in details;
if its display float overflows, `derived.factor` is null without changing the
exact condition result.

A NOMINAL width <= 1.8 GHz bounds its usable width and cannot qualify under this
provisional interpretation. Larger nominal widths require usable evidence or
explicit `nominal_conversion="PORTAL_SCRIPT_V1"`. This existing opt-in mapping
is recorded, remains provisional, and is not automatically applied to Archive
windows. Its source-specific applicability still requires confirmation.
See the central [scientific decision register](duplication_rule_inputs.md#7-scientific-decision-register);
historical reported feedback remains preserved in [its evidence record](evidence/scientific_feedback.md).

## Confirmed Archive line evaluation

[`rules/line.py`](../src/alma_duplicate/rules/line.py) consumes the existing
[preparation and reference contract](line_pairing_design.md) once per context.
Every numerical value comes from `reference.resolve(request, context)` and its
selected support component. No row-level sensitivity or resolution fallback is
used; Queue mappings and mosaic/moving/TP remain outside this approved workflow.

| Criterion | Method version | Inclusive condition / dependency |
| --- | --- | --- |
| LINE-FDM | `archive_line_fdm_1` | Both proposed mode and associated Archive operational mode are FDM; a known TDM is false; otherwise absent mode is unknown |
| LINE-COVERAGE | `archive_line_coverage_1` | Exact component interval contains the prepared sky center, including both endpoints; no row frequency/bandwidth approximation |
| LINE-RESOLUTION-COMPATIBILITY | `archive_line_resolution_compatibility_1` | `299792.458 * dnu_archive_GHz / nu_sky_GHz <= dv_plan_kms` |
| LINE-RMS | `archive_line_rms_1` | Compatible resolution, same-component @10km/s estimate, associated requested RMS and both angular resolutions are required |

LINE-RMS computes `sigma_at_plan = sigma10 * sqrt(10 / dv_plan_kms)`, then
`sigma_comp = sigma_at_plan * (theta_plan / theta_archive)^2`, and checks
`sigma_comp <= 2 * sigma_requested`. RMS is in mJy/beam and angles in arcsec.
ANGULAR remains a separate condition. Coarse Archive resolution makes the
resolution condition false but leaves LINE-RMS without an outcome or either
computed RMS, with `ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED`.
Missing resolution similarly blocks RMS; missing RMS does not erase coverage.

The numeric method `canonical_decimal_unit_scale_squared_rms_1` uses rational
arithmetic over the decimal spellings of validated values and explicit unit
conversion scales. It compares the squared RMS ratio to 4 exactly, without an
epsilon. Square roots are calculated with a local 40-digit Decimal context for
display only. This does not recover precision lost in parsing or prior request
preparation, and performs no new frame transformation. Exact squared quantities
are retained in details. A display value outside finite nonzero float range is
null with `NUMERIC_DISPLAY_UNREPRESENTABLE`; the exact comparison remains valid.

`LinePairEvaluation` retains the complete attempt/reference and six criteria:
POS-SINGLE, ANGULAR and the four line conditions. `archive_line_pair_and_1`
combines only eligible approved results within that one pair. A definite false
AND unknown is false. Unapproved results supply unknown, never a formal true.

`archive_line_context_or_1` ORs **whole pair results** within one coherent context:
true OR unknown is true; false OR unknown is unknown. Different pairs cannot
contribute different passing conditions. If proposed enumeration is incomplete,
add an unknown alternative: a demonstrated positive remains positive, but all
listed failures cannot establish a negative. An empty list is unknown even if
marked complete. Unlinked/conflicting or unsupported contexts remain unknown.
No OR across candidate contexts, sources or mixed intents is provided.

All new methods use the existing [confirmation](evidence/supervisor_confirmation_2026-09-17.md#confirmed-2026-09-21).
Numerical acceptance is in [line tests](../tests/integration/test_line_evaluation.py);
preparation regressions remain in [preparation tests](../tests/integration/test_line_preparation.py).
A context result does not establish retrieval completeness or a reviewed real-case label.

## Caller migration from schema 1

This is an intentional rule-result API change; no legacy five-state wrapper is
provided. Request, ingestion and search-result schemas are unchanged.

| Previous access | Schema 2 replacement |
| --- | --- |
| `outcome == INSUFFICIENT_INFORMATION` (or NOT_APPLICABLE / NOT_EVALUATED) | Inspect `evaluation`; `outcome` is null |
| `missing_side` | Iterate `issues`; `issue_sides` provides a distinct-side summary |
| `is_definite` for numerical status | `has_computed_outcome` |
| `is_definite` for formal use | `eligible_for_formal_aggregation`, then the implemented branch/context gates and separate search completeness |
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

CONT-SETUP runs once when CONTINUUM is selected, even for zero candidates.
ANGULAR and POS-SINGLE run when a branch is selected; CONT-FREQ and CONT-RMS
run for CONTINUUM. All retained Archive and Queue contexts are visited.
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

`evaluation_version="5"` versions orchestration; rule-result schema remains 2.
Report `execution="FINISHED"` means evaluation completed. In candidate reports,
`assessment="NOT_AGGREGATED"` means no search-wide decision was made; inspect
`context_evaluations[].branches` for independent continuum and LINE results. The
nested search assessment stays NOT_EVALUATED. LINE pair results are in `line_pairs`.
An approved explicit failure can make a supported continuum branch or line pair false
even when another condition is unknown. Unapproved results do not supply formal
truth. Empty results, source failure and filter exclusion never imply absence.

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

## Scoped Queue continuum

The `queue_continuum=True` evaluator option enables the
[Queue continuum contract](queue_continuum.md) and implies Queue common methods.
It supplies approved source-specific frequency/RMS criteria and a context-local
continuum branch. Unsupported common scope remains indeterminate. Default and
common-only calls retain their previous scope. Queue LINE is not enabled by this option.
