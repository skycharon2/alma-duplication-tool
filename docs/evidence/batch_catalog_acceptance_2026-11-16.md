# Multi-source catalog workflow acceptance — 2026-11-16

## Scope and outcome

Eight offline HTTP workflow cases passed: four existing catalog cases, each
uploaded as CSV and whitespace TXT. Each upload contains two independent rows
at the catalog's captured cone, with distinct names and redshifts 0.024 and 0.
These rows are controlled variants of the existing proposed setup, not two
independently sourced proposals. No live Archive or Queue acquisition was run.

| Catalog case | Existing evidence class | Purpose | Result |
| --- | --- | --- | --- |
| `ngc6240-line-diagnostic` | `HYBRID_DIAGNOSTIC` | LINE, including REST input | CSV/TXT workflow and standalone parity passed |
| `ngc6240-continuum` | `REAL_CAPTURE_ENGINEERING` | CONTINUUM | CSV/TXT workflow and standalone parity passed |
| `dual-source-line` | `SYNTHETIC_NUMERICAL` | LINE | CSV/TXT workflow and standalone parity passed |
| `dual-source-continuum` | `SYNTHETIC_NUMERICAL` | CONTINUUM | CSV/TXT workflow and standalone parity passed |

The [acceptance catalog](../../examples/acceptance/catalog.json) owns the source
paths, SHA-256 digests, evidence classes and review states. The test loads that
catalog through the existing checksum validator, including captured-response
validation. It does not duplicate or rewrite the reference ledger. NGC 6240's
Archive capture is real; the proposed setup and diagnostic inputs are not an
observed setup or an independently reviewed duplicate label. All four catalog
cases remain `AWAITING_INDEPENDENT_REVIEW`.

## Verification contract

The test enters through the actual Flask upload and assessment routes:

1. Load the batch form and obtain its session-bound form and submission tokens.
2. Upload two rows, preview them and validate the shared catalog requirements.
   Assessment and Queue pinning are forbidden during preview and validation.
3. Submit the batch and require two completed source records with available
   child reports. Require retrieved Archive/Queue sources and retained
   comparison contexts; matching failures or empty output cannot pass silently.
4. Independently fill and submit the original Single Pointing form for each
   source and purpose. Inputs come from the original catalog form and uploaded
   row, never from the generated batch child request.
5. Compare downloaded request, report and inspection JSON. Only the existing
   four explicitly documented execution-time fields may be normalized. Numeric
   values, source capture dates, criterion reasons, outcomes, associations and
   embedded geometry assessment remain compared.
6. Open each batch visualization and resubmit the original batch token with
   assessment disabled. The duplicate submission must return the existing batch.

Both execution paths share the same pinned Queue object, and a test assertion
requires exactly one source configuration. Archive responses come from the
same checksum-verified replay. This isolates workflow differences from source
changes. The test uses legacy catalog requests; separate existing tests cover
V2 requests, combined purposes, failure isolation and report expiry.

## Reproduce

From the repository root in the installed project environment:

```sh
python -m pytest -q tests/ui/test_batch_catalog_acceptance.py
```

Result: **8 passed in 14.45 seconds**. External HTTP requests are forbidden by
the test fixture. This is server-side form-flow acceptance, not a new interactive
browser run. The [offline browser acceptance](../../examples/acceptance/batch/README.md)
separately records the actual navigation checks.

The combined batch catalog, preview, navigation, routes and orchestration suite
passed **58 tests in 21.15 seconds**. Static analysis and diff whitespace checks
also passed.

## Remaining scientific acceptance

Before treating this feature as scientifically accepted for actual proposals,
obtain a user-approved source list and shared requirements, record the provenance
and expected judgments before evaluating, and have a reviewer examine the
criterion-level outcomes. Record reviewer, date, disagreements and resolutions.
Live acquisition freshness and failure behavior require a separate opt-in run.
Do not promote automated parity or successful retrieval into a duplicate label,
an independent scientific review, or an executable ALMA Science Goal claim.
