# Single-point browser workflow verification — 2026-10-12

## Scope and execution

Baseline: `986faa6`, after PR #132. A fresh localhost Flask process ran the
production application with live Archive TAP, live AQ, the complete official
Queue CSV snapshot and the default 1 GiB temporary-report budget. No replay,
captured AQ, candidate truncation or scientific-method changes were used.

All four requests were entered, validated and submitted in the real browser,
including purpose selection, window creation, units and contributor checkboxes.
All inputs were valid and READY. All searches used AUTO. Runs were submitted
sequentially; later runs did not replace earlier reports. Downloads and page
checks also took place while subsequent work was running.

Queue used the existing 3200-row official snapshot **as of 2026-03-03**, not a
fresh download or a statement of today's observing queue. SHA-256:
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.

## Inputs

All targets were FIXED / SINGLE_POINTING. Angular units were arcsec and RMS
inputs were mJy/beam. Each request selected only its tested source and purpose.

| Input | Archive CONTINUUM | Archive LINE | Queue CONTINUUM | Queue LINE |
| --- | --- | --- | --- | --- |
| Target label | CASE1 | IRAS_09245-5228 | NGC6240 | circinus_galaxy |
| RA | 18:33:39.920 HMS | 141.5461103909849 deg | 253.24541666666667 deg | 213.291275 deg |
| Dec | -21:03:39.900 DMS | -52.70729721185924 deg | 2.4010972222222224 deg | -65.339019 deg |
| Angular resolution | 0.23 | 3.573980180426332 | 0.4 | 0.15 |
| Representative / line centre, SKY GHz | 290.420 | 230.53800141830845 | 338.5 | 182.5870779652115 |
| Aggregate / LINE RMS | 0.02 | 19.92234925906079 | 0.008 | 5.5 |
| Planned LINE resolution | — | 1 km/s | — | 0.564453125 MHz |
| Declared LINE mode | — | FDM | — | FDM |

Archive CONTINUUM used the explicit researcher declaration of at least two
distinct windows with usable width greater than 1.8 GHz. This and the selected
0.23 arcsec resolution are engineering assumptions, not a reconstruction of the
complete original CASE1 proposal.

Queue CONTINUUM supplied four SKY centres: 350.4999999999, 348.5000000001,
338.4999999999 and 336.5000000001 GHz. Each width was **1875 MHz NOMINAL**;
all four windows contributed to aggregate RMS and the list was marked complete.
The declaration checkbox was not used for this request.

Each LINE test listed one FDM window, marked complete for that test request.
Redshift and proposed window bandwidth were blank because the input frequency
was SKY. These single-window tests do not reconstruct every original SPW.

## Results

| Workflow | Retained comparisons | Meet / not met / indeterminate | Expected identity recovered | Click to first report |
| --- | ---: | --- | --- | --- |
| Archive CONTINUUM | 336 | 16 / 320 / 0 | 2021.A.00028.S, PKS1830-211, Member uid://A001/X2df9/X1b, ASDM uid://A002/Xfd251c/X7ba5, SPWs 25/27/29/31 | 114–132 s |
| Archive LINE | 4 | 1 / 3 / 0 | 2024.1.00408.S, IRAS_09245-5228, Member uid://A001/X3788/Xc194, ASDM uid://A002/X11e3e46/Xff4a, SPW 28 | About 99 s |
| Queue CONTINUUM | 3200 | 1 / 118 / 3081 | 2024.1.00750.S, NGC6240, snapshot hash + physical line 42 | About 14 s |
| Queue LINE | 3200 | 1 / 118 / 3081 | 2025.1.00344.S, circinus_galaxy, snapshot hash + physical line 97, SPW 3 | About 54 s |

Archive CONTINUUM had four matching Members in total. Matching one or more
SPWs does not mark every observation in a Member as duplicated. Queue identity
was checked using the snapshot hash and physical row, not target name alone.

Both Archive TAP and AQ completed. The Queue report distinguished 2940 custom
mosaic pointings, 140 rectangular mosaics and one spectral scan as unresolved
scope. These are not additional matches or missing proposed-input fields.
Other comparison-method diagnostics can overlap those scope counts.

Timings describe one local run per case and include source access, assessment,
storage and initial navigation, but exclude later exports. Server log times
have one-second precision. The Archive CONTINUUM interval is bounded by report
generation and the later browser observation; it is not an exact stopwatch
measurement. These results do not promise a general response-time limit.

## Numerical and lifecycle checks

- Independent arithmetic verified half-power beam radius from the stored
  candidate frequency and diameter, and separation within that radius.
- Archive LINE used source-bound D = 7 m. Its comparable RMS equalled
  `6.3 * sqrt(10 / 1) = 19.92234925906079 mJy/beam` at identical angular resolution.
- Queue CONTINUUM used `continuum_setup_4`: four qualifying usable widths from
  the nominal inputs, total usable bandwidth 7500 MHz and aggregate RMS 0.008 mJy.
- Queue LINE matched only candidate SPW 3. Its interval width was 468.8 MHz
  from the candidate's nominal 500 MHz, and requested/reference resolution was
  0.564453125 MHz on both sides. Comparable RMS and requested RMS were both 5.5
  numerically. Original Queue mJy semantics were retained, not silently relabeled.
- All exported requests passed the shared validator. Rebuilding inspection from
  each exported report matched the saved inspection exactly.
- After all four runs, each old report and its applicable pagination returned
  HTTP 200. Archive all-comparison pages 1 and 2 were also navigated in the
  browser. Positive result sets fitted on one Member-group page.
- All 12 report/inspection/request exports were downloaded again. Their sizes
  and SHA-256 hashes were unchanged. A browser-clicked Queue LINE request
  download was also byte-identical to the HTTP export.
- All four reports remained retained within the default budget. Expiry and
  restart were not forced during these live checks; their coverage belongs to
  the [storage increment](../matching_report.md#single-copy-browser-storage-2026-10-12).

## Small presentation repair

The Queue LINE resolution row previously displayed planned km/s next to
candidate MHz. It now uses the backend's stored `planned_resolution_mhz` when
the candidate unit is MHz, showing **0.564453 MHz on both sides**. No conversion
or decision is performed by the viewer. Legacy records without that derived
value retain their original operands. Archive km/s displays are unchanged.

The exact saved reports were opened by a fresh read-only application to verify
the repair in a real browser. Focused report presentation, report routes, run
routes and storage tests: **75 passed**. Ruff `--select F` passed. The added test
checks source-record immutability, missing evidence and the Archive fallback.

## Evidence and limits

The [compact machine-readable record](browser_single_point_acceptance_2026-10-12.json)
contains identities, counts, source statuses, timing bounds and all export hashes.
Local full exports, browser snapshots/screenshots, repeated-download checks and
verification scripts are in the Git-ignored directory
`reports/pre-supervisor-2026-10-12/`.

This supports a supervised trial of the four tested single-point workflows.
Self-retrieval is a positive-path integration check, not independent scientific
acceptance of all proposals. This run does not cover REST/redshift input,
all unit combinations, mixed purposes or arrays, TP, mosaic/moving-target
science, source failure, or global completeness of Archive retrieval.
