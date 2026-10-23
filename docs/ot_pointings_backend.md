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

## Multiple execution/SPW coverage

Use `--selections FILE` instead of `--asdm` and `--spw`. The JSON file contains
an explicit list of objects with exactly `asdm_uid` and integer `spw_id` keys.
An IC1954 example is in `examples/mosaic/ic1954-selections.json`. SPW numbers are
execution-local; identical IDs do not establish identical frequencies. The caller
selects each pair, and each footprint uses its own verified frequency and diameter.
Automatic spectral matching remains outside this interface.

```bash
python -m alma_duplicate.cli.proposed_mosaic \
  --pointings /path/to/actual-ot-pointings.txt \
  --source YOUR_PROPOSED_SOURCE --array 7m \
  --confirm-fixed-icrs --confirm-complete \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json \
  --selections examples/mosaic/ic1954-selections.json \
  --hpbw-coefficient 1.13 --boundary-epsilon-arcsec 0.000001 \
  --assume-uniform-field-antennas \
  --output reports/mosaic-dev/proposed-union-01.json
```

Only use the completeness confirmation for an entire intended proposed list.
The selected Archive inputs come from one verified Member/target readiness bundle.
Every selected input must succeed: missing executions/SPWs, unready fields,
duplicate pairs and different arrays fail the request without a partial output.
At most 128 pairs, a 64 KB selection file, and five million point/circle relations
are accepted. Existing single-execution commands retain their schema and behavior.

Union reports use `proposed_mosaic_union_1`. Every circle and match has an ASDM UID,
SPW ID and FIELD ID, so execution-local FIELD IDs cannot collide. Coincident circles
remain separate evidence records, while each proposed row counts once. The output
includes individual footprints and frequencies, all point/circle distances, and
unselected ASDMs present in readiness. This list is not a complete Member inventory;
executions absent from readiness are not inferred. Selecting every available
execution does not establish Member completeness. NOT_MET applies only to the
selected union and must not be presented as a whole-Member non-duplication verdict.

Validation with the three IC1954 executions uses 22 synthetic probes placed at the
first execution's science field centres. These are explicitly not an OT export or
an independent science proposal. The 66 evidence circles cover 22 proposed rows,
with the same counts as the single-execution assessment. Synthetic unit tests also
exercise disjoint coverage, execution-specific frequencies, overlapping hits,
boundary intervals, incomplete lists, invalid selections and CLI mode exclusion.

## Inspect and export SPW selections

The SPW catalog enumerates science-scan-linked SPWs from verified readiness inputs.
AVAILABLE means the current footprint builder accepts the execution/SPW under the
supplied beam coefficient and antenna assumption. It does not establish spectral
compatibility with a proposal. BLOCKED rows remain visible with their reason;
executions with no linked SPWs remain in the execution inventory.

```bash
python -m alma_duplicate.cli.mosaic_spw_catalog \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json \
  --hpbw-coefficient 1.13 --assume-uniform-field-antennas \
  --output reports/mosaic-dev/ic1954-spw-catalog-02.json
```

Review the listed frequencies and field counts. To generate a union selection file,
repeat the command with explicit selections and a different output:

```bash
python -m alma_duplicate.cli.mosaic_spw_catalog \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json \
  --hpbw-coefficient 1.13 --assume-uniform-field-antennas \
  --select uid://A002/Xc63024/X4c8 16 \
  --select uid://A002/Xc63024/X568e 16 \
  --select uid://A002/Xc63024/X98b 16 \
  --output reports/mosaic-dev/ic1954-selected-spws-01.json
```

Pass that output to `proposed_mosaic --selections`. Export validates every explicit
pair against freshly rebuilt readiness, rejects unavailable or duplicate selections
and mixed arrays, and never picks the closest frequency automatically. The selection
file intentionally contains only pairs; the downstream assessment independently
revalidates evidence and records all footprint parameters and provenance. Neither
catalog availability nor selection establishes complete Member coverage.

## Formal position criterion and assessment integration

Coverage CLI reports now include `position_criterion`, using the shared
`CriterionResult` contract with criterion ID `POS-MOSAIC`. The assessment-layer
entrypoint `assess_mosaic_candidates` evaluates explicitly supplied candidates
independently. Each candidate contains context_id, member_ous_uid, source_name,
optional verified readiness, and explicit selections. Readiness is produced by
`build_readiness`; arbitrary edited dictionaries are not an evidence acquisition
interface. Member and source identities must match before evaluation.

A complete proposed list with strictly more than half its rows inside a verified
candidate subset yields SATISFIED for position. Additional candidate coverage cannot
remove those hits. If coverage is insufficient and Member completeness remains
unestablished, the formal outcome is absent with INSUFFICIENT_INFORMATION, even
though the selected-union diagnostic can say NOT_MET. Boundary ambiguity and
unconfirmed proposed completeness also remain explicit insufficient-information
states. Missing candidate evidence never becomes a negative result. Invalid
bindings are contract errors. Different candidates never share their disks.

The result uses the existing rule schema and records the project coverage-model
decision. It is a position result only: continuum/line duplication aggregation is
not enabled. The legacy automatic candidate-search entrypoint still rejects Mosaic
requests, since its single-pointing search filters have not been validated for this
geometry. This increment integrates supplied-candidate evaluation in the assessment
layer; it does not claim automatic Mosaic discovery or web-upload integration.

## Run a candidate assessment from native OT input

`mosaic_assessment` exposes the assessment-layer POS-MOSAIC rule for a list of
explicit Archive candidates. It does not run automatic candidate discovery.

```bash
python -m alma_duplicate.cli.mosaic_assessment \
  --pointings /path/to/actual-7m-ot-export.txt \
  --source YOUR_PROPOSED_SOURCE --array 7m \
  --confirm-fixed-icrs --confirm-complete \
  --candidates examples/mosaic/ic1954-candidates.json \
  --hpbw-coefficient 1.13 --boundary-epsilon-arcsec 0.000001 \
  --assume-uniform-field-antennas \
  --output reports/mosaic-dev/mosaic-assessment-01.json
```

The example requires the existing local IC1954 package audit. Candidate manifest
paths are relative to the manifest, not the working directory; absolute paths are
also accepted. Each candidate declares context_id, member_ous_uid and source_name.
Evidence-backed entries additionally require package_audit_dir, array_catalog and
selections together. To retain a candidate with unavailable evidence, omit all
three; its rule result is INSUFFICIENT_INFORMATION. Invalid evidence or mismatched
identity is an error, not a missing-data fallback. Duplicate context IDs, duplicate
JSON keys, unknown fields and partial evidence configuration are rejected.

The manifest is limited to 1 MB and 100 candidates. Every evidence bundle is rebuilt
through the verified readiness loader. Output includes the OT import, manifest
SHA-256, effective configuration and each candidate's rule and coverage evidence.
The console summarizes inside/total counts and the formal position outcome without
printing every circle distance. Exit 0 means the assessment report was generated;
it does not mean the candidate satisfies all duplication criteria. Exit 2 indicates
invalid input or execution failure. Existing output files are never overwritten.
