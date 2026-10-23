# Independent 12m Pipeline Validation

These records cover NGC5248, Member `uid://A001/X1465/X3f4`, ASDM
`uid://A002/Xeaae1d/X1a2`, on 2026-10-23.

- `metadata.xml`: original live TAP response selecting one explicit identity row.
- `metadata_receipt.json`: request, timestamps, HTTP status, size, hash, and scope.
- `initial_limit_failure.json`: successful download followed by rejection of the
  195,903,625-byte nested weblog under the earlier 100 MB member limit.
- `acquisition.json`: subsequent successful inspection from the verified cache
  using bounded streaming for nested weblogs.
- `listobs.txt`: unmodified selected archive member bytes.
- `comparison.json`: all 11 science fields match the prior local reference.

The selected discovery response and receipt remain in
`../mosaic_products_2026_10_23/12m/`. The 250,724,352-byte auxiliary tar is retained
only in the ignored local cache. Original and `_target.ms` listobs candidates are
both recorded; only the exact original MS header is selected.

The old experimental TAP file was reserialized without QUERY_STATUS. It remains
unchanged and is rejected by the unified pipeline. The new response preserves
server status, but its TOP 1 query provides identity evidence only, not a full
SPW or Member execution inventory. No independent scientific verdict is claimed.
