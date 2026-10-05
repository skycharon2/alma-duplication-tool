# Live browser LINE, TAP and AQ smoke — 2026-10-05

## Baseline and execution

This follow-up to the [continuum smoke](live_browser_aq_smoke_2026-10-05.md)
used the same local server and production baseline
`1538c405c1604c08cfb54e6637155b7eb9223761` (PR #125). Live TAP and live AQ
were enabled; no replay, captured AQ or Queue source supplied this run.
The temporary HTTP observer forwarded production requests unchanged.

The browser submitted a synthetic single-window LINE request for the public
target IRAS_09245-5228. These are engineering inputs, not an actual proposal:

| Field | Value |
| --- | --- |
| Target / geometry | FIXED / SINGLE_POINTING |
| RA / Dec | 141.5461103909849 / -52.70729721185924 deg, ICRS |
| Search radius | 0.0036 arcsec |
| Source / display limit | ARCHIVE / 1 |
| Angular resolution | 3.5 arcsec |
| Purpose | LINE only |
| Requested window centre | 230.538 GHz REST |
| Redshift | Explicitly entered 0 |
| Correlator mode | FDM |
| Planned resolution | 1 km/s |
| RMS at planned resolution | 20 mJy/beam |
| Window list complete | Yes; one synthetic requested window |

Before confirmation of list completeness, validation was READY but reported that
the listed windows could not support an exhaustive negative LINE conclusion.
The completeness checkbox was then selected before Run assessment.

## Result and scientific trace

Run `d098b6b698364967a764409bf0871f67` completed, producing report v4 at
`2026-10-05T08:47:23.849165+00:00`.

- TAP completed with 4 retained/evaluated contexts.
- Live AQ completed one Member query for `uid://A001/X3788/Xc194`, returning
  4 source records; all candidate contexts bound to the exact source identity
  `uid://A001/X3788/Xc194.source.IRAS_09245-5228` and used D = 7 m.
- AQ response SHA-256:
  `1ff8d5d30c16dd5c35fa9376cead57188ad792c06f72d5e4cbdfdf43d90b6978`.
- SPW 28 produced CRITERIA_MET. Position, angular resolution, FDM, frequency
  coverage, resolution compatibility and RMS were all SATISFIED in that pair.
- SPWs 24, 26 and 30 produced CRITERIA_NOT_MET for this requested window.
  No cross-SPW borrowing was needed for the matching pair.

The matching pair retained these backend values:

| Quantity | Value |
| --- | --- |
| Prepared SKY centre | 230.538 GHz |
| Candidate interval | 230.48–230.60 GHz |
| Candidate spectral resolution at requested centre | 0.0917564819529969 km/s |
| Candidate per-component RMS at 10 km/s | 6.3 mJy/beam |
| RMS at planned resolution | 19.92234925906079 mJy/beam |
| Comparison RMS after existing angular treatment | 19.10611373013061 mJy/beam |
| Candidate angular resolution | 3.573980180426332 arcsec |
| Candidate half-power radius | 0.00601383099791523 deg |

The candidate FDM evidence was the existing association-bound channel-count
method (`em_xel=1920`), not a new direct telemetry measurement. The browser's
pair expansion correctly displayed SPW 28 and its associated criteria.

## Downloads and HTTP lifecycle

Report, inspection v3 and request were downloaded through browser links. The
request passed the shared validator; inspection recomputed from the downloaded
report matched exactly. A second report download after refresh was byte-identical.

| Artifact | SHA-256 |
| --- | --- |
| report.json | `c9147942a55f9f1f342ad214552c7c3454344f8fe1c3c155043aced5adb10bcf` |
| inspection.json | `337cf27ddec89da4b69243ca9aeb787a23705d52509a95161c6aa8ef9ce3243f` |
| request.json | `8aeab39857ebc8f59c5a1b84616de5e6c248c51415f08b9c5473716f2c7527c6` |

This run added 8 successful HTTP events: three TAP POST calls and their redirected
GETs, then AQ discovery and one Member POST. All returned HTTP 200. The final TAP
completion preceded AQ discovery. Refresh, expansion and downloads added no
external requests. A run-specific trace was extracted from the shared observer
log; it excludes the earlier continuum run.

Original downloads, verification summary, trace and a browser screenshot are
stored locally in the Git-ignored directory
`reports/live-aq-line-browser-smoke-2026-10-05/`.

## Limits and UI observations

This verifies one successful real-service LINE workflow. It does not establish
independent scientific acceptance, exhaustive Archive coverage, live Queue
parity, nonzero-redshift behavior or future service availability. The small
engineering search radius is not a recommended automatic search policy.
All four local spatial-filter outcomes remained NOT_EVALUATED with
`ARCHIVE_REGION_COVERAGE_NOT_UNIVERSAL`; formal POS-SINGLE was evaluated later.

The report currently hides useful observation/SPW identities behind generic
candidate numbers and nested evidence. Raw status codes and long numeric values
dominate the first view. A future presentation change should expose source/SPW
identity, concise criterion explanations and appropriately formatted display
values, while retaining original numbers and method identities in exports and
expandable evidence. Retrieval automation requires a separate backend policy;
this verification does not change the search radius contract or scientific rules.
