# Archive Mosaic package execution audit

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

A real multi-execution case changes the inventory validation boundary. For IC1954,
Member `uid://A001/X1284/X28b7`, the captured TAP query returns
`uid://A002/Xc63024/X4c8`. The 201,467,904-byte auxiliary package also contains original
MS listobs for `uid://A002/Xc63024/X568e` and `uid://A002/Xc63024/X98b`. Each original
MS has a corresponding `_target.ms` listobs. These are three executions, not six.
All three originals parse as IC1954 with 22 science fields per execution.

This observation demonstrates that this TAP row set is insufficient to enumerate
all executions present in this package. It does not establish why the service
selects these rows, or that every Archive dataset behaves the same way.

## Run against the validated cache

```bash
python -m alma_duplicate.cli.archive_mosaic_package_audit \
  --metadata tests/fixtures/archive/mosaic_multi_execution_2026_10_23/metadata.xml \
  --capture-receipt tests/fixtures/archive/mosaic_multi_execution_2026_10_23/inventory_receipt.json \
  --receipt tests/fixtures/archive/mosaic_multi_execution_2026_10_23/discovery.json \
  --product-row 3 \
  --member uid://A001/X1284/X28b7 \
  --source IC1954 \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/ic1954-package-audit-02 \
  --offline
```

A new output directory is required. Without `--offline`, the existing bounded
auxiliary downloader may acquire a missing package. The original source paths are
never extracted; bounded listobs bytes are saved under SHA-256 filenames.

The audit verifies the TAP capture and Member-bound DataLink receipt, verifies or
downloads the package, inventories supported MS headers, then separately parses
original MS science fields for the requested target. Duplicate original MS candidates,
unrecognized headers, missing originals and parse failures remain unresolved.
Target-only MS records do not substitute for original MS evidence.

Each supported original produces an `archive_mosaic_package_execution_1` document.
Its metadata status is `MEMBER_PACKAGE_BOUND_NOT_TAP_EXECUTION_BOUND`: the Member
comes from the product binding, the ASDM from the MS header, and the target from the
science-field parser. Additional TAP rows are never fabricated. This document is
intentionally not accepted as a verified TAP-bound pipeline execution for reuse.

`package_audit.json` records the full package hash and download provenance, candidate
paths and hashes, TAP ASDMs, additional supported ASDMs, unresolved candidates and
per-execution document hashes. It does not assert whole-Member completeness, merge
FIELD identities, deduplicate coordinates or evaluate duplication policy.

Statuses are ADDITIONAL_EXECUTIONS_FOUND, NO_ADDITIONAL_EXECUTIONS or UNRESOLVED.
The first two exit 0; UNRESOLVED exits 3. Input errors exit 2; inspection failures may
leave partial evidence. Scope remains direct listobs and bounded nested weblogs,
not every file or product belonging to the Member.

## Batch safeguard and validation

New acquisition receipts preserve MS header identities, including nonselected
candidates. A batch with all TAP executions verified but additional package ASDMs
now ends PACKAGE_AUDIT_REQUIRED (exit 3). It does not silently add those ASDMs to the
TAP inventory. Older receipts without header identities cannot establish this audit;
rerun package inspection when using historical evidence.

The real captured six listobs files and receipts are retained under
`tests/fixtures/archive/mosaic_multi_execution_2026_10_23/`; the large tar remains
in the ignored local cache. Offline tests rebuild a small test container from the
captured listobs to test three independent reconstructions, ambiguous originals,
target-only candidates and malformed headers. This synthetic container tests parsing
and orchestration; the separate recorded live package audit supplies download and
nested archive provenance. Existing batch tests retain partial-failure and verified
reuse coverage. Package-bound reuse and missing-output retry are supported by the explicit
batch package-audit mode described below.


## Package-bound batch reuse and retry

```bash
python -m alma_duplicate.cli.archive_mosaic_batch \
  --metadata tests/fixtures/archive/mosaic_multi_execution_2026_10_23/metadata.xml \
  --capture-receipt tests/fixtures/archive/mosaic_multi_execution_2026_10_23/inventory_receipt.json \
  --member uid://A001/X1284/X28b7 \
  --source IC1954 \
  --cache data/cache/archive-auxiliary \
  --package-audit-dir reports/mosaic-dev/ic1954-package-audit-01 \
  --output-dir reports/mosaic-dev/ic1954-package-batch-01 \
  --offline
```

This mode uses the prior audit's validated discovery receipt and selected product.
It cannot be combined with TAP `--reuse-dir` inputs or a DataLink response override.
The capture scope, Member/target, discovery hash and cached archive hash must match.
The cached package is re-inspected and original listobs are re-parsed to validate
saved execution content, hashes and provenance. Reuse saves output regeneration and
network acquisition; it does not skip source validation or archive scanning.

Existing verified documents are copied unchanged and marked REUSED. Missing
execution documents, or supported candidates absent from a prior audit's successful
execution list, are reconstructed from the verified package and marked RECONSTRUCTED.
An existing modified document or listobs is FAILED; it is not silently repaired.
Other executions continue. Old output directories are never overwritten. Global
scope or archive integrity errors abort the run and may leave a partial directory.

The resulting `archive_mosaic_package_batch_1` summary uses
`INSPECTED_MEMBER_PACKAGE_AND_VISIBLE_TAP_ROWS` scope. Its expected ASDM set is the
union of the TAP rows and recognized package headers; unsupported or ambiguous
candidates keep the run INCOMPLETE. PACKAGE_EVIDENCE_COVERED (exit 0) requires every
expected ASDM to have verified evidence and no unresolved candidate. INCOMPLETE exits
3. This remains a single selected-package scope, not whole-Member completeness.

Real IC1954 cache validation reuses all three 22-field executions. A separate copy
of the audit with the X568e output removed verifies recovery: two outputs are reused,
one is reconstructed, and the original audit remains intact. This is a deliberate
missing-output scenario, not a claim that the remote source failed. Tests additionally
cover changed coordinates, modified listobs, unsafe recorded filenames and mismatched
archive hashes. The failed initial development replay is retained separately.
