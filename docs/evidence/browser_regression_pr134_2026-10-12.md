# Browser regression after PR #134 — 2026-10-12

## Scope

Baseline: `3fff6a8a3b3d09dd5d8b567c4e562f071ae8ef8b`, merged PR #134.
A fresh localhost application used live Archive TAP and AQ, the existing official
3200-row Queue CSV snapshot, AUTO retrieval and the default 1 GiB run-storage
budget. Four requests were entered, validated and submitted in the browser.
All were valid, READY, FIXED / SINGLE_POINTING, with one source and one purpose.
No production code or scientific methods were changed. No commits, branch
changes or pushes were made.

Inputs repeat the [earlier four-workflow verification](browser_single_point_acceptance_2026-10-12.md#inputs).
The [machine-readable record](browser_regression_pr134_2026-10-12.json) contains
the exact submitted requests, run identities, source evidence and file hashes.
The Queue snapshot is dated **2026-03-03**, with SHA-256
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
This is a snapshot regression, not verification of the current observing queue
or its automatic refresh mechanism.

## Results

| Workflow | Expected object recovered | Met / not met / indeterminate | Click to saved view | Retained files |
| --- | --- | --- | ---: | ---: |
| Archive CONTINUUM | PKS1830-211, 2021.A.00028.S, Member `uid://A001/X2df9/X1b`, SPWs 25/27/29/31 | 16 / 320 / 0 | 66.0 s | 2.12 MiB |
| Archive LINE | IRAS_09245-5228, 2024.1.00408.S, Member `uid://A001/X3788/Xc194`, SPW 28 | 1 / 3 / 0 | 53.2 s | 0.13 MiB |
| Queue CONTINUUM | NGC6240, 2024.1.00750.S, physical CSV line 42 | 1 / 118 / 3081 | 11.7 s | 36.16 MiB |
| Queue LINE | circinus_galaxy, 2025.1.00344.S, physical CSV line 97, SPW 3 | 1 / 118 / 3081 | 36.7 s | 84.77 MiB |

Archive CONTINUUM contains four matching Members overall. Counts are comparison
outcomes, not numbers of duplicated projects. A matching SPW does not classify
an entire Member as duplicated. All four reports preserve the same context
display identities and branch outcomes as the earlier saved runs.

Timing uses the browser timestamp immediately before clicking Run assessment
and the filesystem modification time of the completed `view.json`. It includes
source access, evaluation and storage, but excludes subsequent HTML rendering,
downloads and time spent reviewing results. These are individual local samples,
not a latency guarantee or a controlled comparison with earlier page-load times.
File totals include report, inspection, request and view index. All four runs
together used approximately 123.2 MiB, below the default budget.

## Scientific evidence and source checks

- Both Archive runs completed live TAP and AQ. TAP recorded
  `STATUS_THEN_COUNT`, explicit retrieval `OK`, `count_attempted=false` and
  `expected_count=null`; the retrieved counts were 336 and 4. The browser used
  the merged retrieval-first path without claiming that a COUNT query ran.
- Archive LINE retained source-bound D = 7 m and comparable RMS
  `6.3 * sqrt(10 / 1) = 19.92234925906079 mJy/beam`.
- Queue CONTINUUM supplied four 1875 MHz NOMINAL windows, without the researcher
  declaration shortcut. `continuum_setup_4` found four qualifying usable windows;
  candidate aggregate bandwidth was 7500 MHz and aggregate RMS 0.008 mJy.
- Queue LINE matched only candidate SPW 3. The interval was 468.8 MHz wide,
  corresponding to the candidate's 500 MHz nominal width. The page showed
  0.564453 MHz on both sides and comparable/requested RMS values of 5.5.
  Original Queue mJy labels remained distinct from the proposed mJy/beam label.
- Independent arithmetic checked beam radii and the matching position tests.
  Each saved request passed the shared validator; rebuilding inspection from
  each saved report reproduced the stored inspection exactly.
- Queue unresolved counts remained 2940 custom mosaic pointings, 140 rectangular
  mosaics and one spectral scan. These were not presented as matching results
  or missing proposal inputs.

## Browser and storage checks

All four runs completed sequentially. Earlier reports remained readable after
later runs. Archive and Queue LINE all-comparison pages 1 and 2 were navigated,
then switched back to matching results. All positive sets fitted on one result
page; this run therefore did not exercise multiple pages of matching Members.

The CSV LINE input was downloaded through the browser and was byte-identical
to the saved request. All four runs' saved files retained their hashes after
report revisits and pagination. Report and inspection downloads were not
repeated in this pass. Expiry, eviction and restart were not forced.

Full local artifacts, verification script and screenshots are preserved in the
Git-ignored `reports/browser-regression-pr134/` directory. Original active run
links remain temporary and depend on the localhost server staying available.

## Interpretation

The four tested paths passed this integration regression after the performance
changes. No code repair was needed. These self-retrieval cases support a
supervised single-point trial; they do not establish independent scientific
acceptance for all inputs. REST/redshift, other unit combinations, mixed purposes,
mixed arrays, TP, mosaic/moving-target science and source-failure paths were not
newly tested here. Archive completeness remains limited by the recorded AUTO
retrieval scope.
