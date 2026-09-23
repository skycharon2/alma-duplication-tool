# Reproducible acceptance cases and review status

The [catalog](../examples/acceptance/catalog.json) is an offline executable list
against PR #73. It adds no scientific methods and does not require new formula
approval. The [independent reference ledger](acceptance_reference_values.md) owns
raw-field extraction, arithmetic, expected outcomes and engineering-only boundaries.

## Inventory

| Case | Evidence kind | Purpose |
| --- | --- | --- |
| guide-a | SYNTHETIC_NUMERICAL | Continuum positive, negative and missing candidate RMS |
| guide-b | SYNTHETIC_NUMERICAL | Six line conditions, exact pair identity, both RMS intermediate values |
| missing-line-rms | SYNTHETIC_NUMERICAL | Missing requested RMS leaves coverage available and branch unknown |
| coarse-line-resolution | SYNTHETIC_NUMERICAL | Coarse resolution fails compatibility and blocks RMS |
| multiple-line-windows | SYNTHETIC_NUMERICAL | Two requested windows against two candidate SPWs; no cross-pair borrowing |
| mixed-intents | SYNTHETIC_NUMERICAL | Independent continuum/LINE results with explicit sensitivity associations |
| source-not-provided | SOURCE_FAILURE_ENGINEERING | Missing Queue input leaves Archive report usable; exit 3 |
| ngc6240-continuum | REAL_CAPTURE_ENGINEERING | Real capture mapping plus synthetic proposal; 157 evaluated contexts |
| ngc6240-line-diagnostic | HYBRID_DIAGNOSTIC | Real Source–SPW component independently checked against artificial line input; retain .5 arcsec angle |

All nine cases have status AWAITING_INDEPENDENT_REVIEW, with no invented reviewer,
date or approval record. **Reviewed real-proposal cases: zero.** Confirmed formulas,
independent arithmetic and executable expected results do not justify silently
promoting artificial requests to reviewed real science cases.

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
`execution.txt`. Root `summary.json` records catalog hash, case classifications,
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
