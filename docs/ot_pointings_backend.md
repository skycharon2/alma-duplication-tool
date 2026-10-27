# OT proposed Mosaic pointings

The OT import format below remains current. For default Archive assessment,
use the [s_region workflow](mosaic_s_region_position.md). The package/SPW coverage
commands later on this page are retained reconstruction diagnostics, not required
inputs to the default evaluator.

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

## Automatic candidate pointing preparation

The preparation runner connects discovery identities to the existing inventory,
DataLink, cache, auxiliary inspection and package reconstruction implementations.
Users no longer supply ASDM IDs, product row indices or per-candidate package paths
for this acquisition step.

```bash
python -m alma_duplicate.cli.mosaic_candidate_preparation \
  --discovery reports/mosaic-dev/ic1954-discovery-acceptance-01/discovery.json \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/automatic-pointings-01
```

This command performs live metadata retrieval and may download auxiliary products
within the existing per-product size/time limits. At most 100 distinct Member/target
candidates are accepted. Each candidate captures fresh Member/target inventory and
DataLink evidence, selects exactly one accessible verified auxiliary product, and
runs the package audit. Downloads reuse the hash-verified auxiliary cache. Multiple
eligible products are reported as AMBIGUOUS_PRODUCTS, never silently selected.
Missing products and failures retain their stage and reason. One candidate failure
does not discard successful candidates. New output directories preserve earlier runs.

POINTINGS_PREPARED means supported package pointings were reconstructed without
reported unresolved package entries; it does not establish complete Member coverage.
PARTIAL_EVIDENCE retains available executions and unresolved records. The summary
also preserves upstream discovery status and recall limitations. A COMPLETED
preparation run only describes its supplied candidates, not exhaustive discovery.
No-position-result is not non-duplication.

Preparation now includes automatic AQ array readiness as described below. Selection
of spectrally applicable SPWs and overall duplication aggregation remain separate work.
The output package directories feed the existing verified readiness builder. Metadata
replay is available through injected providers for offline tests; the CLI uses live
metadata and cached auxiliary content where available.

### Automatic AQ array readiness

Candidate preparation now fetches official AQ source records for each reconstructed
Member using the existing validated AQ client. Source identity and execution antenna
diameters are cross-checked by the existing readiness binder. The command no longer
requires a manually prepared array manifest for this stage.

Each candidate retains `array_acquisition.json` (query provenance, response hashes
and parsed records) and `readiness.json`. This is live acquisition provenance, not
an original-response capture manifest; no raw AQ response is fabricated. The readiness
builder also accepts an in-memory catalog, mutually exclusive with a captured manifest.

A successful run requires pointings and EVIDENCE_BOUND readiness for every supplied
candidate. AQ failures preserve reconstructed pointings and set readiness_status to
UNAVAILABLE. Incomplete or conflicting position/array evidence yields NOT_READY. Offline
replay without an injected array provider explicitly skips AQ and remains INCOMPLETE.
Listobs spectral selection remains diagnostic; the main Archive assessment uses TAP metadata and shared branch aggregation.

### Metadata responsibilities

OT exports supply proposed pointing positions. Archive auxiliary listobs supply
candidate science pointing positions and their execution/scan identity. Additional
listobs setup information is diagnostic evidence only; it does not define a second
proposal-frequency matching workflow.

Production frequency, bandwidth, angular resolution, spectral resolution and
sensitivity inputs must come from the existing Archive metadata ingestion and
comparison contexts used by Single Pointing. Those contexts retain their existing
unit, association and evidence validation. Mosaic adds candidate pointings and the
directional POS-MOSAIC criterion; it does not replace the other metadata sources.

The experimental listobs proposal-window routing module and its CLI options have
been removed. Candidate preparation does not require a proposal frequency interval,
TOPO-only proposal input, or full containment within an estimated listobs interval.
Existing execution/SPW footprint diagnostics remain diagnostics and must not be
mistaken for the metadata-driven comparison interface described below.

## Shared Archive metadata assessment

`assess_archive_mosaic_contexts` in the assessment layer now accepts a validated
fixed Mosaic request, imported proposed pointings, existing Archive comparison
contexts, audited package directories keyed by (Member UID, target), and the existing
AQ array catalog. It loads verified package executions and binds pointings to each
context's Member, target and ASDM. Wrong candidate identities are errors; absent
matching execution evidence leaves the position criterion unresolved.

The corresponding `evaluate_mosaic_context` uses the Archive context's canonical
frequency and bound array diameter for half-power radii. Listobs contributes science
field coordinates and execution identity only. No listobs SPW selection or approximate
spectral containment is required by this path. Frequency and continuum RMS evaluators
are reused directly, as are angular resolution, continuum setup and line-pair numeric
rules. Continuum and line aggregation explicitly accept POS-MOSAIC; the proposal is
never relabelled SINGLE_POINTING to bypass a guard. Legacy evaluation defaults remain
unchanged.

Results include the same per-context criteria, continuum/line branch outcomes,
line-pair evidence and position coverage. Existing ambiguity, association, missing
quantity and unapproved-evidence gates remain in force. Pointing completeness and
boundary limitations still prevent unsupported negative position conclusions. A
verified majority can satisfy position while another independent criterion fails.

## Automatic assessment entrypoint

`assess_observation(..., mosaic=MosaicAssessmentInput(...))` now runs the Archive
Mosaic workflow. The CLI exposes the same entrypoint:

```sh
python -m alma_duplicate.cli.evaluate \
  --request path/to/mosaic-request.json \
  --live-archive \
  --mosaic-pointings path/to/ot-pointings.txt \
  --mosaic-array 7m \
  --confirm-fixed-icrs --confirm-complete \
  --mosaic-margin-arcsec 1 \
  --mosaic-cache data/cache/archive-auxiliary \
  --mosaic-workdir reports/mosaic-dev/full-assessment-01 \
  --output reports/mosaic-dev/full-assessment-01-report.json
```

The request uses `geometry: "MOSAIC"`, its proposed target name, and the same
frequency, angular resolution, spectral-window and sensitivity fields as a Single
Pointing request. Select `ARCHIVE` only. The OT file supplies the position list;
no replacement central coordinate is required. Use a fresh work directory and
choose the discovery margin explicitly; the example value is not a validated
completeness guarantee. Queue and custom candidate prefilter predicates are not
supported in this workflow and are rejected rather than silently ignored.

The backend discovers candidate identities, acquires auxiliary products, reconstructs
pointings, obtains AQ array evidence, and fetches full TAP rows with an exact
Member/target query. Count-first completeness, field descriptors, normalization,
reconstruction and comparison-context construction reuse the existing Archive client.
The report retains metadata rows, field descriptors and query provenance alongside
acquisition receipts and per-context criterion/branch results. Failures remain visible
per candidate; an empty or incomplete search never establishes non-duplication.

### Position readiness and multi-execution binding

`position_status` and `position_blocking_reasons` describe array/pointing readiness.
The older `input_status`, SPW links and spectral parse errors remain available for
experimental listobs diagnostics. Missing FULL_RES labels, missing listobs frequency
tables and non-TOPO labels do not block the metadata-driven position path.

Execution union requires matching Member/target identity and explicit compatible TAP
rows for each ASDM. Compatibility requires equal normalized frequency, bandwidth,
resolution and sensitivity operands, frequency-support content, observing-mode input,
project and array labels. Distinct local field IDs are qualified by ASDM. A proposed
row counts once regardless of how many circles cover it. Package-only executions with
no compatible TAP row are listed in `excluded_executions`; package membership does not
supply missing spectral associations. Other criteria remain evaluated per Archive
context, with existing ambiguity gates intact.

Position results distinguish missing pointings, missing array/frequency metadata,
unbound execution metadata, unconfirmed proposed completeness, boundary uncertainty,
and insufficient candidate completeness. More than half inside a verified subset can
satisfy POS-MOSAIC. Exactly half does not satisfy the strict threshold. An uncovered
subset cannot establish a negative Member-level verdict while completeness is unknown.

### Acceptance scope

Regression tests exercise the common assessment entrypoint, captured three-execution
listobs reconstruction, automatic product selection/readiness, metadata ingestion,
multi-execution union, shared continuum/line rules, missing spectral diagnostics,
incompatible metadata and duplicate-hit counting. Network boundaries are replayed
for deterministic acceptance; synthetic proposal/metadata identities are explicitly
marked in tests. These tests do not establish all-sky discovery recall.

UI form wiring and exhaustive candidate discovery are separate remaining work. The
region prefilter includes science rows across candidate geometries and a null-region fallback; its
recall against reconstructed half-power coverage is still unproven. Results therefore
remain scoped to the acquired candidates and bound Archive contexts.

A live IC1954 verification on 2026-10-23 returned four complete TAP metadata rows.
With the saved synthetic 22-point acceptance list, all four contexts satisfied
POS-MOSAIC using their own Archive frequencies. Only ASDM `uid://A002/Xc63024/X4c8`
had matching TAP metadata; the two additional package executions remained explicit
exclusions. Local receipts are `reports/mosaic-dev/ic1954-member-metadata-acceptance-02.json`
and `reports/mosaic-dev/ic1954-metadata-position-acceptance-01.json`. This verifies the
metadata/position connection, not a final scientific verdict for a real proposal.

The Archive Single Pointing candidate route is described in
[cross-geometry support](mosaic_cross_geometry.md). The proposal remains Mosaic;
the new route changes candidate coverage construction, not the other criteria.
