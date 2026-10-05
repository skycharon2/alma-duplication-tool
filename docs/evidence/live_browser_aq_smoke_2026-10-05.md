# Live browser TAP and AQ smoke — 2026-10-05

## Scope and baseline

A browser form submission reached the production TAP client, then the production
AQ client, shared assessment and report v4 on merged baseline
`1538c405c1604c08cfb54e6637155b7eb9223761` (PR #125).
No production code was modified for this check.

The local server enabled `LIVE_ARCHIVE=True` and `LIVE_AQ=True`, equivalent to
`ALMA_UI_LIVE_ARCHIVE=1` and `ALMA_UI_LIVE_ARCHIVE_AQ=1`. Replay, captured AQ,
Queue CSV and saved report directories were explicitly unset. A temporary
transport observer logged HTTP method, URL without query parameters, timestamps
and status; it forwarded real requests unchanged and did not record credentials,
headers or response bodies. No mock transport or replay supplied these results.

## Browser input

The public target came from the existing `non_solar_mixed_names` engineering
sample. Scientific requirements below are synthetic test inputs.

| Field | Input |
| --- | --- |
| Target | IRAS_09245-5228 live AQ engineering smoke |
| Type / geometry | FIXED / SINGLE_POINTING |
| RA / Dec | 141.5461103909849 / -52.70729721185924 deg, ICRS |
| Search radius | 0.0036 arcsec |
| Sources / display limit | ARCHIVE / 1 |
| Purpose | CONTINUUM |
| Angular resolution | 1 arcsec |
| Representative frequency | 230 GHz SKY |
| Aggregate RMS | 0.1 mJy/beam |
| Continuum setup declaration | At least two usable windows wider than 1.8 GHz |
| Detailed windows | None |

The page accepted the input as valid and READY. Startup, form editing and
validation generated no observed external HTTP requests.

## Observed result

Run `02d9e03d9bfb460f9ba2e3d30f43b756` completed and generated its report at
`2026-10-05T08:36:30.098334+00:00`.

- TAP: COMPLETED; expected, retrieved, retained and evaluated counts were all 4.
- Display limit remained 1 while all 4 contexts were evaluated and available in
  the browser report. The report had one browser page.
- TAP query hash: `0c9cc5804256c2553aff289c74cd1879f6bad94d05956f0af1ff3155472b4dfc`.
- AQ: LIVE / COMPLETED; one planned Member and one completed Member query,
  `uid://A001/X3788/Xc194`, returning 4 source records.
- AQ response SHA-256: `e23556df4bea16be37523a569602c828b8268d3c60df15d5d32da5d54962d187`.
- All 4 contexts bound to the exact source observation ID
  `uid://A001/X3788/Xc194.source.IRAS_09245-5228`, with label `7m`, component
  `ACA_7M`, method `archive_source_array_1` and diameter 7 m.
- POS-SINGLE used `archive_pos_single_3` and computed SATISFIED with that diameter.
- Continuum branches were CRITERIA_NOT_MET for these test requirements; the
  report's whole-search assessment remained NOT_AGGREGATED.

The transport observer recorded 8 completed HTTP events, all status 200:
3 TAP POST calls and their 3 redirected GET calls, followed by AQ properties
discovery and one AQ Member POST. The last TAP completion preceded the first
AQ request. Refreshing the report and downloading its files did not add events.

## Export verification

The browser downloaded report, inspection v3 and request JSON. A second report
download after refresh was byte-for-byte identical. Recomputing inspection v3
from the downloaded report exactly matched the downloaded inspection. The
downloaded request remained valid and searchable under the shared validator.

| Download | SHA-256 |
| --- | --- |
| report.json | `47d6a6eaf580ead40cf15dfb431bb59503d16d116947371ad486d27273705496` |
| inspection.json | `8b9b1337d4b629515ce84c6957de43210efdb269471bee0fb177cd8a0805308f` |
| request.json | `2e12e4dfa3430ba3e2ec23dbcf649d189205bca860cce86e37fe05a874c35785` |

Local copies, the transport trace and a verification summary are retained under
`reports/live-aq-browser-smoke-2026-10-05/`, which is Git-ignored. The downloaded
files preserve report provenance; raw external HTTP response bytes were not
captured by this smoke.

## Limits

This is a successful point-in-time engineering check of one fixed-target
continuum request. It does not establish a reviewed proposal decision, exhaustive
search coverage, future service availability, live LINE/Queue validation or
mixed-array/TP scientific acceptance. Local spatial filtering recorded all 4 rows
as NOT_EVALUATED and `ARCHIVE_REGION_COVERAGE_NOT_UNIVERSAL`; completed retrieval
does not establish a search-wide absence of duplication. Multi-page browsing,
failed/empty AQ and run isolation remain covered by offline regression tests,
not by this single-page live run.
