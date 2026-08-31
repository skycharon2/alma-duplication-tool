# Live Archive TAP smoke test

## Purpose

The live smoke test verifies that the production Archive client can currently
communicate with the ALMA TAP service, receive the declared retrieval schema,
and produce complete query provenance.

It does not validate a fixed Archive row count, a fixed project identifier, or
the formal duplication rules. Archive contents and external-service
availability can change independently of this repository.

## Default test behaviour

The normal test command remains offline:

```bash
python -m pytest -q
```

Tests marked `live` are collected but skipped unless the caller explicitly
passes `--run-live`. This keeps ordinary local tests and pull-request checks
deterministic.

## Run locally

Run only the live Archive smoke test:

```bash
python -m pytest -q -s \
  --run-live \
  tests/live/test_archive_tap_smoke.py
```

To test another compatible endpoint:

```bash
ALMA_TAP_ENDPOINT="https://example.invalid/tap" \
python -m pytest -q -s \
  --run-live \
  tests/live/test_archive_tap_smoke.py
```

## GitHub Actions

The `Live Archive TAP smoke test` workflow uses only `workflow_dispatch`.
After the workflow file is present on the default branch, run it from:

```text
GitHub repository -> Actions -> Live Archive TAP smoke test -> Run workflow
```

It is intentionally absent from `push` and `pull_request` events and therefore
does not block ordinary pull-request checks.

## Assertions

The smoke test requires:

- execution to reach a recognized non-error Archive query status;
- no required-column schema drift;
- COUNT and retrieval query statuses to be recognized;
- non-negative dynamic counts;
- retrieved count to match the number of preserved rows;
- endpoint, ADQL, timestamps, versions, run ID, and query hash provenance.

`COMPLETE`, `OVERFLOW`, and `COUNT_MISMATCH` are accepted as evidence that the
live boundary executed and the completeness contract classified the response.
Only `COMPLETE` permits reconstruction. `ERROR`, including schema drift or
service failure, fails the smoke test and remains a technical outcome rather
than a scientific conclusion.

For a complete, non-empty response, the live closure test also runs the rows
through metadata normalization, identifier parsing, frequency-support parsing,
and deterministic Archive reconstruction.

The pipeline assertions do not require a fixed Archive row count, project ID,
or association count. They verify raw-row preservation, surrogate-row
identity, row-accounting consistency, and at least one reconstructed
association.