# Archive Mosaic footprint input readiness

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

This layer binds execution-local science FIELD/scan/SPW links to verbose listobs
spectral-window and antenna tables. It crosschecks optional official AQ source array
labels against the execution's reported dish diameters. It does not compute beam
sizes, select a representative frequency, merge fields or calculate coverage areas.

## Usage

```bash
python -m alma_duplicate.cli.archive_mosaic_readiness \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json \
  --output reports/mosaic-dev/ic1954-readiness-03.json
```

The package execution loader revalidates local receipt bindings and reparses the
original listobs. A second hash check binds setup parsing to those same bytes.
The output must be new. CLI exit 0 means a diagnostic report was generated, including
reports with NOT_READY fields; input integrity and filesystem errors exit 2.
No live acquisition occurs in this command. Omitting `--array-catalog` leaves the
array unknown rather than inferring it from a dish diameter or project name.

## Spectral evidence

The supported layout explicitly declares MHz for Ch0/CtrFreq and kHz for ChanWid/
TotBW. The parser requires exactly one table with the declared number of unique
SPWs and preserves the raw row, reference frame, signed width, channel count, total
bandwidth, reported centre, BBC and correlations. Other units/layouts, missing rows,
duplicate IDs and nonfinite values are rejected without fallback interpretation.

The approximate interval is derived from the first channel, signed channel width
and channel count under a uniform-grid assumption, with half a channel width at
each end. Negative widths are retained and endpoints sorted. These are rounded
listobs values, not exact channel edges or usable/unflagged bandwidth. Source
centre and bandwidth values are preserved separately, not replaced by the estimate.

Each field retains scan-specific SPW links and all referenced windows, including
channel averages and auxiliary windows. `explicit_full_res_spw_ids` identifies the
literal FULL_RES source labels without combining IDs across executions or asserting
an observing-mode policy. Missing referenced SPWs keep that field NOT_READY.
Non-TOPO frames require further frequency-frame handling and are not silently
converted. No single effective frequency is chosen.

## Array and antenna evidence

The verbose antenna table requires explicit metre units and its declared number
of unique antenna IDs. Diameter sets distinguish 7M, 12M, MIXED and OTHER dish
classes. This is execution-table evidence, not per-field active-baseline membership;
a 12 m dish alone does not distinguish the main array from total power.

The existing `load_archive_array_catalog` loader verifies captured AQ response
hashes, endpoint and query completeness. Binding requires the exact AQ source ID,
Member and source name, one unambiguous record and supported labels. A single
7m/12m label must agree with the execution diameter set. Mixed source labels remain
MIXED, total power is unsupported, conflicting diameters are CONFLICT and absent or
ambiguous evidence is UNKNOWN. Labels and diameter evidence remain separately
reported with their scopes and hashes.

## Readiness semantics

EVIDENCE_BOUND means required table evidence and a consistent source array label
are available for that field. It is not permission to compute a scientific footprint.
NOT_READY lists explicit evidence gaps or conflicts. Every field still reports
NOT_EVALUATED for footprint and lists outstanding choices: frequency/SPW policy,
exact-edge requirements, primary-beam model/threshold and field antenna participation.
The report preserves all execution-local coordinates and scan associations. It does
not consume candidate grouping as a reason to merge frequency or array evidence.

IC1954 validation binds 66 records across three executions. Each original listobs
contains 24 SPWs; the ON_SOURCE FULL_RES IDs are 16, 18, 20 and 22. Each execution
lists eleven 7 m antennas. The separately captured official AQ source label is 7m.
All 66 field inputs bind successfully, while footprint evaluation remains deferred.
Tests exercise signed widths, unit conversion, missing references, malformed and
duplicate SPWs, changed evidence, conflicting/mixed/unknown arrays and execution-local
SPW identity with different frequencies.

CASA documents listobs as a summary with spectral-window and verbose antenna tables;
selection can affect its contents, so it is not an unqualified full-MS inventory:
[CASA listobs documentation](https://casadocs.readthedocs.io/en/v6.2.0/api/tt/casatasks.information.listobs.html).
