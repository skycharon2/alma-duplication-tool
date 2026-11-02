# Queue Mosaic reconstruction: first backend increment

This offline increment consumes a complete parsed CSV snapshot and produces
`queue_mosaic_reconstruction_1` evidence. It does not run duplication criteria,
change the active snapshot, or enable Queue Mosaic in the browser/shared evaluator.
Supervisor testing of the existing application can proceed independently.

## Run

```sh
python -m alma_duplicate.cli.queue_mosaic \
  --queue-csv /path/to/duplication-check-csv.csv \
  --output /path/to/new-reconstruction.json
```

The output parent must exist. Existing files, including the input CSV, are never
overwritten. Exit 0 means reconstruction succeeded, not that a duplication was
found or excluded. Invalid/incomplete parsing and file errors return 2. There is
no network acquisition, implicit snapshot activation or spatial prefilter.

## Associations

The existing parser and `reconstruct_queue_rows` retain their contracts.
Custom rows are partitioned by snapshot and every exact operational field except
Long/Lat Offset and the formatted RA_HMS/Dec_DMS strings. This includes the
reference position, all SPWs, velocity, requested performance, array flags,
operational standalone evidence and unknown additional columns. Numeric lexical
differences can conservatively split groups. Unknown columns are not discarded.

These are inferred export-equivalence groups, not official Science Goals.
Neither seven rows nor successful whole-file parsing establishes complete
candidate coverage. Repeated positions keep their physical row identities.
Each Rectangle row is a separate candidate, including exact duplicate records.
No union of distinct rectangles or cross-setup Cartesian product is constructed.

The report retains snapshot hash, source date/description, parser issues, original
columns, units, dictionary, raw values, physical lines, fingerprints and the
existing spatial/spectral/request association IDs. Non-Mosaic rows are accounted
for explicitly; their existing assessment path remains unchanged.

## Coordinates and arrays

Custom rows expose diagnostic pointing centres; Rectangle rows expose only
diagnostic rectangle centres. Blank/ICRS frames use the existing project's
ICRS-reference, local east/north spherical transport convention:
`bearing=atan2(long_offset, lat_offset)`, `distance=hypot(offsets)`.
Positive offsets follow celestial east/north, never screen right/down. The
existing source zero tolerance is recorded. Raw offsets are never overwritten.
Rectangle PA never rotates the centre offset. No rectangle corners or grid are
generated. OT equivalence remains unverified, so derived centres are marked
`DIAGNOSTIC_ONLY`. Zero/zero reference placeholders remain unresolved.

Galactic reference-coordinate semantics in this export require separate evidence;
the adapter retains those rows without guessing whether the RA/Dec values are
equatorial or Galactic. Other unsupported frame labels are also unresolved.

`resolve_queue_beam_interpretation` is reused without modifying its rules:
`QUEUE_ARRAY_BEAM_INFERENCE_3`, TP ignored, independent D7/D12 variants when
inferred. TP does not block reconstruction. Array inference does not prove which
array owns the explicit Custom points. Variants therefore have unresolved
geometry and no assigned pointing list; no seven-point list is silently reused
as an OT-generated ACA grid. No beam radius or scientific branch is evaluated.

## Validation and next increment

Tests use the existing reduced real CSV fixture, with explicitly modified
engineering cases for setup isolation, signed offsets, RA wrap, Galactic
ambiguity, duplicate preservation, input-order determinism, parser failure,
snapshot identity and output overwrite protection.

Read-only local acceptance on the supplied full snapshot
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`:
3200 rows; 420 inferred Custom groups (2940 rows); 140 independent Rectangle
records; 120 non-Mosaic rows; 64 exact repeated Mosaic rows retained. This dated
snapshot describes 2026-03-03, not a current Queue census. Full operational data
and the generated report remain outside version control.

The [second increment](queue_mosaic_position.md) provides per-array beam coverage
and strict-majority POS-MOSAIC for explicitly supplied coverage bindings. Automatic
CSV geometry binding still requires explicit-point array ownership and
offset/absolute OT parity evidence. Rectangle grid anchoring, PA sign, edge sampling and
7-m patterns require OT export comparisons. Full branch OR belongs after
position and the other criteria have been evaluated coherently.

References:
- [OT Reference Manual, field centres and Rectangle](https://almascience.eso.org/documents-and-tools/cycle13/alma-ot-refmanual)
- [OT Mosaic and array patterns](https://help.almascience.org/kb/articles/how-do-i-set-up-a-mosaic-in-the-ot)
- [Existing Queue array interpretation](queue_common.md)
