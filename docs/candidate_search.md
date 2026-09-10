# Candidate search service

## Formula spatial strategy

An explicit `beam_decision_ref` enables [coordinate retrieval and formula beam
selection](primary_beam_search.md). Without it, the existing region strategy
remains compatible. Region-specific descriptions below apply to that legacy
strategy; formula search uses centers and separate local beam checks.


Service version 1 connects validated requests, existing search plans, Archive
query execution/binding, Queue loading/selection and comparison contexts.
It discovers candidates for review; `assessment` remains `NOT_EVALUATED`.

## Inputs

`alma_duplicate.candidate_search.search_candidates(validation, ...)` accepts:

| Argument | Meaning |
| --- | --- |
| `validation` | A valid request validation result with search readiness |
| `archive_client` | Explicitly supplied ArchiveClient-compatible object with `search(spec)` |
| `archive_result` | Alternative: previously obtained ArchiveQueryResult, checked against this plan |
| `queue_result` | Already parsed QueueCsvParseResult |
| `queue_loader` | Alternative: zero-argument callable returning QueueCsvParseResult, e.g. QueueCsvClient.load with its path bound |
| `interpretations` | Optional iterable of source-row-scoped PositionInterpretation records |
| `archive_science_only` | Explicit Archive science-only restriction; defaults to false |

Client/result or loader/result pairs are mutually exclusive. Invalid requests and
duplicate interpretation IDs fail before I/O. No client is created implicitly.
Providers for unselected sources are never called. Unused interpretation IDs are
reported, including when a source fails or is not selected.

The Queue loader allows file-read failures to be reported independently of Archive.
It does not authorize downloads, invent retrieval times or require persistence.
Acquisition/run binding still belongs to the caller; existing source timestamps,
checksum, metadata and diagnostics stay in the retained parse result.

## Execution and source outcomes

Each source has its own SourceSearchExecution and source record:

| Status | Meaning |
| --- | --- |
| NOT_SELECTED | Source was not selected; its provider was not called |
| NOT_PROVIDED | Selected source has no provider/result |
| FAILED | Provider exception, binding failure, Queue parse failure or context-construction failure |
| INCOMPLETE | Archive overflow/count mismatch; no unsafe reconstruction |
| COMPLETED | Every constructed context from the supplied complete input was processed |

Archive client receives the generated ArchiveQuerySpec. Both fresh and supplied
results must pass query binding before construction. Incomplete raw results remain
available for diagnosis, but do not become candidates through a bypass.
Queue retains its strict parse gate. One source failure does not abort the other.

Operational exceptions at source and per-row/filter boundaries become explicit
reasons (stage, exception type and message); they are never converted to empty
success. KeyboardInterrupt and SystemExit are not caught. The service does not
retry. Programming/configuration failures in these records still need investigation.

`execution=FINISHED` means orchestration ended, including failure outcomes.
The immutable input plan retains its declarative `NOT_EXECUTED` marker; actual
execution is recorded by the service result, source records and FilterExecution
objects. No global success/comparison-ready flag hides source or filter limits.

## Per-row results and evidence

CandidateRecord references the original ComparisonContext and optional adapted
SpatialEvidence, with one FilterExecution per planned predicate. It records the
predicate index/name, execution stage, outcome, reasons and individual selector
result. The source plan retains original operators, values, units and skipped
conditions. Server predicate indices identify predicates reported by a complete,
plan-bound Archive retrieval; this is not an independent audit of the server.

| Disposition | Meaning |
| --- | --- |
| MATCHED_FILTERS | Every planned predicate returned a definite match for this row |
| RETAINED_UNEVALUATED | No definite exclusion, but at least one skipped/unevaluated condition |
| EXCLUDED | At least one explicit predicate returned NO_MATCH |

Both retained dispositions are included in candidates. Excluded rows remain in
`source.rows` with their evidence and filters. If geometry is unknown but an
independent angular filter definitely fails, the row is EXCLUDED **for that
angular filter**, and its missing geometry remains visible in unevaluated_rows.
Nothing is silently classified as outside because it is unsupported or missing.

Archive server-reported intersection is also checked through the existing limited
local spatial adapter. A local OUTSIDE that disagrees with the server is retained
as NOT_EVALUATED with SERVER_LOCAL_SPATIAL_DISAGREEMENT, not silently excluded.
Unsupported local geometry remains unevaluated. An inconsistent or missing
science-observation flag under science-only retrieval is similarly flagged.
All original selector outputs are retained, including a disagreeing OUTSIDE value.

Frequency, RMS and spectral-resolution predicates currently skipped by the planner
stay SKIPPED; they are not implemented by this service. Queue coordinate/target
interpretations are never fabricated. Existing geometry, offsets, TP and SPS
limitations apply. See [search/spatial](search_plan_spatial.md).

## Limits, completeness and grouping

SearchOptions.result_limit is a **global presentation limit on retained context
rows**, applied after all selected sources and all contexts have been processed.
It is not TAP MAXREC, a query TOP clause or an early-stop instruction.
Order is requested source order followed by lexicographic context ID within each
source. This deterministic order is not scientific ranking.

`total_retained` counts before the limit. `candidates` is the limited view;
`truncated` and per-source omitted_candidate_ids describe omitted display rows.
The full source.rows audit remains available, so this limit does not bound memory
or erase unevaluated evidence. A small limit may leave no visible rows from a
later source; its execution, retained records and omissions are still reported.

`requested_filters_fully_evaluated` requires a completed source, no skipped plan
predicates and no unevaluated row conditions. A skipped predicate is still skipped
for an empty result. This property is independent of display truncation and
does not establish universal source coverage or formal criterion evaluability.

Query scope/projection/counts remain in Archive provenance. Queue date, URL,
description and checksum remain in its snapshot. COMPLETED does not mean all-sky
coverage or all queued programs. Empty, failed, truncated and unevaluated results
never produce a negative duplication verdict.

Member OUS grouping is not performed here; candidates are individual contexts.
Alternatives and observed associations remain intact, with no best-value merging.
CASE grouping/expected UIDs require a separate reproducible retrieval fixture;
existing synthetic tests are not CASE verification.

## Running

```bash
python -m pytest -q tests/integration/test_candidate_search.py
python examples/search_candidates.py
```

The example uses the local Queue fixture and explicitly reports Archive missing.
It supplies no artificial fixed-target/frame interpretation. To opt into Archive
network execution, pass `--live-archive`. A different controlled Queue file may be
selected with `--queue-csv PATH`. Live service availability and complete snapshot
acceptance must be reported separately from offline test results.

The offline integration suite exercises both source paths, real ArchiveClient
with fake TAP, QueueCsvClient loading, complete/empty/incomplete/failed inputs,
query mismatch, unknown geometry, skipped/missing filters, server disagreement,
source isolation and post-processing display limits.

A pinned CASE1/CASE2 weak-recall acceptance test now exists at
[tests/live/test_case_retrieval.py](../tests/live/test_case_retrieval.py); it
asserts only that the reported Member UID is retrieved, not an exact
candidate count or disposition (see that file's module docstring for the
exact boundary). It has been run against the live service and PASSED for
both cases (see docs/duplication_rule_inputs.md section 8, "Executed
retrieval evidence" for the retrieved-row counts, dispositions and matched-
row reasons); this remains a retrieval-recall result, not a confirmation of
CASE1/CASE2 as duplicates. A companion applicability measurement,
[tests/live/test_case_beam_strategy_applicability.py](../tests/live/test_case_beam_strategy_applicability.py),
reports whether the formula primary-beam strategy's array-label diameter
lookup resolves for the real rows near each case; see
[primary_beam_search.md](primary_beam_search.md) for what it does and does
not claim, and for the result of that run (0 of 336 / 0 of 851 rows resolved
a diameter in this small local sample). An Archive-wide census,
[scripts/beam_array_label_census.py](../scripts/beam_array_label_census.py),
has since confirmed this generalizes: **0%** of all 443,998
`science_observation = 'T'` Archive rows have an `antenna_arrays` value
exactly equal to `12-m`/`7-m` (see primary_beam_search.md and
docs/duplication_rule_inputs.md section 8 for the full result).

Next: confirm CASE grouping/count semantics (Q7) before extending this
test's assertions beyond weak recall; with the exact-label heuristic now
confirmed to resolve 0% of the Archive, prioritize a real
`classify_array_type()` parser before relying on the formula strategy's
Archive side beyond hand-checked cases; extend supported evidence/methods
incrementally. Formal duplication rules remain a separate layer.
