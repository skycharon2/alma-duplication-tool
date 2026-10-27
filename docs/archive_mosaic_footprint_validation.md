# Multi-SPW footprint validation

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

This diagnostic runs the explicit circular half-power model independently for each
selected SPW. It checks inverse-frequency scaling and spherical boundary behaviour.
An optional sampled TAP s_region supplies vertex probes only, not an authoritative
half-power region, complete boundary comparison, area comparison or duplication rule.

## Run

```bash
python -m alma_duplicate.cli.archive_mosaic_footprint_validation \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json \
  --asdm uid://A002/Xc63024/X4c8 \
  --spw 16 --spw 18 --spw 20 --spw 22 \
  --hpbw-coefficient 1.13 \
  --frequency-choice reported-spw-centre \
  --assume-uniform-field-antennas \
  --boundary-epsilon-arcsec 0.000001 \
  --boundary-offset-arcsec 0.01 \
  --region-metadata tests/fixtures/archive/mosaic_region_2026_10_23/metadata.xml \
  --output reports/mosaic-dev/ic1954-footprint-validation-02.json
```

All scientific model choices remain explicit, inherited from the footprint builder.
Each SPW is evaluated separately; no spectral averaging or union across SPWs occurs.
The output must be new. Select at most 32 unique SPWs. Probe comparisons retain the
existing five-million-distance budget. Exit 0 means numerical diagnostic checks pass,
3 means a check failed, and 2 means invalid input or a filesystem failure.

## Boundary probes

For each circle, generate its centre and four spherical bearings (0, 90, 180,
270 degrees), at radius minus offset, radius and radius plus offset: thirteen points.
Astropy directional_offset_by generates the coordinates independently of the scalar
great-circle distance implementation used for classification. The offset must exceed
the positive epsilon and remain smaller than the radius. Neither is an astrometric
uncertainty or policy tolerance.

Origin-circle expectations are checked separately from union membership. A probe
outside its originating circle can still be inside another circle; that is expected
Mosaic overlap, not a failed boundary test. Reports retain both classifications,
origin FIELD IDs, signed boundary distances and failed probe IDs. Radius × frequency
must remain constant at fixed coefficient and diameter within numerical tolerance.
This validates implementation consistency, not the physical beam approximation.

## s_region evidence

The input must be one successful science Mosaic TAP row with exact Member, target
and ASDM identities. Only one STC-S ICRS polygon is supported. Coordinates and vertex
count are validated; the raw s_region, response hash and frequency metadata (with
reported units) are preserved. A TOP 1 capture is expressly a sampled row, not an
execution inventory. No automatic equivalence to the selected listobs SPW is claimed.

For each SPW, classify polygon vertices against the circular union and record their
nearest field distance and signed nearest-circle boundary distance. A vertex outside
shows a sampled discrepancy. Vertices all inside do not prove edge containment,
area equivalence or either direction of full-region inclusion. The previous standalone
s_region experiments retain their local projection/raster scope and are not silently
promoted into production geometry or used as ground truth.

## IC1954 result

For ASDM X4c8 with coefficient 1.13 and reported SPW centres:

| SPW | Frequency (GHz) | Half-power radius (arcsec) | Sampled polygon vertices |
| --- | ---: | ---: | --- |
| 16 | 229.7063782 | 21.728172 | 43 outside |
| 18 | 232.1586488 | 21.498659 | 43 outside |
| 20 | 216.2757257 | 23.077484 | 43 inside |
| 22 | 218.1087257 | 22.883540 | 43 inside |

Each footprint contains 22 circles and 286 generated probes. All origin-circle
checks pass. These differences are conditional on the model and frequency choices;
the s_region response definition and correspondence to each SPW remain unresolved.
No proposed-pointing coverage fraction or duplication verdict is produced.
