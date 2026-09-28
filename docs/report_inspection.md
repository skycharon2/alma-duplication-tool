# Report inspection v3: pair identity

`inspect_report(document)` now defaults to inspection version `3`. Report v4
and scientific evaluator methods are unchanged. This is a report-consumer fix,
not a new duplication decision or a change to scientific evidence.

Each pair-specific gap has:

- `location`: a JSON Pointer to its exact criterion in the input report, such as
  `/context_evaluations/0/line_pairs/2/criteria/5`;
- `pair_identity.context_id`, `proposed_window_id` and `pair_index`;
- `pair_identity.reference`: the original source-specific pairing reference.
  Queue includes the row/SPW identity; Archive includes its assigned component.
  Unresolved Archive attempts retain a null reference and their report location.

Indices locate occurrences within this report, not across reports or reorderings.
Use the pairing reference for scientific source identity. No identity is guessed
when an association is unresolved. Only pair locations are JSON Pointers;
existing non-pair locations retain their earlier convention.

Deduplication remains per location, reason code and side. Different candidate
SPWs or proposed windows retain separate occurrences. Repeated identical issues
within the same criterion count once. POS-SINGLE and ANGULAR are read from the
context criteria once; their copies in line pairs are not counted again.
Counts describe evidence occurrences, not duplicate observations or independent
missing user inputs. A missing planned RMS affecting four SPWs produces four
pair occurrences, even though one input correction may resolve all four.

Versions `1` and `2` remain explicitly callable to reproduce historical summaries:
`inspect_report(document, inspection_version="2")`. Their historical pair
undercount is retained for reproducibility; use version 3 for new consumers.
The active acceptance catalog updates only three inspection-version assertions.
Pinned scientific references and expected evaluator outcomes remain unchanged.

Regressions cover an actual four-SPW Queue evaluation with missing planned RMS,
shared common criteria, repeated issues, distinct windows, unresolved Archive
references and exact report lookup. Source failures, empty results and the
absence of a search-wide verdict retain their existing behavior.
