# OT proposed Mosaic pointings

The backend imports native OT Pointings exports without manual JSON conversion.
It accepts fixed ICRS absolute positions in Degrees, Radians or Sexagesimal.
Degrees is recommended: the captured C04 export retains distinct coordinates that
round to identical strings in the Sexagesimal export. Original row text, order,
line numbers and file SHA-256 are retained. Duplicate coordinates are reported,
never merged. Each input row is one proposed pointing for this interface.

The file must contain the four-column OT header and its `--` terminator.
Coordinate type and units are case-insensitive. Invalid rows fail with line numbers;
no data row is silently discarded. Blank lines are ignored. Mixed units, offsets,
non-finite coordinates and out-of-range coordinates are rejected. Offset users
should export Absolute coordinates from OT. Limits are 2 MB and 10,000 rows.

Source and array are user-supplied bindings, not facts established by the file or
its filename. Fixed ICRS must be confirmed explicitly. Moving targets are unsupported.
Completeness is a separate user confirmation, not inferred from successful parsing.

## Import

```bash
python -m alma_duplicate.cli.proposed_mosaic \
  --pointings tests/fixtures/ot_pointings/c04_degrees.txt \
  --source P2B_C04_PRECISION --array 12m --confirm-fixed-icrs \
  --output reports/mosaic-dev/ot-import-01.json
```

Use `--confirm-complete` only when this file contains the entire intended pointing
list for the selected source and array. Outputs must be new; parent directories
must exist. Exit 0 means report generation succeeded, not duplication detected.
Invalid input or output failure exits 2.

## Selected Archive coverage

Add all of the following to an import command, choosing the appropriate actual
proposed file and matching array:

```text
--package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02
--array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json
--asdm uid://A002/Xc63024/X4c8
--spw 16
--hpbw-coefficient 1.13
--boundary-epsilon-arcsec 0.000001
--assume-uniform-field-antennas
```

The IC1954 example is a 7m Archive execution; a 12m proposed binding is rejected.
Original Archive evidence is revalidated through the readiness builder. The selected
reported SPW centre defines the beam frequency. Proposed spectral compatibility is
not evaluated. No cross-frequency or cross-execution aggregation is performed.

The report includes the footprint and every proposed row's classification, matching
field IDs, distances to all selected circles, radii and signed boundary distances.
A row inside several circles counts once. Lower coverage counts INSIDE rows; upper
coverage also counts BOUNDARY rows. The threshold is strictly more than half, using
integer comparisons. Results are MET, NOT_MET or BOUNDARY_UNRESOLVED for the supplied
list versus the selected execution/SPW. Unconfirmed proposed completeness overrides
these with PROPOSED_COMPLETENESS_UNCONFIRMED. A NOT_MET result does not establish
non-duplication against a complete Archive Member.

The project accepted the circular beam-union model on 2026-10-23. This report records
that acceptance separately from the legacy diagnostic footprint status. Archive
completeness and the complete duplication policy remain unevaluated. Epsilon is a
numerical band, not an astrometric error estimate.

## References and tests

[Cycle 13 OT Reference Manual, section 5.4.2.3](https://almascience.eso.org/documents-and-tools/cycle13/alma-ot-refmanual)
describes Pointings export. This parser does not accept the different Sources export.
Tests cover captured C04 precision, repeated rows, radians, sexagesimal negative-zero
declination, RA near wraparound, malformed rows, strict majority, boundary intervals,
user bindings and non-overwriting CLI output.
