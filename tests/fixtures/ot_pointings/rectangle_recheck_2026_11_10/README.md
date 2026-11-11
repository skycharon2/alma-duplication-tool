# Brief live Rectangle recheck, 2026-11-10

Cycle 13 web OT, MOSAIC_P2B_OT_TEST / SG-R100 / SG-RECTANGLE-TEST.
Read-only geometry inspection and native download; no geometry/spectral changes
or proposal submission. Source ICRS RA 150 deg, Dec -30 deg; zero centre offsets;
rectangle p=100 arcsec, q=70 arcsec, PA=0 deg. Displayed representative frequency
107 GHz, 12-m HPBW 54.42009 arcsec, spacing 0.51093 beam units (rounded display).
OT shows 10 pointings for 12-m and 5 for 7-m.

The original native download `pointings-7m-3.txt` is preserved as
`ot-7m-absolute.txt`. Production generation uses the full-precision Nyquist
12-m spacing at 107 GHz, 27.804826215407775 arcsec, scaled by 12/7 for 7-m.
All five fresh 7-m coordinates match one-to-one within 0.001 arcsec; maximum
residual approximately 2.43e-7 arcsec. No rounded UI value was fitted to output.

Safari again saved only a 7-m file despite the 12-m display selector. This run
does not claim a fresh 12-m coordinate export. Instead, the independent historical
D3 fixture (`tests/fixtures/queue/rectangle_d3_reference.json`, nonzero offsets
and PA=30 deg) was replayed against production: 10/10 12-m and 5/5 7-m matched,
maximum residuals approximately 1.85e-7 and 4.30e-7 arcsec respectively.
`audit.json` records counts, spacings, residuals and the fresh file hash.

The separately named RECT_TEST_D_DEC30_OFFSET source was inspected briefly and
currently has different coordinates from historical D3; it was not treated as
the original D3 configuration or edited to recreate it.

Validation: `python -m pytest -q tests/unit/test_queue_rectangle_grid.py`:
21 passed. No changes to production code. This confirms the tested ICRS/default
spacing cases, not every coordinate system, non-default spacing, or operational
CSV convention. The Custom grid-frequency observation is not applied to Rectangle.
