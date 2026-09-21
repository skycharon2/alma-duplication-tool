# Independent reference ledger for the acceptance catalog

Reference version 1; prepared 2026-09-21 against PR #73 (`a3d2923`).
These are transparent arithmetic references and engineering expectations, not
invented human reviews. Every delivered case is AWAITING_INDEPENDENT_REVIEW;
reviewer, review date and review record are null. No genuine proposal request
with an independently reviewed real-world duplication label was supplied.

## Raw evidence and input identity

The catalog pins each request, this document, capture manifest and Queue CSV by
SHA-256. Manifests additionally pin every unmodified raw VOTable response. Capture
time and endpoint come from those manifests, not the date of an acceptance run.
Both guide captures have synthetic endpoints and identifiers. The NGC6240 capture
is real; its proposed requests are engineering test inputs. Neither capture
status COMPLETE nor an acceptance PASS establishes current service availability.

Guide A raw fields: `examples/confirmed_continuum/archive/response-2.xml`, zero-based
TABLEDATA rows 0–3. Row 0 selects Member `uid://SYNTHETIC/Xguide/X0`, ASDM
`uid://SYNTHETIC/Xexecution/X0`, Source `GuideA`, SPW 0, parsed component 1.
All rows have frequency 240 GHz, spatial_resolution .45 arcsec and 12 m array
labels. Rows 0/1/2/3 have aggregate sensitivity .15/.21/missing/.15 mJy/beam.
Row 3 has RA 201.373 degrees; the others have 201.3665; Dec is -43.0185.

Guide B raw fields: `examples/confirmed_line/archive/response-2.xml`, rows 0/1.
Both select Member `uid://SYNTHETIC/Xguide/X0`, ASDM `uid://SYNTHETIC/Xexecution/X0`,
Source `GuideB`; SPWs are 0/1, each selecting component 1 from its own raw row.

| Raw field | SPW 0 | SPW 1 |
| --- | --- | --- |
| frequency | 225.1 GHz | 240 GHz |
| frequency_support interval | 224.8–225.4 GHz | 239–241 GHz |
| component resolution | 500 kHz | 1000 kHz |
| component sensitivity @10km/s | .4 mJy/beam | .8 mJy/beam |
| em_xel | 1920 | 128 |
| spatial_resolution | .25 arcsec | .25 arcsec |
| cont_sensitivity_bandwidth | .15 mJy/beam | .15 mJy/beam |
| s_ra / s_dec | 201.3665 / -43.0185 degrees | same |

These fields were inspected directly from the saved VOTables. The calculations
below use those raw scalars and the request files, not evaluator outputs.
Expected report paths locate the corresponding context and component explicitly.

## Guide A arithmetic

Proposed angle .30 arcsec, representative SKY frequency 230 GHz, aggregate RMS
.10 mJy/beam; four declared USABLE windows each 1.875 GHz.

- Two or more widths satisfy 1.875 > 1.8.
- Angular factor .45/.30 = 1.5 <= 2.
- Frequency factor 240/230 = 24/23 <= 1.3.
- Aggregate RMS limit = 2 × .10 = .20 mJy/beam. Rows 0 and 3 pass RMS;
  row 1 fails (.21 > .20); row 2 lacks evidence.
- Position uses great-circle separation and candidate half-power radius:
  `r = .5 × 1.13 × 299792458/(240e9 × 12)` radians.
  The radius is about 12.13 arcsec. Rows 0–2 are about 4.34 arcsec from the
  proposed (201.365, -43.019); row 3 is about 21.13 arcsec away.

Thus branches in raw-row order are MET, NOT_MET, INDETERMINATE, NOT_MET.
The absent row-2 RMS must remain candidate evidence, not a request input demand.

## Guide B arithmetic

`230.538 / (1 + .024) = 225.134765625 GHz`. This lies in SPW 0 and outside SPW 1.
For SPW 0, `299792.458 × .0005 / 225.134765625 = .665806671767778 km/s`.
That is finer than the planned 20 km/s. Mode is FDM by the confirmed operational
1920-channel mapping; SPW 1 is TDM by the 128-channel mapping.

The requested RMS is .30 mJy/beam, angular resolution .30 arcsec:

```text
sigma_at_plan = .4 × sqrt(10/20) = .282842712474619 mJy/beam
sigma_comp = .282842712474619 × (.30/.25)^2
           = .4072935059634514 mJy/beam
limit = 2 × .30 = .60 mJy/beam
```

The candidate radius at 225.1 GHz is about 12.93 arcsec; position is inside.
The angular factor is 1.2. All six SPW-0 conditions pass. SPW 1 fails FDM and
coverage even if its RMS were favourable. No values may be borrowed from SPW 0.

## Explicit variants

| Case | Independent expected effect |
| --- | --- |
| missing-line-rms | Remove only the associated requested RMS. SPW 0 becomes unknown; SPW 1 stays false due to FDM/coverage. |
| coarse-line-resolution | Plan .1 km/s. SPW 0 .6658 km/s and SPW 1 about 1.3316 km/s are too coarse; both resolution conditions fail and RMS calculations remain null. Both branches are false. |
| multiple-line-windows | Add an independently declared FDM SKY center at 240 GHz with its own .30 RMS / 20 km/s. SPW 0 passes the original pair; SPW 1 remains TDM. SPW-0 branches true, SPW-1 false; four pairs remain visible. |
| mixed-intents | Use those two explicit FDM windows, each declared USABLE 1.875 GHz, plus representative 230 GHz and setup aggregate RMS .10. Both candidates satisfy continuum; LINE remains true for SPW 0 and false for SPW 1. |
| source-not-provided | Add Queue selection without a file. Archive Guide B outcomes persist; Queue is NOT_PROVIDED; evaluation exit code is 3, not a no-duplicate verdict. |

The mixed input explicitly supplies per-window RMS associations; the form must
never create such associations implicitly merely because both intents are selected.

## Real-capture engineering regressions

`ngc6240-continuum` uses the original fixed request and the original Archive
manifest plus the 13-row Queue fixture. Expected retained/evaluated 157, shown 1;
Archive continuum 91 false / 53 unknown; Queue 13 unknown. No aggregate RMS is
supplied. These are the PR #73 engineering regression counts, not independent
scientific labels for 157 candidates.

`ngc6240-line-diagnostic` copies only intents, windows, sensitivities and redshift
from Guide B. It **keeps the NGC request's 500 mas angular resolution**, coordinates,
search options and representative frequency. Archive LINE expectation: 96 false /
48 unknown; Queue 13 unknown. These counts are the supplied PR #73 diagnostic
baseline and are explicitly labelled HYBRID_DIAGNOSTIC.

A previous diagnostic also copied Guide B's .30 arcsec angular resolution. Its
RMS correction differs by `(.50/.30)^2 = 25/9`; its branch/RMS counts cannot be
compared as if the request were identical. The catalog pins the complete input.
No reviewed real-case result is inferred from either artificial request.

## Independent arithmetic on one real captured component

Capture: `tests/fixtures/archive/ngc6240/response-2.xml`, acquired
2026-09-15T10:34:03.425096+00:00 from `https://almascience.eso.org/tap`.
Zero-based raw row 8: Member `uid://A001/X5a3/X18c`, ASDM
`uid://A002/Xb4da9a/X69a`, Source `ngc6240`, SPW 25. Its exact second support
component is `[223.93..225.80GHz,1938.48kHz,1.4mJy/beam@10km/s,90.8uJy/beam@native, XX YY]`.
The row has em_xel 960, spatial_resolution .489938228111276 arcsec,
frequency 224.86771911423784 GHz, is_mosaic F and only DA/DV 12 m antennas.

Using the diagnostic request's .50 arcsec angle and the raw numbers above,
independent Decimal arithmetic (45 digits, no project imports) gives:

| Quantity | Reference value |
| --- | --- |
| Planned sky center | 225.134765625 GHz, inside the second component |
| Candidate velocity resolution | 2.5813058341768045 km/s, <=20 |
| Smoothed RMS | .9899494936611665 mJy/beam |
| Angular-corrected RMS | 1.0310278394309026 mJy/beam, >.60 |
| Spherical separation from request | .7089752391 arcsec |
| Candidate half-power radius | 12.9475001020 arcsec |

Position, ANGULAR, FDM, coverage and resolution pass; RMS fails. The context
LINE result is false. Using .30 arcsec instead would multiply this RMS by .36,
explaining the earlier differing positive diagnostic. The catalog checks the
full association, component index, individual outcomes and intermediate values.
This independently checks raw-field association and arithmetic on real data;
the proposal is still artificial and the case has no human review sign-off.

## Completing real-case review

Add the actual proposal request and immutable source capture; retain capture time,
endpoint and hash. Identify the exact Member/ASDM/Source/SPW/component, copy the
raw values and units into a review record, and calculate the expected values
independently of production rule functions. State tolerances, uncertainty and
expected unknowns. Only after a person supplies reviewer/date/record should the
case metadata become REVIEWED. Preserve disagreements as comparison differences;
never overwrite expected values automatically from a generated report.
