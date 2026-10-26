# CASE2 NGC253: Archive pointings for an OT round trip

## Acquisition on 2026-10-26

Project 2018.1.00294.S has two selected NGC253 Members. Exact Member/target TAP
queries returned four spectral metadata rows per Member. The actual auxiliary
packages contain more executions than those TAP rows enumerate:

| Member suffix | Original ASDM suffixes | Science FIELD rows per execution | AQ / antenna cross-check |
| --- | --- | --- | --- |
| X9c3 | Xd40be0/X42e2, Xd5affb/Xf9c, Xed4607/X8155 | 3 each | 12m / 12 m, BOUND |
| X9c5 | Xfeb5e6/X59b7, Xfee03e/X492 | 3 each | 12m / 12 m, BOUND |

Both final package audits report ADDITIONAL_EXECUTIONS_FOUND without unresolved
entries. This is selected-package evidence, not proof of whole-Member completeness.
The preparation attempts and final audits are under
`reports/mosaic-dev/case2-ot-acquisition-02/`; all five separate exports are under
`reports/mosaic-dev/case2-ot-export-01/`. Failed attempts are retained.

The selected TAP-associated executions X42e2 and X59b7 have exactly equal reported
coordinates. Their separate files in `examples/mosaic/case2/` preserve their distinct
provenance. Repeated execution rows have not been pooled into a nine- or six-point
proposal. The exported rows are reconstructed science FIELD centres, not time-series
antenna pointing telemetry or original proposal files.

## OT operation

Start with `examples/mosaic/case2/ngc253-X9c3-pointings.txt`. Create a test target
named `NGC253_CASE2_TEST` and use the 12m array. In the Pointings table, use Import
with this file. It uses the four-column absolute Degrees format captured in the
existing OT experiments. Verify that the table contains three positions, near
RA 11.8878 deg and Dec -25.2884 deg. Export the pointings as Absolute / Degrees and
save the unmodified download for backend round-trip validation.

These are generated test inputs. The current OT application's acceptance and its
actual export precision remain to be checked by that round trip. Do not describe
them as files already exported by OT.

The companion metadata JSON files retain the four candidate TAP rows, field units
and query provenance. Candidate frequency centres are approximately 689.13, 690.89,
692.71 and 694.52 GHz (Band 9). The two Members have angular resolutions approximately
0.066806 and 0.223310 arcsec respectively. These candidate properties are not proposed
requirements; the historical CASE2 inequalities are search thresholds. A final
continuum/line test request must explicitly specify its spectral setup and sensitivity
basis. Position-only acceptance does not require inventing those requirements.

## Reproducible export

```sh
python -m alma_duplicate.cli.archive_pointings_ot \
  --package-audit-dir /path/to/verified/package-final \
  --asdm uid://A002/Xd40be0/X42e2 \
  --output-dir reports/mosaic-dev/new-ot-export
```

The exporter revalidates receipts and reparses listobs through the existing package
loader, requires one explicit ASDM, preserves row order and duplicate coordinates,
and writes the FIELD mapping and hashes beside the file. Output directories must
not already exist.

## Acquisition limits

The auxiliary packages advertise 932341760 and 487395328 bytes. The contained weblogs
are 693039181 and 458362940 bytes. These exceed the default 300 MB download and 250 MB
weblog limits. The package-audit CLI now accepts explicit `--max-download-bytes`,
`--max-weblog-bytes` and `--max-expanded-bytes` overrides, capped at 1 GB, 1 GB and
10 GB respectively. This run used those ceilings. Defaults, download timeout, text
size, entry count, nesting and path checks remain unchanged. Inspection streams the
archives and saves bounded listobs files; it does not extract the original paths.

The general automatic preparation path still uses default budgets. CASE2 therefore
currently needs the explicit package-audit budget override and verified local reuse;
this successful acquisition does not imply that the default automatic live route
can download these large packages. A future automatic resource-budget interface
should preserve explicit configuration and per-candidate failure reporting.

Modern `_targets.ms` and `_targets_line.ms` headers are now recognized as derived
TARGET variants. They never replace original MS evidence or add executions.

## Next acceptance step

Import one three-point file into OT and return its Degrees export. Compare coordinates
and counts against the generated source, then assess the imported proposal against
verified CASE2 coverage. Additional package executions without compatible TAP metadata
must remain excluded from production coverage binding. Candidate search recall and
final duplication criteria remain separate acceptance questions.

## Actual OT round trip and production position acceptance

The user supplied `pointings-12m.txt` after the OT round trip. All three coordinates
and their order exactly match the selected X9c3 source file. The actual bytes are
retained in `tests/fixtures/archive/case2_mosaic_2026_10_26/ot-12m.txt`. The separately
supplied 7m list has different positions and is not used as the CASE2 round-trip fixture.

Offline acceptance restores captured metadata, reparses package listobs, rebuilds
array readiness and invokes the production context assessment and common assessment
entrypoint. Both Members produce four contexts with 3/3 inside and POS-MOSAIC
SATISFIED. Synthetic variants verify 2/3 SATISFIED, while 1/3 and 2/4 retain unknown
because Member completeness is not established. They never become positive. Only
the TAP-bound ASDM contributes coverage; additional package executions stay excluded.
Other request parameters in these position tests are synthetic, so no complete
scientific duplication claim is made.

Run the deterministic acceptance with:

```sh
python -m pytest -q tests/integration/test_case2_mosaic_acceptance.py
```

## Automatic resource-budget configuration

The earlier package-audit-only limitation is now removed: the common evaluate CLI
accepts these optional flags and passes them through preparation to package audit:

```text
--mosaic-max-download-bytes 1000000000
--mosaic-max-weblog-bytes 1000000000
--mosaic-max-expanded-bytes 10000000000
```

The standalone `mosaic_candidate_preparation` CLI accepts the same flags without the
`mosaic-` prefix. The API uses `MosaicResourceLimits`. Defaults remain 300 MB download,
250 MB weblog and 1 GB expanded; limits are per package, not a whole-run quota.
Invalid values are rejected and effective values appear in `preparation.json`.
Timeout, hash, path, nested-depth, text-size and candidate-count checks remain active.

A real-cache preparation replay using captured inventory, DataLink and AQ providers
completed for both CASE2 Members with POINTINGS_PREPARED and EVIDENCE_BOUND. It selected
products automatically and rescanned the actual cached tar files with explicit limits.
The receipt is `reports/mosaic-dev/case2-automatic-budget-01/preparation.json`.
This validates actual cached packages and acquisition orchestration, not a fresh
network retrieval or exhaustive spatial candidate discovery. Live discovery recall
and full continuum/line proposal acceptance remain separate work.
