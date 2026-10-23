# Archive Mosaic execution batches

The batch runner consumes a verified TAP inventory capture for one Member/target.
It discovers Member DataLink products once, selects a unique usable auxiliary tar,
and runs the existing reconstruction pipeline independently for each ASDM. Downloads
reuse the auxiliary cache; no raw science measurement sets are downloaded.

## Offline batch from captured evidence

```bash
python -m alma_duplicate.cli.archive_mosaic_batch \
  --metadata tests/fixtures/archive/mosaic_inventory_2026_10_23/12m/metadata.xml \
  --capture-receipt tests/fixtures/archive/mosaic_inventory_2026_10_23/12m/inventory_receipt.json \
  --member uid://A001/X1465/X3f4 \
  --source NGC5248 \
  --datalink-response tests/fixtures/archive/mosaic_products_2026_10_23/12m/response.xml \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/12m-batch-01 \
  --offline
```

The auxiliary tar must already be cached for this offline command. Without
`--offline`, missing auxiliary products may be downloaded subject to existing limits.
Omit `--datalink-response` to discover products live at the captured inventory origin.

The output directory must be new. It contains the original inventory and capture
receipt, Member product discovery evidence, and one SHA-256-named directory per
execution. Filenames never contain raw ASDM UIDs. Single-row metadata is derived
from the validated inventory for pipeline input; these XML files are not independent
TAP captures. The original inventory hash remains in `batch.json`.

## Reuse and failure handling

Pass `--reuse-dir PATH` once per existing execution to reuse. The inventory identity,
acquisition receipt, extracted listobs, saved execution and provenance are reverified.
If every execution has a reuse directory, neither discovery nor download runs, and
an offline DataLink response is unnecessary. Invalid reuse evidence is reported as
FAILED; the runner does not silently overwrite or reacquire it. Rerun into a new
batch directory without that reuse argument to acquire a fresh result.

Duplicate or unexpected reuse identities fail preflight. Other execution failures
are isolated and processing continues. Multiple usable auxiliary products are
ambiguous and fail new executions rather than selecting an arbitrary package.
Existing validated executions can still be reused if discovery for other executions
fails. Successful directories from an incomplete batch can be passed as reuse inputs
to a later run. Existing batch directories are never overwritten.

`batch.json` records each ASDM as RECONSTRUCTED, REUSED, or FAILED, including its
execution directory, verified execution hash and field count, or failure reason.
It records missing ASDMs after each attempt and ends as VISIBLE_INVENTORY_COVERED
only when every expected execution is verified. Otherwise it ends as INCOMPLETE.
An interrupted run may leave IN_PROGRESS or partial files and should be inspected
before selecting reuse inputs. CLI exit codes are 0 for covered, 3 for incomplete,
and 2 for preflight or filesystem failure.

## Scientific boundary

The Member/target summary references execution-local records; it does not merge
coordinates or FIELD IDs. Two executions can both have FIELD 4 without implying
identical pointings. Member completeness remains unestablished and policy is not
evaluated. Coverage refers only to the captured visible science Mosaic query.

On 2026-10-23 the live NGC5248 inventory returned one ASDM, as did the SPT0303-59
inventory. These are not real multi-execution validation cases. The 12m cached batch
reconstructed 11 fields; the 7m reuse batch verified 19 fields. Synthetic two-execution
tests cover partial failure, identical FIELD IDs, revalidation of reuse, modified
evidence, ambiguous products and overwrite protection. Cross-execution coordinate
aggregation requires separate scientific validation.
