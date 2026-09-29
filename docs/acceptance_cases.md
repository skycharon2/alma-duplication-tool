# Reproducible acceptance cases and review status

The [catalog](../examples/acceptance/catalog.json) is an offline executable,
versioned acceptance contract. Catalog v2 adds explicit evaluator selection without
adding or approving any scientific method. The
[independent reference ledger](acceptance_reference_values.md) and pinned
case-specific reference records own raw-field extraction, arithmetic, expected
outcomes and engineering-only boundaries.

## Version boundary for pinned references

Treat pinned reference records as immutable historical acceptance evidence. A
reference may name the method versions that existed when it was prepared; do not
rewrite that file or its catalog SHA solely to track a later method/numeric
version migration.

For current runtime method identities, use [rules](rules.md), the shared
[LINE precision contract](line_precision.md), and the assertions in the active
catalog/report. The LINE precision migration advances Archive and Queue
coverage/resolution/RMS to version 2 while preserving pinned numerical/reference
records and expected outcomes. A version-1 method identifier inside a pinned
reference is provenance, not a UI/backend method-selection instruction.

## Inventory

| Case | Evidence kind | Purpose |
| --- | --- | --- |
| guide-a | SYNTHETIC_NUMERICAL | Continuum positive, negative and missing candidate RMS |
| guide-b | SYNTHETIC_NUMERICAL | Six line conditions, exact pair identity, both RMS intermediate values |
| missing-line-rms | SYNTHETIC_NUMERICAL | Missing requested RMS leaves coverage available and branch unknown |
| coarse-line-resolution | SYNTHETIC_NUMERICAL | Coarse resolution fails compatibility and blocks RMS |
| multiple-line-windows | SYNTHETIC_NUMERICAL | Two requested windows against two candidate SPWs; no cross-pair borrowing |
| mixed-intents | SYNTHETIC_NUMERICAL | Independent continuum/LINE results with explicit sensitivity associations |
| [dual-source-continuum](acceptance_reference_dual_source_continuum.md) | SYNTHETIC_NUMERICAL | Same-request Archive+Queue formal continuum with source-bound outcomes |
| [dual-source-line](acceptance_reference_dual_source_line.md) | SYNTHETIC_NUMERICAL | Same-request Archive+Queue formal LINE with one positive and one RMS-negative Queue whole pair |
| [adversarial-source-spw-isolation](acceptance_reference_adversarial_source_spw_isolation.md) | SYNTHETIC_NUMERICAL | Favorable LINE evidence is split across Archive contexts and Queue SPWs; no pair may borrow evidence |
| [archive-failed-queue-preserved](acceptance_reference_source_state_matrix.md#archive-failed-queue-preserved) | SOURCE_FAILURE_ENGINEERING | Archive query binding fails while completed Queue contexts remain usable; exit 3 |
| [queue-failed-archive-preserved](acceptance_reference_source_state_matrix.md#queue-failed-archive-preserved) | SOURCE_FAILURE_ENGINEERING | Strict Queue ingestion fails while completed Archive contexts remain usable; exit 3 |
| [completed-empty-queue](acceptance_reference_source_state_matrix.md#completed-empty-queue) | SOURCE_FAILURE_ENGINEERING | Queue completes with zero rows; empty success remains distinct from missing/failure and yields no search-wide verdict |
| source-not-provided | SOURCE_FAILURE_ENGINEERING | Missing Queue input leaves Archive report usable; exit 3 |
| ngc6240-continuum | REAL_CAPTURE_ENGINEERING | Real capture mapping plus synthetic proposal; 157 evaluated contexts |
| ngc6240-line-diagnostic | HYBRID_DIAGNOSTIC | Real Source–SPW component independently checked against artificial line input; retain .5 arcsec angle |

All fifteen cases have status AWAITING_INDEPENDENT_REVIEW, with no invented reviewer,
date or approval record. **Reviewed real-proposal cases: zero.** Confirmed formulas,
independent arithmetic and executable expected results do not justify silently
promoting artificial requests to reviewed real science cases.

## Catalog v2 evaluator options

Every v2 case declares exactly three JSON booleans:

    "evaluation_options": {
      "queue_common": false,
      "queue_continuum": false,
      "queue_line": false
    }

Unknown option names, missing option keys, non-boolean values, unknown v2 case
keys and non-boolean `queue_candidate_beam` values are rejected before execution.

Queue evaluator options must also agree with the request contract. Queue must be
a selected source, `queue_continuum` requires CONTINUUM intent and `queue_line`
requires LINE intent. A Queue CSV is deliberately not required because
NOT_PROVIDED is itself an acceptance condition.

The runner translates true options to production CLI flags in deterministic
common/continuum/LINE order. For catalog v2 it also checks requested options
against report-v4 `evaluation_configuration`. Queue continuum or LINE therefore
has effective `queue_common=true`. This checks execution provenance, not a
scientific expected value.

The nine pre-existing cases were migrated to catalog v2 with all three evaluator
options false, so their historical scientific invocation is unchanged. Historical
catalog v1 remains readable; absence of `evaluation_options` in v1 normalizes to
all false and does not retroactively label those runs as formal Queue evaluation.

## Execute

```bash
python -m alma_duplicate.cli.acceptance \
  --catalog examples/acceptance/catalog.json \
  --output-dir reports/acceptance-run-1
```

The runner uses the production evaluation CLI in offline mode. There is no live
fallback. It checks catalog/request/reference/manifest/CSV pins and each raw replay
response before execution. Paths in the catalog are relative to its directory;
run the command from the repository root or pass absolute paths. Existing output
directories are rejected to avoid replacing evidence. Use a new directory each run.

Each case produces `report.json` (unaltered report v4), `inspection.json` (read-only
gap summary), `comparison.json` (expected/actual differences with references), and
`execution.txt`. Acceptance-run version 2 records each case's requested
`evaluation_options`. Root `summary.json` records catalog hash, case classifications,
review status, input hashes and results, including the number of REAL_PROPOSAL
cases declared REVIEWED. That count reads review metadata; it does not create or
authenticate a human sign-off. Outputs are intentionally not committed
as changing multi-megabyte golden reports; they are reproducibly generated.
No expected value is automatically updated from an evaluator result.

| Acceptance exit code | Meaning |
| --- | --- |
| 0 | All pinned assertions and expected evaluation exit codes matched |
| 1 | At least one comparison failed; inspect differences |
| 2 | Catalog/input validation or execution setup failed |

A case can PASS with expected evaluation exit 3, UNKNOWN outcomes or missing
source data. This means the required behavior was reproduced, not that the data
source completed or a candidate was proved duplicate. Optional numeric absolute
tolerances are explicit per assertion; outcomes, IDs and nulls are exact checks.
Report `generated_at` is not a frozen expected capture timestamp.

## Review and extension

Use evidence_kind `REAL_PROPOSAL` when adding an actual proposal request as a new case. Preserve raw captures,
manifest timestamps/source and checksums. Document the exact member/execution/
source/SPW/component, raw units, independent calculations, expected outcomes and
unresolved reasons in a separately retained reference record. Pin that document.
Only when an actual reviewer has recorded the review should status change to
REVIEWED with reviewer, reviewed_at and record. A mismatch remains visible until
its cause is understood; do not copy the new output into the expected field to
make a test green. Keep synthetic, hybrid, captured-data engineering and genuine
proposal evidence distinguishable.

The [thin-interface contract](thin_interface_contract.md) defines display labels
and explains overlapping gap counts. The [PR plan](roadmap.md) owns the
remaining UI and case-review work.
