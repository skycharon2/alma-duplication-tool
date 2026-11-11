# Bounded Custom ACA experiment, 2026-11-11

Two experiments were performed through the Cycle 13 web OT in Safari, project
MOSAIC_P2B_OT_TEST / SG-C100 / OT_CUSTOM_GEOMETRY_TEST. No proposal submitted.
Production code and scientific assessment were not changed.

## 1. Frequency discriminator

Original seven offsets: (0,0), (15,0), (-15,0), (0,15), (0,-15),
(10,10), (-10,-10) arcsec. Source ICRS (150 deg, -30 deg), radial velocity
0 km/s LSRK, RADIO, zero proper motion and parallax.

Temporarily switched Single Continuum to Spectral Line. Added BB1 manually at
105 GHz rest, BB2 at 93 GHz rest; both full fraction, 1875 MHz bandwidth,
1.129 MHz smoothed resolution (2-bit), names TEST105 and TEST93; BB3/4 empty.
The spectral table displayed sky frequencies 104.99816 and 92.99837 GHz.
Representative rest frequency was 105 GHz. The target field page displayed
104.99555 GHz representative sky frequency and 95.07260 arcsec 7-m HPBW.
These different sky conversions are recorded as observed, not silently equated.
The experiment did not establish which source's velocity/frame conversion is
used internally for grid spacing. Source flux/linewidth validation remained
incomplete; this is a geometry experiment, not a schedulable proposal.

Export: `line-first105-lowest93-7m.txt`, copied unchanged from pointings-7m.txt.
Three points; first pair separation 54.8418160611 arcsec. The corresponding
Nyquist frequency inferred diagnostically is 92.9983709116 GHz.

Scoring the existing 16 geometric hypotheses gives best maximum residuals:

| Frequency hypothesis | Maximum residual (arcsec) |
| --- | ---: |
| First rest 105 GHz | 4.14621447 |
| First displayed sky 104.99816 GHz | 4.14565145 |
| Target representative sky 104.99555 GHz | 4.14485278 |
| Lowest rest 93 GHz | 0.000635466 |
| Lowest displayed sky 92.99837 GHz | 0.000000314 |

The lower-frequency centre is strongly supported against first/representative
frequency in this configuration. Both rest and displayed-sky lower frequencies
pass the existing 0.001 arcsec tolerance; the much smaller sky residual is
suggestive, not a complete proof of the frame-conversion policy. This does not
prove a universal frequency rule for every spectral mode.

## 2. Asymmetric shape discriminator

Restored continuum 100 GHz, TDM, Dual, representative frequency 107 GHz.
Changed only the second offset from (15,0) to (25,5) arcsec. Before editing OT,
all 16 predictions at 93 GHz were saved in `asymmetric-predictions.json` using
the existing hypothesis generator, without inspecting the new OT output.

Export: `asymmetric-7m.txt`, copied unchanged from pointings-7m-2.txt.
Three points. Exactly one of the 16 precomputed hypotheses matches at 0.001
arcsec tolerance: minimum-area centre rectangle, directed generator PA
141.3401917459 deg, one 12-m FWHM added to each total dimension. Maximum
one-to-one spherical residual is 6.59576e-8 arcsec (numerical agreement, not
an astrometric accuracy claim).

Matched rectangle parameters, in the existing generator's angle convention:

- Centre offset: (+3.3536585366, +2.6829268293) arcsec.
- Centre-only dimensions: 36.7008340438 x 23.4260642833 arcsec.
- Padding: 62.6123616380 arcsec added to each total dimension, equivalent to
  31.3061808190 arcsec on each side.
- Padded dimensions: 99.3131956818 x 86.0384259213 arcsec.
- 7-m spacing: 54.8408553926 arcsec.

Axis-aligned padded alternatives either produce four rather than three points,
or have maximum residuals of 22.27--29.75 arcsec. The unpadded alternatives
produce one point. Thus the tested axis-aligned models fail and the rotated
minimum-area model survives a new asymmetric case. Alternative padding values
can yield identical discrete grids: this does not uniquely identify padding,
orientation tie-breaking for all shapes, or redundant-point pruning.

## Reproduction and final state

With the project and experiment dependencies installed, run from repository root:

```bash
python experiments/custom_aca_derivation/verify_minimal.py
```

The script replays predictions and writes `reports/custom-aca-minimal/audit.json`.
Native files, saved predictions and their SHA-256 hashes are retained here.
Run without `-O` so assertions remain active.

After the two experiments, the original seven input offsets were restored and
verified in the UI. Continuum 100 GHz / representative 107 GHz was restored.
The page was left displaying the original 12-m input list (7 points, 3 derived
7-m points). No array configuration was changed. Exploration stopped after these
two cases; this evidence supports a candidate model, not unrestricted production
replacement of the shared-centre approximation.
