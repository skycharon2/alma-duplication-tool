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
