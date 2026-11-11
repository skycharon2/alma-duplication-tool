# C1 live OT frequency experiment, 2026-11-10

Native Safari UI session, Cycle 13 web OT, existing test project
MOSAIC_P2B_OT_TEST / SG-C100 / OT_CUSTOM_GEOMETRY_TEST. No proposal submitted.
Build identifier was not exposed. Source ICRS (150 deg, -30 deg), zero radial
velocity, proper motion and parallax. Seven unchanged input offsets in arcsec:
(0,0), (15,0), (-15,0), (0,15), (0,-15), (10,10), (-10,-10).

## Observations and native downloads

| Case | Continuum Sky Frequency | Representative Frequency | 7-m HPBW displayed | 7-m centres |
| --- | --- | --- | --- | --- |
| Baseline | 100 GHz | 107 GHz | 93.29158 arcsec | 3 |
| Representative only | 100 GHz | 106.5 GHz | 93.72957 arcsec | 3, unchanged |
| Continuum shifted | 101 GHz | 108 GHz (automatic) | 92.42777 arcsec | 3, changed |
| Restored | 100 GHz | 107 GHz (automatic) | original | original offsets |

At baseline, the spectral table visibly showed baseband centres 93, 95 and
105 GHz; the representative frequency was 107 GHz. The 93 GHz value was read
from the UI, not inferred solely from exported coordinates. The full shifted
SPW table was not captured: 94 GHz is the expected shifted first centre and is
independently consistent with the output spacing, not a separately recorded UI
measurement in this run.

An attempted representative value of 105 GHz was rejected as outside the
106.06249--107.93751 GHz allowed window. It was corrected to the valid 106.5 GHz
before any experimental export. No scientific result uses the invalid setting.

`baseline-7m.txt` and `representative-106p5-7m.txt` are native Absolute/Degrees
downloads and are byte-identical. `continuum-101-7m.txt` is the shifted native
download (Safari named it pointings-7m-2.txt). Original downloads were copied,
not edited. `audit.json` contains hashes, counts, separations and hypothesis scores.

`historical-12m-reference.txt` is explicitly the older 12-m download, not a fresh
export. The live UI confirmed all seven unchanged inputs. Attempts to export
with the 12-m selector active produced 7-m downloads in this session, so no
fresh 12-m export is claimed. This UI/export discrepancy needs separate checking.
The old reference is consistent with the existing 2026-11-02 fixture.

Control/Performance was inspected: Custom angular resolution 1.6--2.4 arcsec,
LAS 45 arcsec, Standalone ACA unselected; simultaneous 12-m/ACA set to No.
That simultaneous flag does not mean ACA is absent. This run did not independently
establish the full requested-array scheduling configuration; it measured the
7-m grid exposed by OT. No scheduling/array settings were changed.

## Quantitative results

- Baseline pairwise separation: approximately 54.840855 arcsec.
- Shifted separation: approximately 54.257442 arcsec.
- Ratio: 1.01075268814, consistent with 94/93.
- Changing only representative frequency leaves the native coordinates unchanged
  while changing the displayed beam size.

Re-evaluating the existing exploratory hypotheses at 93 and 94 GHz yields a
match in both cases for the minimum-area centre rectangle, directed PA 135 deg,
one 12-m FWHM total dimension padding, and the existing triangular-grid generator.
Maximum residuals are approximately 4.15e-8 and 4.00e-8 arcsec, below 0.001 arcsec.
These are numerical residuals, not astrometric accuracy claims. All tested
hypotheses and failures are retained in the audit.

This supports spectral-setup-dependent grid spacing in this controlled continuum
case. It does not distinguish first SPW from lowest-frequency SPW, establish the
padding/pruning/orientation rule uniquely, or validate arbitrary Custom shapes.
Several rectangle sizes can generate the same small discrete grid. The reference
was used for hypothesis scoring; this is exploratory agreement, not blind general
validation. Scientific status remains NOT_EVALUATED.

## Final state and next experiment

Continuum restored to 100 GHz, representative frequency restored to 107 GHz;
the original three 7-m offsets were observed again, then the UI was left on the
12-m selector with all seven original inputs. No pointings, source coordinates,
or array configuration were edited. No production code was changed during acquisition.

Next isolate the grid-frequency selection using a spectral setup where first
and lowest windows differ (if supported), then vary shape/translation/rotation
with the spectral setup held fixed. Do not replace production frequency policy
with a universal minimum-SPW rule based on this case alone.
