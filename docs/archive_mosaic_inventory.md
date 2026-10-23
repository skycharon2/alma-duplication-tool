# Archive Mosaic execution inventory

The inventory reconciler checks saved science Mosaic TAP rows against verified
single-execution pipeline directories. It reports expected ASDM identifiers,
verified acquisitions, and missing executions for one Member and one target.

Repeated rows for spectral products collapse by ASDM within the same project,
Member, and target. Fields retain their execution-local identities. No pointing
coordinates are merged across executions.

## Usage

```bash
python -m alma_duplicate.cli.archive_mosaic_inventory \
  --metadata docs/research/mosaic/evidence/case_E_tap.xml \
  --member uid://A001/X15aa/Xe5 \
  --source SPT0303-59 \
  --execution-dir reports/mosaic-dev/7m-execution-pipeline-01 \
  --output reports/mosaic-dev/7m-inventory-01.json
```

Repeat `--execution-dir` for additional executions in the same Member/target scope.
Omit it to report all supplied ASDM identifiers as missing. The output parent must
exist; an existing report is never overwritten. No network requests are made.

The metadata requires a successful, non-overflowing TABLEDATA response with the
same identity columns as the single-execution pipeline. Empty results, mixed
Members, mixed targets, and inconsistent project identifiers are rejected.

Each execution directory must contain its pipeline evidence files. Reconstruction
is repeated from the saved listobs and acquisition receipt, then compared with the
saved execution JSON and provenance. Duplicate inputs, unexpected ASDMs, changed
coordinates, or inconsistent receipts fail reconciliation rather than contributing
to successful coverage. Directory paths and execution hashes are recorded for audit.

## Status and scope

- `SUPPLIED_INVENTORY_COVERED`: every ASDM in the supplied rows has verified evidence.
- `MISSING_EXECUTIONS`: the report lists the ASDM identifiers still missing.
- Invalid evidence produces an error and no report.

Exit codes are 0 for supplied coverage, 3 for missing executions, and 2 for invalid
input or filesystem errors.

Successful TAP status alone does not prove an exhaustive query. A TOP 1 response
can be successful and still omit executions. Both coverage outcomes therefore
retain `MEMBER_COMPLETENESS_NOT_ESTABLISHED` and `NOT_EVALUATED`. This is a saved-row
reconciler, not a live inventory acquisition or Member-wide completeness claim.
The [TAP inventory capture](archive_mosaic_discovery.md) command records the fixed
Member/target query and validates response limits. Supply its receipt with
`--capture-receipt` to establish captured visible-query scope; Member-wide
completeness remains unestablished.

## Validation

Offline tests cover missing executions, repeated spectral rows, empty and overflowing
responses, mixed identities, unexpected and duplicate execution inputs, tampered
source evidence, modified reconstructed coordinates, and CLI overwrite protection.
The captured 7m pipeline provides the verified execution fixture; a synthetic second
ASDM checks missing coverage without claiming another observed execution.
