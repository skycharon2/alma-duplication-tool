# Rectangle array validation

Run from the repository root in an environment with this project installed
(`python -m pip install -e .`), plus Astropy, NumPy and Matplotlib:

```bash
python experiments/rectangle_plot/verify_recheck.py
python experiments/rectangle_plot/plot_arrays.py
python -m pytest -q tests/unit/test_queue_rectangle_grid.py
```

The verifier checks the SHA-256 hash and one-to-one spherical coordinate match
of the fresh 2026-11-10 7-m export (five points). The plot independently replays
the historical D3 reference for 12-m (ten points) and 7-m (five points). Both use
a 0.001 arcsec matching tolerance. A failed match exits with an error.

PNG, SVG and recomputed D3 residuals are written to
`reports/rectangle-array-plot/`, which is ignored by Git. Native exports and
the historical audit remain unchanged. Circles illustrate half-power beams;
they are not a sensitivity map. The dashed rectangle is the input rectangle.

See `tests/fixtures/ot_pointings/rectangle_recheck_2026_11_10/README.md` for
the acquisition conditions and export limitations. These checks cover the
recorded ICRS/default-spacing configurations, not arbitrary OT configurations,
CSV spacing conventions, or Custom-to-7-m reconstruction. No production
geometry or report behavior is changed by this experiment.
