# Legacy QA acquisition follow-up

## Observed failure and change

A bounded live preparation of RX_J1347.5-1145, Member `uid://A001/X140/X6`,
downloaded a 121,027,072-byte public auxiliary package. The standard listobs scan
found no candidates. Inspection found four `qa/*__textfile.txt` summaries with FIELD
tables that were previously skipped because their filenames do not contain listobs.

The auxiliary scanner now reads this explicit QA filename/path family within the
existing text, entry, expanded-byte and candidate-count limits. It rejects unsafe
paths and linked candidate members, records hashes and archive paths, and saves text
in the local evidence directory. A diagnostic parser retains exact-target FIELD
records and reported frame without creating a reconstructed execution. Unsupported
or repeated summaries remain explicit unsupported layouts.

The package audit retains these records under `inspection.alternative_evidence`.
Candidate preparation exposes them as `alternative_pointing_evidence`, alongside
`missing_tap_asdm_uids`. Reconstructed executions with missing TAP inventory entries
now remain `PARTIAL_EVIDENCE` instead of appearing fully prepared.

## Real replay

Offline replay at `reports/mosaic-dev/rx-legacy-qa-02/package_audit.json` found four
QA summaries, each with eight target FIELD records. No execution was promoted to
ready. The report remains `UNRESOLVED`. These 32 records are not a claim of 32
unique sky positions or a complete observing history.

The QA coordinate frame is J2000; the dataset is `.ms.split`, not the original MS;
the scan names can be truncated. Those three bindings must be validated before this
route can feed the position rule. The calibrated log container was also inspected:
it contains startup/calibration logs, not a supported original-MS listobs table.

## Validation and next step

Regression tests cover real text, exact target names, saved evidence integrity,
repeated summary rejection, unsafe paths, linked members and partial inventory
status. Existing standard listobs reconstruction continues through its original
parser. No frequency or sensitivity is imported from QA text.

The next step is an independently checked J2000 coordinate conversion and a
validated split-MS scan/FIELD identity adapter using real reference evidence.
Until then the additional QA route improves evidence acquisition and failure
explanation, while the scientific result remains unknown where this evidence is
required. It is not an s_region-based reconstruction.

## Scan binding and main-entry follow-up

The exact-target FIELD table has eight records, but this is not eight science
pointings. FIELD 2 has only a calibration scan; FIELD IDs 3–9 have `Obs Target`
scans. The adapter now validates FIELD/source ID pairs, checks full or explicitly
truncated display names against that exact ID, and retains only those seven fields
as diagnostic science candidates. Duplicate IDs, unsupported intents, malformed
rows, bad coordinate ranges and contradictory MS summaries are rejected.

The original calibration script explicitly splits the named original MS to the
same `.ms.split` named in the QA summary, selecting spectral windows 9,11,13,15.
It is stored as non-executable text with provenance. This establishes a documented
processing relationship, not an independent coordinate measurement or proof that
all processing and historical corrections were applied. No independent original
FIELD/ASDM coordinate table was obtained in this bounded auxiliary-product
inspection. Consequently no coordinate residual tolerance test can yet be run and
no QA execution is promoted to production coverage.

### Correction to the proposed frame conversion

The official historical ALMA article states that pre-Cycle-3 data were labeled
J2000 although the phase-calibrator reference was ICRS; it recommends relabeling
applicable old images and MS FIELD/SOURCE tables, rather than transforming their
coordinate numbers:

https://help.almascience.org/kb/articles/how-do-i-combine-cycle-1-and-or-2-measurementsets-and-images-with-ones-from-other-cycles-j2000

This is distinct from the Mosaic FIELD-coordinate correction incident:

https://almascience.eso.org/news/notification-of-problem-affecting-certain-alma-data-that-used-mosaic-and-offset-pointing-observing-modes

RX project 2013.1.00246.S is absent from that published affected-project list. This
is not a product-level certificate of coordinate correctness. A generic FK5/J2000
numerical conversion must not be applied just because the QA header says J2000.
The adapter preserves the reported frame and flags relabel applicability and
independent coordinate verification as unresolved.

### Assessment integration

`alternative_pointing_diagnostics` in each candidate is rebuilt from hash-checked
QA text and Member/target-bound local receipts. Saved `EVIDENCE_BOUND` labels are
not trusted. Its source entries expose science FIELD counts, excluded FIELD IDs,
reported execution identity and specific outstanding checks. It never contributes
circles to the position rule. `position_summary` exposes per-context inside/total
counts and contributing/excluded executions from the existing evaluated coverage;
missing coverage has null counts rather than an invented zero.

Offline common-entry tests combine the real unresolved RX capture with the verified
LMC capture. RX retains an unknown position while LMC can pass; incompatible
frequency/angular resolution and exact-half coverage cannot create a positive
joint result. Corrupted QA text and a different target identity are rejected.

The remaining scientific prerequisite is an independently obtained original
MS/ASDM FIELD reference for the same execution, with applicable frame and repair
provenance. The acquisition and unresolved-result path is integrated; a validated
QA-to-coverage fallback is deliberately not claimed complete.
