# Queue mode census — measured 2026-09-22

This is an engineering census of the repository-pinned source capture, not a live
Queue query, a reviewed scientific-case label, or an approved Queue rule.
The source description says **2026-03-03**; filenames suggesting a later date
must not replace that source date.

- Snapshot SHA256: `8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
- 3,200 raw and typed rows; 3,199 regular rows; 1 unexpanded spectral scan.
- 16,216 regular row/SPW occurrences; 39 raw numeric signatures.
- 65 repeated-content rows remain counted. The denominator is not unique setups.
- Method: `queue_correlator_configuration_match_1`, `PROVISIONAL`.
- Catalog: `blc_queue_signature_catalog_1`; [scope and provenance](../queue_mode_census.md).

## Results and their conditions

| Count view | FDM | TDM | UNKNOWN | Unique % |
| --- | ---: | ---: | ---: | ---: |
| One conditional configuration, including supplied export compatibility | 15,707 | 269 | 240 | 98.519980 |
| Mode agreement across conditional configurations, including supplied export compatibility | 15,947 | 269 | 0 | 100.000000 |
| Mode agreement using retrieved reference numerical profiles only | 15,871 | 269 | 76 | 99.531327 |
| Source-bound processor evidence available from CSV alone | 0 | 0 | 16,216 | 0.000000 |

The 100% figure is conditional signature coverage. It does not mean a uniquely
recovered physical setup or a source-bound mode. The 76 additional matches depend
on the supplied N16 response coefficient 15.999, not the exact coefficient in
the two retrieved OT versions. They are labelled separately in every artifact.

## All configuration ambiguities

All 240 occur in Cycle 12 DOUBLE polarization. All compatible modes are FDM,
but the unique-configuration result remains UNKNOWN as required by the contract.

| Raw bandwidth MHz | Resolution MHz | Occurrences | Distinct explanations |
| ---: | ---: | ---: | --- |
| 62.5 | 0.06103515625 | 128 | 2x2 full resource N4 rounded profile; 2x2 half resource N1 |
| 125 | 0.1220703125 | 2 | 2x2 full resource N4 rounded profile; 2x2 half resource N1 |
| 250 | 0.564453125 | 108 | 2x2 quarter resource N2; 4x4 full resource N2 |
| 62.5 | 0.14111328125 | 2 | 2x2 quarter resource N2; 4x4 full resource N2 |

For the first ambiguity, 62.5/4096 * 4 = 62.5/2048 * 2 = 0.06103515625 MHz.
For the third, 250/1024 * 2.312 = 0.564453125 MHz for either resource/quantization
explanation. These arithmetic checks do not call the evaluator or the matcher.
Missing baseband, resource and quantization information prevents choosing one.

## The single-field subset matters more for the next delivery

| Geometry | SPWs | Unique configuration FDM/TDM/UNKNOWN | Reference-only mode FDM/TDM/UNKNOWN |
| --- | ---: | --- | --- |
| SINGLE_FIELD | 459 | 279 / 168 / 12 | 215 / 168 / 76 |
| CUSTOM_POINTING | 14,994 | 14,994 / 0 / 0 | 14,994 / 0 / 0 |
| RECTANGULAR_MOSAIC | 727 | 402 / 100 / 225 | 627 / 100 / 0 |
| UNSPECIFIED_WITH_OFFSET | 36 | 32 / 1 / 3 | 35 / 1 / 0 |

Project `2025.1.00383.L` contributes all 14,994 custom-pointing occurrences,
92.464233% of this SPW denominator. Consequently, the overall 99.53% reference
match rate conceals the **83.442266%** reference-only mode match rate in the
459 single-field SPWs. All 76 export-compatibility cases are single-field.
Including that hypothesis gives single-field mode consensus FDM=291, TDM=168,
UNKNOWN=0; unique configuration still has 12 UNKNOWNs.

Array request flags partition SPWs into 15,702 with both 7-m and TP requested,
71 with 7-m only, and 443 with neither flag set. None is a raw processor ID.
The census does not turn the false/false case into an authoritative BLC identity.

## Independent raw-field count ledger

The following table was counted directly from physical CSV rows and occupied
SPW columns, with numeric signature labels assigned separately from the matcher.
It contains no generated expected values from `derive_queue_mode`. Its FDM/TDM
labels are **conditional on the catalog scope**, including the supplied N16
compatibility examples; they are not independent measurements of source mode.
The raw-field tally is FDM=15,947 and TDM=269. It cross-checks enumeration and
classification wiring; it cannot independently validate the missing processor
association or the N16 exporting-software semantics.

| Project year | Polarization | Raw BW MHz | Raw resolution MHz | Count | Conditional mode |
| --- | --- | ---: | ---: | ---: | --- |
| 2024 | DOUBLE | 125.0 | 0.14111328125 | 4 | FDM |
| 2024 | DOUBLE | 1875.0 | 0.9765625 | 6 | FDM |
| 2024 | DOUBLE | 1875.0 | 1.12890625 | 9 | FDM |
| 2024 | DOUBLE | 1875.0 | 1.9384765625 | 3 | FDM |
| 2024 | DOUBLE | 1875.0 | 31.25 | 42 | TDM |
| 2024 | DOUBLE | 1875.0 | 36.125 | 12 | TDM |
| 2024 | DOUBLE | 500.0 | 0.484619140625 | 2 | FDM |
| 2024 | FULL | 1875.0 | 15.6240234375 | 4 | FDM |
| 2025 | DOUBLE | 1000.0 | 0.564453125 | 33 | FDM |
| 2025 | DOUBLE | 1000.0 | 2.2578125 | 14 | FDM |
| 2025 | DOUBLE | 125.0 | 0.070556640625 | 1324 | FDM |
| 2025 | DOUBLE | 125.0 | 0.1220703125 | 2 | FDM |
| 2025 | DOUBLE | 125.0 | 0.14111328125 | 23 | FDM |
| 2025 | DOUBLE | 1875.0 | 0.9765625 | 7 | FDM |
| 2025 | DOUBLE | 1875.0 | 1.12890625 | 1510 | FDM |
| 2025 | DOUBLE | 1875.0 | 1.9384765625 | 4 | FDM |
| 2025 | DOUBLE | 1875.0 | 3.904296875 | 16 | FDM |
| 2025 | DOUBLE | 1875.0 | 31.25 | 196 | TDM |
| 2025 | DOUBLE | 1875.0 | 7.81201171875 | 63 | FDM |
| 2025 | DOUBLE | 1875.0 | 7.812011718750001 | 1 | FDM |
| 2025 | DOUBLE | 250.0 | 0.1220703125 | 1 | FDM |
| 2025 | DOUBLE | 250.0 | 0.14111328125 | 94 | FDM |
| 2025 | DOUBLE | 250.0 | 0.2822265625 | 70 | FDM |
| 2025 | DOUBLE | 250.0 | 0.564453125 | 108 | FDM |
| 2025 | DOUBLE | 500.0 | 0.244140625 | 24 | FDM |
| 2025 | DOUBLE | 500.0 | 0.2822265625 | 35 | FDM |
| 2025 | DOUBLE | 62.5 | 0.030517578125 | 18 | FDM |
| 2025 | DOUBLE | 62.5 | 0.0352783203125 | 4616 | FDM |
| 2025 | DOUBLE | 62.5 | 0.060577392578125 | 1323 | FDM |
| 2025 | DOUBLE | 62.5 | 0.06103515625 | 128 | FDM |
| 2025 | DOUBLE | 62.5 | 0.070556640625 | 6474 | FDM |
| 2025 | DOUBLE | 62.5 | 0.14111328125 | 2 | FDM |
| 2025 | FULL | 1875.0 | 1.953125 | 2 | FDM |
| 2025 | FULL | 1875.0 | 15.6240234375 | 8 | FDM |
| 2025 | FULL | 1875.0 | 2.2578125 | 9 | FDM |
| 2025 | FULL | 1875.0 | 3.876953125 | 4 | FDM |
| 2025 | FULL | 1875.0 | 62.5 | 19 | TDM |
| 2025 | FULL | 250.0 | 0.244140625 | 4 | FDM |
| 2025 | FULL | 500.0 | 0.564453125 | 2 | FDM |

The two spellings 7.81201171875 and 7.812011718750001 remain separate raw
signatures; the explicit 1e-12 representation tolerance maps them alike.

## Reproduction and checks

```bash
python -m alma_duplicate.cli.queue_mode_census \
  --queue-csv "$ALMA_QUEUE_CSV_SNAPSHOT" \
  --require-pinned-snapshot \
  --output-dir reports/queue-mode-census
python -m pytest -q tests/unit/test_queue_mode.py tests/integration/test_queue_mode_census.py
python -m pytest -q tests/acceptance/test_queue_csv_snapshot.py tests/acceptance/test_queue_mode_snapshot.py
```

Measured checks: focused 44 passed; both opt-in full-snapshot tests passed;
default suite 1124 passed / 11 skipped; Ruff F passed. Default skips are nine live
checks and two external-snapshot checks. No live TAP availability claim is made.
The source CSV is caller-owned and is not added to this patch.
