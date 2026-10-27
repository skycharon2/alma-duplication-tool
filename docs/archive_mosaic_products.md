# Archive Mosaic Product Discovery

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

## Scope

This increment discovers product links for a known Archive Member using the
DataLink metadata endpoint. It supports explicit live requests and offline replay,
retains original response bytes, and reports source binding and access diagnostics.
It does not download products, follow service descriptors, extract listobs files,
or evaluate Mosaic duplication.

The existing local reconstruction entry is documented in
[Archive Mosaic backend](archive_mosaic_backend.md). Product discovery supplies a
preceding acquisition stage; it does not yet invoke that entry.

## Interface

`clients.archive_products.discover_archive_products(member_ous_uid, ...)` returns
three values: a typed discovery result, captured response bytes (when available),
and the requested URL. An optional ASDM identifies the intended execution but does
not narrow the Member request or establish that a product contains that execution.
An injectable transport supports deterministic tests.

`parse_archive_products(raw, member_ous_uid=..., asdm_uid=...)` performs offline
parsing. The supported input is a VOTable 1.3 namespace document with one results
resource, one link table, and TABLEDATA encoding. Other layouts are rejected.
Missing QUERY_STATUS is allowed for DataLink responses; any provided status must
be OK. Inventory completeness is never inferred from successful parsing.

## Discovery and identity

Every returned row must carry exactly the requested Member ID. A mismatched ID
invalidates the response instead of silently filtering rows. Repeated products
remain separate and retain their row indices. No preferred product is selected.

| Declared semantics | Recorded role |
| --- | --- |
| `#documentation` | Documentation |
| `#auxiliary` | Auxiliary candidate, contents not inspected |
| `#progenitor` | Progenitor product |
| `#this` | Dataset |
| Other values | Other, original semantics retained |

Rows containing only a service reference remain service references. Row errors,
unsupported access URLs, missing access routes, and reported authorization failures
remain visible. Original error text and service descriptors are retained in the
raw response. Successful metadata discovery does not establish product access.

All products retain `pointing_content=NOT_INSPECTED` and
`asdm_binding=NOT_ESTABLISHED`. An auxiliary archive is a candidate for subsequent
inspection, not proof that a listobs file exists inside it. In particular, the
response does not yet supply a verified package-internal listobs path.

## Commands

Run from the repository root with the project installed. The parent output directory
must exist; each receipt directory must be new.

Offline replay of the existing 7m response:

```bash
python -m alma_duplicate.cli.archive_products \
  --member uid://A001/X15aa/Xe5 \
  --asdm uid://A002/Xfb8480/X4f37 \
  --response docs/research/mosaic/evidence/case_E_datalink.xml \
  --output-dir /tmp/mosaic-products-7m-replay
```

Explicit live metadata discovery for the 12m sample:

```bash
python -m alma_duplicate.cli.archive_products \
  --member uid://A001/X1465/X3f4 \
  --asdm uid://A002/Xeaae1d/X1a2 \
  --live \
  --output-dir /tmp/mosaic-products-12m-live
```

Each receipt contains `discovery.json` and, when available, `response.xml`.
The JSON records the request URL, request times for live requests, response hash,
byte count, HTTP status when available, and discovery results. Offline replay
records its input path and processing time without inventing historical acquisition
times. Oversized responses retain only the captured prefix and explicitly set
`capture_truncated=true`; its hash describes that prefix, not the full response.

Exit codes: 0 for discovery without issues or a successfully parsed empty table;
3 for discovery issues, invalid responses, or remote failures; 2 for local input,
configuration, or output errors. An existing receipt is never overwritten. A local
failure after directory creation may leave an incomplete receipt directory.

## Transport limits

Only the three configured official Archive origins are accepted for live discovery.
The client requests `/datalink/sync?ID=...`, disables redirects, caps captured data
at 2,000,001 bytes to detect the 2 MB limit, and uses a 30-second socket timeout.
The socket timeout is not a total workflow deadline. Product URLs are recorded
but never requested. Authentication, retries, mirror failover, and science-product
downloads are outside this increment.

## Validation evidence

On 2026-10-23, explicit live metadata requests returned:

| Sample | Member | Product records |
| --- | --- | ---: |
| SPT0303-59, 7m | `uid://A001/X15aa/Xe5` | 6 |
| NGC5248, 12m | `uid://A001/X1465/X3f4` | 7 |

Original responses and receipts are preserved under
`tests/fixtures/archive/mosaic_products_2026_10_23/`. Both responses contain an
auxiliary candidate. No product URL was followed. Initial requests from the
restricted network environment failed; the subsequent requests with network
access succeeded. These observations do not establish general service availability.

The live receipts were generated before the optional `http_status` result field
was added; their original bytes are preserved. Current live calls record that field,
while offline parsing does not invent an HTTP status.

```bash
python -m pytest -q tests/unit/test_archive_products.py
python -m pytest -q
```

Recorded local validation on `ff5a098` plus the two uncommitted backend increments:
25 product-discovery tests passed; 36 tests passed across both new modules; the full
Python suite passed with 2260 tests and 12 skipped. Python compilation also passed.
Ruff was unavailable in the environment.

Tests replay both new captures and three earlier Member responses, check receipt
hashes, and cover identity mismatches, malformed or oversized input, overflow,
multiple candidates, empty results, row errors, authorization flags, transport
failures, and overwrite protection. Default tests perform no remote requests.

## Next increment

Inspect the discovered products using the previously explored retrieval route to
establish the actual listobs location. Add bounded download and package extraction,
then call the existing local parser. Preserve product-to-Member/ASDM evidence and
package-internal paths before reconstructing a broader Mosaic object. Complete
Member execution coverage remains a separate requirement.
