# Archive Mosaic Acquisition-to-Reconstruction Pipeline

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

## Scope

The unified entry connects saved TAP observation metadata, auxiliary acquisition,
and execution-local reconstruction. Project, Member, ASDM, and target identities
are read from one explicit TAP row instead of being entered again at the command
line. The existing local reconstruction and acquisition commands remain available.

This increment does not add candidate discovery, cross-execution merging, array
inference, or scientific duplication criteria.

## Run

From the repository root in the installed project environment:

```bash
python -m alma_duplicate.cli.archive_mosaic_pipeline \
  --metadata docs/research/mosaic/evidence/case_E_tap.xml \
  --receipt tests/fixtures/archive/mosaic_products_2026_10_23/7m/discovery.json \
  --product-row 3 \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/7m-execution-pipeline-01 \
  --offline
```

Expected result: `RECONSTRUCTED`, with 19 science fields. The output parent must
exist and the output directory must be new. Remove `--offline` to permit download
when no valid cached auxiliary product exists. The previous acquisition limits,
cache validation, and candidate-selection rules remain in force.

## Output

| File | Purpose |
| --- | --- |
| `metadata.xml` | Original saved TAP response bytes |
| `discovery.json`, `response.xml` | Product-discovery receipt and source response |
| `acquisition.json` | Download/cache and package inspection evidence |
| `listobs.txt` | Unique validated candidate, when found |
| `execution.json` | Reconstructed execution with evidence references, on success only |
| `pipeline.json` | Pipeline outcome, selected identity, and metadata hash |

`execution.json` uses the standalone `archive_mosaic_execution_2` wrapper with
explicit provenance references. The nested reconstruction method remains
`archive_mosaic_execution_1`. This is not a change to assessment report schemas.
The older local reconstruction command retains its existing output format.

## Evidence checks

1. Require one TAP results resource, one table, one TABLEDATA row, and explicit
   successful QUERY_STATUS values. Require nonblank identity fields and science
   and Mosaic flags. This is selection of one recorded observation, not proof of
   a complete TAP search or Member inventory.
2. Reparse the original discovery response after validating its hash and size.
   Require its Member to match the TAP row and any requested ASDM to agree.
3. Run the existing acquisition entry for the identity read from TAP.
4. Before reconstruction, verify the saved TAP identity, acquisition schema and
   FOUND status, ASDM, target, discovery-receipt hash, and selected product record.
5. Require a unique selected MATCHED candidate, then verify listobs byte count,
   SHA-256, and parsed science-field count against the acquisition record.
6. Reuse the local reconstruction function and retain acquisition and metadata
   hashes alongside the execution object.

The resulting metadata status is `SAVED_TAP_ROW_MEMBER_BOUND`; acquisition status
is `VERIFIED_ACQUISITION_RECEIPT`. These describe local evidence checks, not an
independent authentication of historical source records. Local hashes are integrity
checks and do not prevent coordinated modification of all input files.

Project identity comes from the saved TAP row. The target and ASDM are checked
against listobs through the existing parser; the Member is matched against the
DataLink row. Array information remains unset. Member completeness remains
`MEMBER_COMPLETENESS_NOT_ESTABLISHED`, and policy status remains `NOT_EVALUATED`.

## Failure handling

Acquisition statuses such as NOT_FOUND, AMBIGUOUS, UNRESOLVED_CANDIDATES, and FAILED
are preserved without producing an execution object. If acquisition reports FOUND
but its saved evidence fails reconstruction checks, the pipeline reports
RECONSTRUCTION_FAILED. Preflight input errors occur before acquisition. Filesystem
failures may leave a partial output directory; existing directories are never reused.

Exit codes: 0 for RECONSTRUCTED, 3 for acquisition or reconstruction failure, and
2 for input/configuration or filesystem errors. No failed state becomes a successful
empty Mosaic object.

## Validation

```bash
python -m pytest -q tests/unit/test_archive_mosaic_pipeline.py
python -m pytest -q
```

Recorded validation on `06caf88` plus this uncommitted increment: 20 pipeline
tests passed as part of the full Python regression: 2298 passed and 12 skipped.
Python compilation and whitespace checks passed. Ruff was not run locally.

Focused tests cover the captured 7m input, preserved numerical field records,
receipt and listobs tampering, source identity mismatches, ambiguous selections,
field-count disagreements, invalid TAP selection, source failures, CLI output,
and overwrite protection. Default tests use captured data and do not contact
remote services.

The production CLI was also run against the previously downloaded, hash-verified
7m cache, reconstructing 19 fields. The independent 12m acquisition and subsequent
cached reconstruction are recorded below.

## Independent 12m validation

NGC5248 uses the same entry and selection logic. The old experimental TAP XML lacks
QUERY_STATUS after reserialization; the pipeline correctly rejects it. A new raw
TAP response was captured for the explicit Member/ASDM/target identity and is saved
with its request, timing, and hash. The TOP 1 query is not an inventory query.

The auxiliary download succeeded at 250,724,352 bytes. Initial inspection rejected
its 195,903,625-byte weblog under the old single-member limit. Nested weblogs now
use streaming reads and a separate 250 MB bound; the ordinary member, expanded-size,
candidate, and nesting limits remain enforced. The failed attempt is preserved.

The subsequent cached run returned RECONSTRUCTED. All 11 fields, including original
coordinate representations and scan/SPW associations, match the earlier reference.
Original MS and `_target.ms` candidates are distinguished by their headers. Evidence
is retained in `tests/fixtures/archive/mosaic_pipeline_12m_2026_10_23/`.

```bash
python -m alma_duplicate.cli.archive_mosaic_pipeline \
  --metadata tests/fixtures/archive/mosaic_pipeline_12m_2026_10_23/metadata.xml \
  --receipt tests/fixtures/archive/mosaic_products_2026_10_23/12m/discovery.json \
  --product-row 3 \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/12m-execution-pipeline-01 \
  --offline
```

The validated local cache is required for offline execution. Remove `--offline`
to allow acquisition when the cache is absent. Use a new output directory each time.

## Next increment

Define the expected execution inventory and reconcile it with acquired execution
records before constructing a broader Mosaic object. Neither successful sample
establishes complete Member coverage or cross-execution pointing identity.
