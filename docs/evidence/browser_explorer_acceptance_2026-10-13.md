# Browser-to-explorer acceptance after PR #139 — 2026-10-13

## Baseline and scope

Baseline: `f3e15f568f5f014789dd023bd236e5c270f9e096`, merged PR #139.
The working tree was clean before verification. A fresh localhost application
used live Archive TAP and post-TAP AQ, the official Queue snapshot, AUTO retrieval
and the default 1 GiB / 20-run / 24-hour temporary storage settings.

Four requests were entered, validated and submitted through the browser. Their
new text reports and single-pointing explorers were opened in sequence. All
inputs were valid and READY, with one purpose and one source per run.
No runtime code or scientific methods were changed. No commits, branch changes,
staging operations or pushes were performed.

Inputs repeat the [four-workflow inputs](browser_single_point_acceptance_2026-10-12.md#inputs).
The [machine-readable record](browser_explorer_acceptance_2026-10-13.json)
preserves the exact requests, run identities, source provenance, numerical
checks, timings and file hashes. Generated window IDs differ between browser
sessions; they are not scientific differences.

The Queue snapshot is dated **2026-03-03**, SHA-256
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
This pass did not refresh the observing queue. Its local filename contains a
different date; the recorded snapshot metadata establishes its provenance.

## Results

| Workflow | Expected object recovered | Met / not met / indeterminate | Click to saved view | Retained files |
| --- | --- | --- | ---: | ---: |
| Archive CONTINUUM | PKS1830-211, 2021.A.00028.S, Member `uid://A001/X2df9/X1b`, SPWs 25/27/29/31 | 16 / 320 / 0 | 64.6 s | 2.14 MiB |
| Archive LINE | IRAS_09245-5228, 2024.1.00408.S, Member `uid://A001/X3788/Xc194`, SPW 28 | 1 / 3 / 0 | 49.8 s | 0.13 MiB |
| Queue CONTINUUM | NGC6240, 2024.1.00750.S, physical CSV line 42 | 1 / 118 / 3081 | 13.0 s | 36.16 MiB |
| Queue LINE | circinus_galaxy, 2025.1.00344.S, physical CSV line 97, SPW 3 | 1 / 118 / 3081 | 36.2 s | 84.77 MiB |

Archive CONTINUUM contains four matching Members overall. The counts describe
comparisons, not duplicated projects or a verdict on every SPW in a Member.
All four runs preserved the context display identities, branch outcomes, truth
values and branch method versions of the [PR #134 regression](browser_regression_pr134_2026-10-12.md).
Acquisition IDs and generated input window IDs were allowed to differ.

Timing starts immediately before clicking Run assessment and ends at the saved
`view.json` modification time. It includes source access, evaluation and storage;
it excludes subsequent page rendering and downloads. These are individual local
measurements, not latency guarantees. The four retained runs total 123.21 MiB.

## Scientific and visualization checks

- Both Archive acquisitions completed TAP and live AQ. The expected target,
  Member, ASDM and SPW identities remained bound together in the report and plot.
- Archive LINE retained D = 7 m, candidate interval 230.48–230.6 GHz and
  comparable RMS `6.3 * sqrt(10 / 1) = 19.92234925906079 mJy/beam`.
- Queue CONTINUUM used four 1875 MHz NOMINAL windows without the researcher
  confirmation shortcut. `continuum_setup_4` found four qualifying usable
  windows. Candidate aggregate bandwidth was 7500 MHz and RMS was 0.008 mJy.
- Queue LINE matched SPW 3. Its plotted interval
  182.3526779652115–182.8214779652115 GHz is 468.8 MHz wide, from the
  candidate's nominal 500 MHz width. Requested and reference spectral widths
  were 0.564453125 MHz; requested and comparable RMS were 5.5. The report
  retained the different source mJy and requested mJy/beam labels.
- Independent arithmetic checked the matching beam radii and position tests.
  Every saved request passed the shared validator. Rebuilding inspection from
  each report reproduced the stored inspection.
- All 19 plotted comparisons across the four reports were checked against
  their saved criteria: radius, separation, D, beam frequency, requested frequency
  and candidate interval or representative frequency. Matching pair SPWs and
  context identities agreed. CONTINUUM displayed frequency markers; LINE
  displayed the recorded candidate interval.
- Queue unresolved results remained visible, including 2940 custom mosaic
  pointings, 140 rectangular mosaics and one spectral scan. They were not
  listed as matches or silently treated as non-duplicates.

## Browser and lifecycle checks

- Four sequential runs remained independently readable. Returning to the first
  report after the fourth preserved its 16 comparisons and four Members.
- Archive all-comparison pages 1/2 of 17 and Queue LINE pages 1/2 of 160 worked;
  returning to matching results restored the expected groups.
- Clicking Archive continuum comparison 4 and selecting it with Enter highlighted
  SPW 31 in both plots and its detail panel. Position and frequency zoom changed
  coordinate ranges; Reset restored them. The Queue LINE detail link returned
  to its specific `pair-3167-2` text comparison.
- Desktop (1440 px) showed both panels side by side. At 390 px, the page remained
  390 px wide and panels stacked; the frequency plot used its scroll container.
- Technical records stayed hidden on default report pages. Form/report links
  worked. With no operator report directory configured, Existing reports showed
  its explicit empty state; this list is not a history of temporary browser runs.
- Queue LINE report, inspection and request files were downloaded through the
  browser and matched the saved files byte for byte. The first Archive report
  download also matched after the later runs. All four runs' stored report,
  inspection, request and view hashes remained unchanged after revisits.
- No browser console errors or warnings were observed in the checked tab.
- `python -m pytest -q tests/ui`: **271 passed in 26.50 s**. This includes
  deterministic multi-page, missing-evidence, no-requery, download, input and
  lifecycle regression cases. These automated cases are separate from live
  browser observations.

Local reports, plot data, verification scripts and screenshots are preserved in
the Git-ignored `reports/browser-acceptance-pr139/` directory. Runtime links are
temporary and depend on the localhost service and report retention.

## Finding and limits

One non-blocking presentation issue remains: Queue LINE's selected row correctly
names SPW 3, but the detail identity list labels the context's full `1, 2, 3, 4`
window list as “SPW”. A later small UI change should distinguish **Selected SPW**
from **Windows in this Queue record**. The pairing and plotted interval were
verified and are correct; this pass does not change scientific results.

All positive result sets fitted on one Member page and one plot page; additional
matching-result and plot pages were covered by automated tests, not new live
samples. No live expiry, eviction, restart, source-failure or concurrent-user test
was forced. REST/redshift, other unit combinations, mixed purposes and broader
scientific scope were not newly exercised with live inputs here.

The four sampled single-pointing paths pass engineering acceptance on this
baseline. Self-retrieval does not replace independent scientific review of real
proposals. The next delivery step is the restricted supervisor preview defined
in the [roadmap](../roadmap.md), with fresh-source and deployment checks performed
for the chosen environment.
