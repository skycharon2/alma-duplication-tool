# Queue Mosaic Galactic coordinate model

Project interpretation adopted 2026-11-16. This adds numerical Galactic support
without claiming that the current offset convention is universally OT-equivalent.
No 7-m Custom grid is inferred; [Custom ownership](queue_pointing_ownership.md)
continues to control which array can receive explicit CSV coverage.

## Reference and offset frames

CSV `RA` / `Dec` locate the source in ICRS. `Mos. Coord. = galactic` selects the
axes of the longitude/latitude offsets, not the reference coordinates' frame.
The implementation converts the reference to Galactic with Astropy `SkyCoord`,
applies the offsets there, then converts each resulting point back to ICRS.

The adopted offset convention is local east/north **arc length**: for offsets
`x, y` in arcseconds, separation is `hypot(x, y)` and position angle is
`atan2(x, y)` east of native north. `directional_offset_by` transports that
direction and distance on the sphere. This is not direct addition of arcseconds
to longitude and latitude. Astropy documents the coordinate operation in its
[separation and offsets guide](https://docs.astropy.org/en/stable/coordinates/matchsep.html)
and [SkyCoord API](https://docs.astropy.org/en/stable/api/astropy.coordinates.SkyCoord.html).
Those APIs establish the mathematical operation, not the ALMA CSV semantics.

Custom rows retain their original CSV data, ICRS reference, raw frame label,
Galactic reference and reconstructed ICRS centre. Coverage records identify the
Galactic method rather than incorrectly citing only the ICRS offset method.
Blank Custom frame labels keep the pre-existing recorded ICRS convention;
unknown frame labels remain unresolved. Coordinate bounds and possible
ephemeris placeholders remain guarded.

## Rectangle grid

`QUEUE_RECTANGLE_TRIANGULAR_GRID_2` retains the established lattice, clipping and
spacing convention. The source is transformed to Galactic before applying the
field-centre offset. The entire staggered grid is then generated around that
native field centre; PA rotates the native axes using the existing convention:

```text
east  = p cos(PA) + q sin(PA)
north = -p sin(PA) + q cos(PA)
```

Every grid point is transported in Galactic and separately transformed to ICRS.
Rotating an equatorial grid about the transformed centre would be a different
model and is not used. The existing 12-m spacing-reference interpretation and
7-m scaling remain unchanged, including their documented uncertainty.

Galactic grids have no assigned native OT reference and are explicitly outside
`ICRS_NYQUIST_REFERENCE_CASES`, even if their numerical spacing is Nyquist-like.
Both JSON and browser/Explorer notices preserve that limitation. The historical
ICRS A–D3 OT tests still apply only to their original domain.

## Numerical validation and limits

Tests compare the Astropy results with independent great-circle destination
equations and ERFA ICRS/Galactic transforms, with a 0.0001 arcsec separation
tolerance. They cover zero and signed offsets, longitude wrap, high Galactic
latitudes, and independently enumerated 12-m and 7-m rectangle lattices at
PA 0, 30, 90 and 210 degrees. These are mathematical reference cases, not saved
ALMA OT observations.

Integration tests exercise both Mosaic and Single Pointing requests, model
coverage, full scientific branches, source inventory and JSON output. Browser
route tests check Galactic frame provenance, 12-m-only Custom matches, missing
7-m coverage and the same notices in text reports and Mosaic Explorer.

Native Galactic OT exports and CSV offset-definition evidence are still needed
to establish OT parity. A successful model assessment remains conditional on
the recorded project interpretation. No numerical continuum/line formula, TP
policy, missing-ACA grid generation or broader OT reconstruction is introduced.
