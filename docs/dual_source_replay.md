# NGC6240: real Archive acquisition and offline dual-source replay

The same fixed single-point request selects ARCHIVE and QUEUE. It retains the
NGC6240 coordinates, complete hypothetical usable-bandwidth setup and display
limit from the Queue example; only source selection changes. No expected project
or UID is used in the query, loader or candidate filter.

## Evidence and limits

The Archive capture contains the **entire** 30 arcsec footprint-intersection
response, not a center-only cone and not a hand-selected subset. It preserves
raw VOTable bytes for the optional-column probe, COUNT and retrieval, including
field descriptors, missing-cell representations, QUERY_STATUS and server query
timestamps. The manifest records exact ADQL, MAXREC, response SHA-256 values,
client acquisition times and the original query-run identity. The production
Archive client checks completeness and binds the result to the request again.
Response hashes detect changed bytes; they are not third-party signatures.
A scoped .gitattributes rule preserves these XML files as binary evidence, so
Git does not normalize the original CRLF bytes or alter their checksums.

Queue uses the existing 13-row `queue_pipeline_v1.csv` fixture. These are real
source rows, previously checked against the captured official download; see
[official source evidence](evidence/official_sources.md). This is a **subset**
of the Queue, with the source's March 3, 2026 snapshot description, not a fresh
full-Queue acquisition. Both inputs concern the same request but have different
source dates. Source COMPLETED means the provided input was processed; it does
not imply exhaustive current-cycle coverage or absence of duplicates.

CASE1's ten rows belong to another sky region and were selected from a 336-row
result. They remain separate retrieval evidence and are not used here. Neither
CASE1 nor CASE2 becomes a scientific duplicate label through this replay.

The proposed request is single-pointing; retrieved candidates need not all be
single-pointing. Unsupported geometries remain explicit. Archive POS-SINGLE
continues to return no outcome, with a method-side issue. No Archive coverage
method, CONT-FREQ method or approval upgrade is added.

## Production CLI

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/dual_source/request.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --archive-replay tests/fixtures/archive/ngc6240/manifest.json \
  --queue-candidate-beam --output reports/dual-source-local.json
```

`--archive-replay` and `--live-archive` are mutually exclusive. Replay has no
network fallback. It feeds raw responses through PyVO and the production
ArchiveClient; a different ADQL/MAXREC sequence or unused response fails the
Archive source. A corrupt/missing input file fails CLI input loading. A failed
Archive replay can still yield a Queue report, with CLI exit code 3. Output may
not overwrite the manifest or any response input.

`source_metadata.provenance` keeps acquisition times and query identity;
`sources.ARCHIVE.replay` explicitly identifies offline reuse and manifest hash.
Report generation/search execution timestamps describe the new replay, not a
new Archive acquisition. Raw responses live alongside the manifest; copying only
the manifest is insufficient. This narrow interface is not a cache platform.

## Acceptance

The captured fixture has 144 Archive rows and 13 supplied Queue rows. The report
has 157 retained/evaluated contexts, one displayed candidate, and one request
CONT-SETUP result. Archive spatial audit: 96 MATCH and 48 NOT_EVALUATED; Queue:
1 MATCH and 12 NOT_EVALUATED. No row is excluded in this fixed replay. Existing
negative-case tests separately exercise excluded-row audit retention; zero
exclusions here do not demonstrate an exclusion event.

Current expected continuum distribution, established at `61813bd` / merge `c1785b2`
and preserved by the Archive line increment based on `3b6105b`:

| Result | Archive (144 contexts) | Queue (13 contexts) |
| --- | --- | --- |
| POS-SINGLE | 96 SATISFIED, 48 without outcome | 1 SATISFIED, 12 without outcome |
| Continuum branch | 91 CRITERIA_NOT_MET, 53 INDETERMINATE | 13 INDETERMINATE |

Thus the combined distribution is 91 not met and 66 indeterminate. This request
has no aggregate RMS: all CONT-RMS results lack an outcome. Explicit failures of
other approved criteria explain the 91 false AND branches. Archive ANGULAR uses
the approved scoped method; Queue retains its provisional method. The report
schema is owned by [evaluation_cli.md](evaluation_cli.md). Top-level
NOT_AGGREGATED does not erase the per-context continuum results.

Historical output at `6b48b3b` had all 144 Archive POS-SINGLE results unresolved;
it is superseded by the current expectation above. Counts are fixture observations,
not query filters or expected populations for future live acquisitions.

## Separate live acquisition

```bash
python examples/capture_ngc6240_archive.py --output-dir reports/ngc6240-new-capture
```

This explicitly contacts TAP and runs the production CLI with the same request
and fixed Queue input. It writes raw responses, manifest and a reporting.py live
report into a new directory. It will not overwrite existing evidence. Inspect
status/counts before accepting a new capture. The ordinary offline pytest suite
does not invoke this script; network and replay records remain separate.

## Scope of the evidence

The Archive position/angular and direct continuum workflow is confirmed in the
[decision record](evidence/supervisor_confirmation_2026-09-17.md#confirmed-2026-09-21).
Queue field/array inference, frame/offset conventions and RMS comparison retain
their independent limitations. Explicit USABLE widths in this request are
hypothetical declarations, not inferred from Queue nominal widths. Arbitrary
nominal conversion is not enabled. This real capture exercises data mapping;
[synthetic acceptance](confirmed_continuum.md) separately exercises numerical
positive cases. Neither is a live-service availability test or a reviewed real
duplication label.
