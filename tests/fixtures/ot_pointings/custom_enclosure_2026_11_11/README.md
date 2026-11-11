# Centre-area versus footprint-area discriminator

## Scope and acquisition

One bounded experiment on 2026-11-11 through Safari, Cycle 13 web OT,
MOSAIC_P2B_OT_TEST / SG-C100 / OT_CUSTOM_GEOMETRY_TEST. No proposal submitted.
The new input differs from the restored seven-point baseline only at the second
point: (15,0) becomes (-30,-10) arcsec. Full inputs are in `predictions.json`.
Source remains ICRS (150,-30) degrees, zero radial velocity LSRK, zero proper
motion/parallax. Single Continuum 100 GHz, TDM, Dual, representative 107 GHz
were confirmed in the UI and not changed. Displayed 7-m HPBW: 93.29158 arcsec.

Before editing OT, an offline search on a 5-arcsec lattice for this one-point
change selected a case whose objective minima differ. No OT output entered
case selection. `predictions.json` was saved before the OT edit/export.
All four directed orientations of each rectangle were retained, rather than
choosing an orientation using the reference output.

A: minimize L*W for the pointing centres, then add one 12-m FWHM to each total
dimension. B: minimize (L+FWHM)*(W+FWHM), then use that padded rectangle.
Both use the same 93 GHz frequency hypothesis, 62.612361638 arcsec total
padding, 54.840855393 arcsec 7-m spacing, existing Rectangle grid generator,
and no extra pruning. The candidate angles come from a monotone-chain convex
hull; a separate 0.005-degree angular scan checks that no sampled interior
angle has a lower objective. The scan is a numerical check, not a general proof.

## Frozen predictions

Angles below use the generator convention, modulo 90 degrees:

| Quantity | A: centre area | B: padded area |
| --- | ---: | ---: |
| Base angle (deg) | 50.194428908 | 21.801409486 |
| Centre-only dimensions (arcsec) | 23.046638388 x 43.532539177 | 29.711254108 x 34.353637563 |
| Centre offset (arcsec) | (-5.901639344, -4.918032787) | (-9.827586207, +0.431034483) |
| Centre area (arcsec squared) | 1003.278688525 | 1020.689655172 |
| Padded area (arcsec squared) | 9092.266061677 | 8952.251650667 |

These objectives genuinely prefer different rectangles, rather than equivalent
angle representations of the same rectangle.

## Observation and comparison

OT generated three 7-m points. `ot-7m-absolute.txt` is the unchanged native
Absolute/Degrees export, downloaded as `pointings-7m-3.txt`. Safari's first
attempt reported `Unknown.csv: Cannot move file`; one retry succeeded. No UI
rounded coordinates were substituted for the native file. Hashes of both the
native export and frozen predictions are retained in `audit.json`.

- A at directed PA 140.194428908 degrees: 3/3 matched one-to-one, maximum
  spherical residual 5.76637547e-8 arcsec.
- Other directed A orientations: either four points or a coordinate mismatch.
- B: two orientations predict four points; the two three-point orientations
  have maximum residuals 21.989738418 and 26.350564896 arcsec.
- Matching tolerance is 0.001 arcsec. Tiny residuals represent numerical
  agreement, not an astronomical accuracy claim.

Conclusion: this case supports choosing the centre-area rectangle before
padding over choosing the padded-area rectangle, under the common fixed
frequency/padding/grid assumptions. It does not establish a unique padding
amount, all degenerate/tied-direction choices, or OT's complete pruning rule.
A different footprint definition or selection algorithm has not been tested.
No production reconstruction or duplication verdict was modified.

## Reproduce

With this project, NumPy and Astropy installed, run from repository root:

```bash
python experiments/custom_aca_derivation/compare_enclosure_objectives.py --score
```

This regenerates and verifies the frozen predictions, scores all eight models,
and writes `reports/custom-aca-enclosure/audit.json` without overwriting the
archived evidence. Run without `-O`. The command without `--score` is only for
initial prediction creation and deliberately refuses to overwrite the saved file.

## Final OT state

The second point was restored to (15,0), all other six inputs unchanged.
Sexagesimal source display was restored. The unchanged continuum and
representative frequencies were verified afterward. The page was left on
Spectral Setup; no further experiments were performed.
