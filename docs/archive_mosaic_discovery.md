# Archive Mosaic TAP inventory capture

The capture command requests all distinct execution identities visible to an
unauthenticated TAP query for one Member and target. The fixed query selects science
Mosaic rows; it has no TOP clause, ASDM filter, or frequency filter. ADQL target
literals are escaped. Only configured official Archive origins are accepted.

## Capture and reconcile

```bash
python -m alma_duplicate.cli.archive_mosaic_discovery \
  --member uid://A001/X15aa/Xe5 \
  --source SPT0303-59 \
  --output-dir reports/mosaic-dev/7m-inventory-live-01

python -m alma_duplicate.cli.archive_mosaic_inventory \
  --metadata reports/mosaic-dev/7m-inventory-live-01/metadata.xml \
  --capture-receipt reports/mosaic-dev/7m-inventory-live-01/inventory_receipt.json \
  --member uid://A001/X15aa/Xe5 \
  --source SPT0303-59 \
  --execution-dir reports/mosaic-dev/7m-execution-pipeline-01 \
  --output reports/mosaic-dev/7m-live-coverage-01.json
```

Each capture requires a new output directory. It records the generated query, URL,
MAXREC, timestamps, HTTP status, raw response hash, byte count, row count and unique
ASDM identifiers. Response bytes are preserved, including unsuccessful responses.
Transport failures have a receipt but no response file. Filesystem failures may
leave a partial directory. Raw oversized responses are retained only up to the
bounded read size, and cannot be accepted as inventories.

No auxiliary products are downloaded. Requests use a 30-second socket timeout,
a 2 MB response bound and MAXREC 10000. Redirects and automatic retries are disabled.
The socket timeout is not a hard total-duration deadline.

## Failure and scope rules

CAPTURED requires HTTP 200, successful QUERY_STATUS throughout the response,
supported TABLEDATA, consistent project/Member/target identities and a row count
strictly below MAXREC. OVERFLOW, ERROR, missing status, malformed XML and the row
limit fail validation. An empty successful response is EMPTY and does not establish
coverage. Capture exits with 0 only for CAPTURED, 3 for unsuccessful acquisition,
and 2 for input or filesystem errors.

When `--capture-receipt` is supplied, reconciliation regenerates the fixed request,
checks response hashes and row summaries, then verifies the execution evidence.
Its scope becomes `CAPTURED_VISIBLE_SCIENCE_MOSAIC_MEMBER_TARGET`. Without a receipt,
the existing saved-row scope remains unchanged. Local hashes establish consistency;
they do not authenticate the remote origin of a manually edited receipt.

A successful capture describes the rows exposed by this query at capture time.
It does not establish private, unpublished, non-science, non-Mosaic, or other-target
coverage. Member completeness remains unestablished and policy remains unevaluated.
Missing executions must be acquired separately before any cross-execution aggregation.

## Recorded validation

On 2026-10-23, the live ESO query for Member `uid://A001/X15aa/Xe5` and
target `SPT0303-59` returned one distinct ASDM, `uid://A002/Xfb8480/X4f37`.
Reconciliation verified the existing 19-field execution with no missing ASDMs.
The raw response and receipt are retained in
`tests/fixtures/archive/mosaic_inventory_2026_10_23/7m/`.

Full Python regression: 2330 passed, 12 skipped. Compilation and whitespace
checks passed. Live validation does not extend the visible-query scope described above.
