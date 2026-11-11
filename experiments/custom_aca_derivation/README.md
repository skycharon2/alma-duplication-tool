# C1: native OT 7-m geometry versus shared centres

Run from the repository root with this project installed
(`python -m pip install -e .`), plus Astropy, NumPy and Matplotlib:

```bash
python experiments/custom_aca_derivation/plot_c1.py
python experiments/custom_aca_derivation/probe_c1.py
python experiments/custom_aca_derivation/verify_frequency.py
```

Outputs under `reports/custom-aca-c1/` (ignored by Git):

- `c1-7m-comparison.png` and `.svg`: equal-scale three-panel comparison.
- `evidence.json`: native-file hashes, counts, absolute coordinates and plotted offsets.
- `c1-hypothesis-audit.json`: all 16 hypotheses at the recorded 107 GHz.
- `frequency-replay.json`: all hypotheses replayed at 93 and 94 GHz.

The frequency verifier checks every archived file hash, pointing count and
pairwise separation, confirms the representative-only exports are identical,
and compares recomputed hypothesis geometry and scores with the recorded audit.
It also checks reordered, missing and displaced reference matches. A failed
check exits with an error. Run without Python's `-O` option, which disables
assertions. Native exports and archived audits are never overwritten.

The replay verifies reproducibility of these observations, not a general
Custom-to-7-m reconstruction rule. The 94 GHz input remains a hypothesis
consistent with the shifted export, not an independently recorded UI value.

The reference is the controlled 2026-11-02 experiment in
`tests/fixtures/ot_pointings/custom_offsets_2026_11_02/`. The seven exported
12-m centres stand in for the shared-centre approximation: the fixture audit
already established their agreement with reconstructed engineering CSV centres.
The three exported 7-m centres are native OT output, not a prediction from a new
reconstruction algorithm. Both sets receive the same 7-m half-power radius,
93.29158 / 2 arcsec, from the OT's displayed HPBW at 107 GHz.

Beam boundaries are spherical small circles, transformed to a common sky-offset
frame about ICRS (150 degrees, -30 degrees). East is left, north is up, and all
panels have the same angular limits and equal aspect. Faint fills are illustrative
and are not summed sensitivity, validated survey coverage, or duplication results.

This experiment does not change application reports, array inference, or science
rules. The engineering CSV spectral metadata differs from this OT setup; native
coordinate agreement does not establish operational Queue ownership/completeness.

## Next validation

### First independent reconstruction probe

```bash
python experiments/custom_aca_derivation/probe_c1.py
```

This enumerates 16 explicitly provisional hypotheses from the seven manually
entered offsets, 107 GHz and the existing Rectangle generator. It compares
axis-aligned and minimum-area centre rectangles, their four equivalent directed
orientations, and either no padding or one 12-m FWHM added to each dimension.
Padding is a hypothesis, not an established OT rule. Predictions are generated
before reading the OT 7-m output. All hypotheses, including failures, are saved
in `reports/custom-aca-c1/c1-hypothesis-audit.json`.

Result: none passes 0.001 arcsec. Axis-aligned cases produce 1 or 4 points.
The best three-point case (minimum-area rectangle, PA 135 degrees, FWHM padding)
has a maximum residual of about 4.7461 arcsec. Minimum-area selection here applies
to input centres; it is not evidence that OT minimizes the same quantity.

The native three points have pairwise separations approximately 54.840855 arcsec,
whereas the nominal 7-m Nyquist spacing at 107 GHz is 47.665416 arcsec. The observed
separation is numerically consistent with that formula at approximately 93 GHz.
This does NOT establish that OT used 93 GHz. Check the original project's actual
spectral setup, representative frequency, any mosaic spacing configuration and
export freshness before changing an algorithm. The fixture's displayed 107 GHz
and HPBW are retained as recorded; the discrepancy is not silently corrected.

Priority next OT check: reopen or independently recreate C1, record spectral
setup and displayed representative frequency immediately before each export,
then export both arrays afresh. Keep previous files unchanged. A second controlled
frequency case will distinguish a stale/mismatched export from a spacing rule.

Update 2026-11-10: this live check is now recorded in
`tests/fixtures/ot_pointings/custom_frequency_2026_11_10/README.md`. The UI showed
a 93 GHz first SPW alongside the 107 GHz representative frequency. A valid
representative-only change left centres unchanged; a continuum frequency shift
changed them. At 93/94 GHz, one candidate matches both exports. This supersedes
the suspicion that the old output necessarily had a stale frequency, but does
not yet establish a general OT grid-frequency or rectangle-construction rule.

The exhaustive one-to-one assignment is deliberately limited to at most eight
points. Reordered-reference, missing-point and displaced-point checks verify the
comparison distinguishes matches from mismatches. This is an experiment, not a
production reconstruction method or a general-purpose matching implementation.

1. Implement an independent Custom-to-7-m predictor; do not use the three reference
   output coordinates as inputs. Match counts and coordinates without relying on
   row order, initially using the existing 0.001 arcsec tolerance subject to export
   precision.
2. Acquire new independent OT exports for internal-shape changes, translations,
   asymmetric rotations (30 or 45 degrees), and point-order permutations. Change
   one factor at a time; identical coordinate extrema alone do not establish an
   identical freely oriented minimum enclosing rectangle.
3. Vary representative frequency and retain the actual spectral setup. Keep
   ACA-only semantics as a separate validation case.

For every new case retain exact input offsets, source frame and centre, array
configuration, representative sky frequency, native absolute-coordinate exports
for both arrays, and OT screenshots/counts. Do not substitute a visual overlap
check for one-to-one spherical coordinate matching.
