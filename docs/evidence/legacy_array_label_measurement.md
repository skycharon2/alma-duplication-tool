# Historical exact-label beam measurement

The following record is preserved from the pre-classifier search documentation.
Its zero-resolution counts describe the exact-label heuristic, not the current
array classifier. No live measurement was repeated for the rule-schema update.

A pinned CASE1/CASE2 weak-recall acceptance test now exists at
[tests/live/test_case_retrieval.py](../../tests/live/test_case_retrieval.py); it
asserts only that the reported Member UID is retrieved, not an exact
candidate count or disposition (see that file's module docstring for the
exact boundary). It has been run against the live service and PASSED for
both cases (see docs/duplication_rule_inputs.md section 8, "Executed
retrieval evidence" for the retrieved-row counts, dispositions and matched-
row reasons); this remains a retrieval-recall result, not a confirmation of
CASE1/CASE2 as duplicates. A companion applicability measurement,
[tests/live/test_case_beam_strategy_applicability.py](../../tests/live/test_case_beam_strategy_applicability.py),
reports whether the formula primary-beam strategy's array-label diameter
lookup resolves for the real rows near each case; see
[primary_beam_search.md](../primary_beam_search.md) for what it does and does
not claim, and for the result of that run (0 of 336 / 0 of 851 rows resolved
a diameter in this small local sample). An Archive-wide census,
[scripts/beam_array_label_census.py](../../scripts/beam_array_label_census.py),
has since confirmed this generalizes: **0%** of all 443,998
`science_observation = 'T'` Archive rows have an `antenna_arrays` value
exactly equal to `12-m`/`7-m` (see primary_beam_search.md and
docs/duplication_rule_inputs.md section 8 for the full result).
