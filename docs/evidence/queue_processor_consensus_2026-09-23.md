# Queue processor-equivalence measurement, 2026-09-23

Method `queue_processor_equivalence_1`, delivered in PR #76. This is a dated
measurement of one pinned snapshot, not general mode recovery or scientific approval.
The [experiment](../experiments/queue_processor_consensus.md) owns assumptions.

## Pinned snapshot result

Snapshot SHA256: `8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
Source date 2026-03-03; 3200 rows, 16216 regular SPWs. These are conditional
comparison-mode counts, not duplication verdicts or exact-configuration counts.

| Profiles / required families | FDM | TDM | UNKNOWN | Consensus |
| --- | ---: | ---: | ---: | ---: |
| Reference / all applicable families | 15857 | 269 | 90 | 99.444993% |
| Reference / requested arrays | 15871 | 269 | 76 | 99.531327% |
| Including export compatibility / all applicable families | 15933 | 269 | 14 | 99.913666% |
| Including export compatibility / requested arrays | 15947 | 269 | 0 | 100% |

The 14 additional unresolved mappings are DOUBLE 1000 MHz / 2.2578125 MHz
4x4 signatures, all with UseTP=false. The other 76 require the provisional
15.999 response. SINGLE is covered by synthetic tests but absent from this
snapshot. Most snapshot SPWs are custom pointings; whole-snapshot success is
not single-point scientific acceptance. Inspect the separate single-field counts.


Single-field subset: 459 SPWs. Reference/requested-array view: FDM 215, TDM 168,
UNKNOWN 76 (83.442266%). Whole-snapshot percentages do not describe single-field
coverage. Compatibility/requested-array view reaches 100% only with the export
compatibility assumption on this snapshot; enumeration remains incomplete and
formal_mode remains UNKNOWN. No live service claim is made.


## Preserved execution artifact and reproduction

The preserved execution used code commit `10d9add1085fed4e64f47979ff589fc3b6cfff6b`. Its tree equals the
PR #76 merge tree (`13c41d5`); the locally applied commit `e656791` is the
corresponding delivered implementation. The original output directory was
`tmp/processor-census-final/` in the delivery workspace, not a repository input.
The delivered `ALMA_Queue_Processor_Consensus_Delivery_2026-09-23.zip` contains
that report as `census/summary.json`.

Original summary SHA256: `712f688a2db9d3e340fdaefccc2013d64191dd26aaa3f21c1a06f8e1be28537a`.
This documentation follow-up also supplies the unchanged summary as
`queue_processor_consensus_original_summary.json` in its delivery bundle.
The report's artifact hashes identify its original SPW/configuration outputs;
those large outputs are in the earlier census bundle, not committed here.

To generate a new report from an already available pinned Queue snapshot:

```bash
python -m alma_duplicate.cli.queue_processor_census \
  --queue-csv "$ALMA_QUEUE_CSV_SNAPSHOT" \
  --output-dir reports/queue-processor-reproduction \
  --require-pinned-snapshot
```

Set the environment variable to an existing file and use a new output directory.
A new run is a reproduction, not the preserved execution artifact. Compare
snapshot, method, counts, reasons and artifact hashes; claim byte-identical
summary reproduction only after comparing its SHA256. No unrecorded environment
or execution timestamp is asserted by this added provenance note.
