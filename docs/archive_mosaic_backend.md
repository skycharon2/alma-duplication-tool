# Archive Mosaic Backend: Local Execution Reconstruction

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

## Scope

This increment parses preserved CASA listobs files and reconstructs science FIELD
evidence for a single Archive execution. The output is a serializable record with
observation identifiers, field coordinates, scan/SPW associations, and explicit
provenance and completeness limits.

The existing Single Pointing input, search, scientific rules, and report formats
are unchanged. Remote acquisition, cross-execution reconstruction, and Mosaic
duplication assessment are outside this increment.

## Implementation

| Module | Responsibility |
| --- | --- |
| `src/alma_duplicate/domain/archive_mosaic.py` | Immutable scan, field, parsing-result, and execution records |
| `src/alma_duplicate/parsers/archive_listobs.py` | Offline parsing of the supported ICRS listobs layout and local consistency checks |
| `src/alma_duplicate/archive_mosaic.py` | Execution reconstruction and validation of identifier and array-reference inputs |
| `src/alma_duplicate/cli/archive_mosaic.py` | JSON export with exclusive file creation to prevent overwriting earlier results |
| `tests/unit/test_archive_mosaic.py` | Captured-data replay, malformed-input checks, association checks, and CLI coverage |

The parser builds on the existing experimental extraction method. It verifies the
MS basename against the supplied ASDM, requires one FIELD table, and links
`OBSERVE_TARGET#ON_SOURCE` scan records to fields. One scan may visit multiple
fields; conflicting SPW associations are checked within each `(FIELD_ID, scan_id)`.

Each output retains:

- Project, Member, ASDM, source name, and caller-supplied metadata reference;
- Original-file SHA-256, MS basename, and parser version;
- FIELD_ID, SOURCE_ID, original coordinate strings, and parsed ICRS coordinates;
- Per-field scan/SPW associations;
- Local-input status, unverified external metadata, unknown Member completeness,
  and unevaluated scientific criteria.

## Run the 12m example

Run from the project root in a Python environment where the project is installed.
The output directory must exist and the output filename must be new.

```bash
python -m alma_duplicate.cli.archive_mosaic \
  --listobs experiments/mosaic_footprint_ab/data/ngc5248_12m_listobs.txt \
  --project 2019.1.01718.S \
  --member uid://A001/X1465/X3f4 \
  --asdm uid://A002/Xeaae1d/X1a2 \
  --source NGC5248 \
  --metadata-reference experiments/mosaic_footprint_ab/data/ngc5248_12m_tap.xml \
  --output /tmp/ngc5248-mosaic-execution.json
```

Expected output: 11 science fields (FIELD_ID 4–14), the original-file hash, and
explicit unknown-completeness and unevaluated-policy states.

The metadata reference records the caller's evidence source; the command does not
read or independently verify that reference. The array label remains unset unless
both `--array` and `--array-evidence-reference` are supplied. A supplied reference
does not establish that its scientific content has been verified.

## Validation

```bash
python -m pytest -q tests/unit/test_archive_mosaic.py
python -m pytest -q
```

Recorded validation for local baseline `ff5a098` plus this uncommitted increment:

- Focused tests: 11 passed.
- Full Python regression: 2235 passed, 12 skipped.
- The captured 7m and 12m samples reproduce 19 and 11 science fields respectively.
- The 12m CLI export was checked successfully.
- Ruff was unavailable in the test environment.
- No new remote acquisition or browser checks were performed.

Tests compare field identities, coordinates, and scan associations with preserved
CSV references. Failure cases include incorrect MS identities, target mismatches,
unsupported frames, truncated input, duplicate headers, missing fields, and
conflicting scan records. CLI tests verify that existing output is not overwritten.

## Supported input and limitations

The parser supports the verified single-target ICRS listobs layout with a complete
FIELD section and parseable ON_SOURCE scan rows, including the existing
Markdown-wrapped sample. Multiple ON_SOURCE targets, unsupported frames, altered
MS basenames, and unsupported layouts raise errors rather than returning a
successful empty list.

FIELD_ID is local to an execution's MS product. Different fields at identical
coordinates remain separate, and executions are not merged. SPW identifiers retain
their original listobs values; their mapping to TAP SPWs is not established.
Cross-execution pointing identity and spectral-setup grouping remain future work.

Successful parsing establishes supported layout and local consistency, not a
complete scan inventory or complete Member execution coverage. Coordinates are
labelled `LISTOBS_REPORTED_FIELD_CENTRE`; they are not reinterpreted as antenna
POINTING directions or an approved half-power coverage model. Original coordinate
strings are retained because conversion to degrees does not increase source precision.

Project and Member metadata are caller-supplied. MS-basename and target-name
matching provides only a local association check. Historical acquisition URLs,
timestamps, and array provenance remain unverified where evidence is missing.
The original limitations are retained in
`experiments/mosaic_footprint_ab/data/local_fixture_inventory.json`.

## Next steps

1. Document the previously explored retrieval path, including requests, product
   links, paths within downloaded packages, and original-file records.
2. Implement acquisition and caching using the same offline parser.
3. Reconcile the expected execution inventory with retrieved evidence before
   claiming completeness across executions.
4. Extend candidate discovery and integrate scientific rules once their required
   evidence and interpretations are established.
