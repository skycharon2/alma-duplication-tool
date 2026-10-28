# Step 04B — internal submitted-LINE V2 context evaluator

## Status and activation boundary

This step connects **the separated-input contract**, existing reference-bound
Archive LINE pairing, six existing approved per-pair criteria, and the Step 04A
`archive_line_context_submitted_or_2` context aggregator. It introduces a typed,
internal, offline evaluable path. It does **not** activate the shared public
`assess_observation` / CLI / browser search and report workflow, whose validator
still emits `SEPARATED_INPUT_NOT_EXECUTABLE`. That final integration and report
provenance review belong to Step 04C. Do not claim a search-wide absence result.

Legacy `archive_line_context_or_1`, `archive_line_pair_and_1` and old reports stay
unchanged. The standalone Step 02 `line_evaluation_scope` value
`SUBMITTED_LINE_REQUIREMENTS_V2` is still reserved and rejected on legacy wire
inputs. The **new separated input contract** selects this internal V2 method;
combining the two scope markers remains a `MIXED_INPUT_CONTRACTS` error.

## Inputs and protected computation

1. `prepare_submitted_line_request(raw_request)` calls the shared wire validator,
   permitting **only** its deliberate `SEPARATED_INPUT_NOT_EXECUTABLE` error.
   Any other parsing, structure, association or unit error fails closed. The
   request must be fixed-target, LINE-only, Single Pointing or Mosaic; mixed
   and Continuum-only **formal** science remain unavailable.
2. Existing `parse_separated_setup` supplies independent immutable operands.
   A short-lived, explicitly LINE-only typed `ProposedObservationRequest` view
   carries *only* `line_windows` and `line_sensitivities`; the view never carries
   `physical_spw_windows` or `physical_links`, a setup-completeness claim, a
   V2 user-supplied switch or a physical inventory completeness flag.
   Existing common-field validation parses position, angular resolution,
   setup ID and redshift. This view is **internal**, never serialized as a
   legacy request and never supplied to the public legacy assessment entry.
3. `evaluate_submitted_line_context_v2(prepared, context, common_criteria)`
   requires one real Archive `ComparisonContext`, plus the already computed
   `POS-SINGLE` (or `POS-MOSAIC`) and `ANGULAR` criterion results bound to its
   context ID. The caller must compute these from authentic Archive and spatial
   inputs; they cannot come from the browser payload. This is an internal
   boundary, not a public API accepting arbitrary user criterion objects.
4. Source, geometry, row link, alternative contexts and position exclusion
   checks follow legacy Archive LINE scope safeguards, **computed internally**.
   The client cannot set `context_supported`. Existing `build_line_pairs()` and
   `_numerical()` resolve the immutable Source-SPW component reference and all
   numerical LINE quantities within each full pair. `LinePairEvaluation`
   preserves the six formal approval gates.
5. Keep each original Source-SPW `LinePairAttempt` and its reference, but label
   this pairing result `archive_line_pair_builder_submitted_2` with scope
   `ONE_CONTEXT_SUBMITTED_LINE_REQUIREMENTS_ONLY`. Its inherited legacy
   `proposed_enumeration_complete` data field is **not** consulted for V2.
6. Submit all resulting whole-pair outcomes to the isolated V2 context OR.
   The V2 result contains the unchanged pair references, context ID and
   `submitted_requirement_ids`. Physical inventory completeness is never
   considered when determining FALSE. A known false condition may dominate
   unknown other criteria **inside the same full pair**; it never combines
   individual successes from different pairs.

## Outcome interpretation

- `TRUE` means **at least one** complete submitted LINE pair in this context
  satisfies all six criteria.
- `FALSE` means **every submitted LINE pair in this supported context** has a
  definitive failure. This is **not** whole-setup, whole-project or search-wide
  proof of no duplication.
- `UNKNOWN` remains for unresolved candidate FDM, reference/component, frequency,
  RMS, spatial method, unsupported context, conflicting alternatives or other
  truly unknown criterion evidence, unless a separate complete pair is TRUE.
- `physical_spw_inventory_complete=true` does **not** imply LINE completeness,
  and neither `setup_complete` nor the old
  `PROPOSED_ENUMERATION_INCOMPLETE` marker participates in V2 OR.
- All physical SPW evidence remains available independently for future
  Continuum qualification, not for LINE matching.

## Restrictions and what Step 04C must do

The new context evaluator is not a provider, acquisition, CLI command, report
writer, Mosaic pointings reader, or new browser Run button. Step 04C must
explicitly connect trusted candidate contexts and spatial criteria to it,
retain source failures and alternative candidates, define response/report
method and scope fields, and test both geometries with bounded offline and
approved live cases before removing the shared fail-closed guard. New-format
Continuum must be reviewed separately rather than being implicitly activated.

Do not publish an internal `SubmittedLineEvaluation` result as a formal report
without those final coverage, retrieval and provenance gates.

## Acceptance

Offline tests exercise genuine recorded Archive Guide B contexts and the
existing Mosaic geometry case: TRUE/FALSE/UNKNOWN, two submitted windows,
no cross-window or cross-context borrowing, optional physical SPWs, independent
physical completeness true/false, REST/redshift preparation, unapproved methods,
missing mode, unsupported alternatives, invalid/mixed requests, and continuing
public entrypoint rejection.

```bash
python -m pytest -q tests/integration/test_submitted_line_context_evaluation_step04b.py
python -m pytest -q \
  tests/integration/test_submitted_line_aggregation_step04a.py \
  tests/integration/test_line_scope_transition_baseline.py \
  tests/integration/test_separated_setup_contract_step03ba.py \
  tests/integration/test_separated_cross_scope_step03bc.py \
  tests/integration/test_line_evaluation.py \
  tests/integration/test_mosaic_scientific_acceptance.py
python -m pytest -q
ruff check src/alma_duplicate/rules/submitted_line_evaluation.py \
  tests/integration/test_submitted_line_context_evaluation_step04b.py
git diff --check
```
