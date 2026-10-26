# Mosaic Archive candidate discovery

This bounded discovery path searches every supplied OT pointing rather than applying
single-pointing candidate-centre filtering. The existing single-pointing search is
unchanged. It searches science rows across candidate geometries. Geometry flags are retained
per Member/target; only explicitly single-field rows use the TAP centre route.
Queue sources are not covered. Discovery alone does not evaluate duplication.

Each ADQL request combines at most 20 spherical region predicates with OR. Zero
margin uses POINT containment in s_region; a positive explicit margin uses CIRCLE
intersection. RA wrap and polar geometry are handled by TAP spherical predicates.
Duplicate proposed coordinates share a retrieval predicate but retain their input
row IDs; this does not deduplicate the proposed-pointing assessment denominator.
Missing s_region rows are included through one separate IS NULL request rather than
silently excluded or OR-combined into every spatial query. That fallback may cause
large or truncated responses. A failed fallback makes the run INCOMPLETE.

The margin is a caller-selected discovery parameter, not the half-power radius or
an approved uncertainty. s_region is not established to equal or contain reconstructed
half-power coverage. Consequently, even successful queries do not guarantee complete
recall. Missing, restricted, underestimated or erroneous regions can affect discovery.
Do not interpret an empty search as non-duplication. Do not apply the >50% rule to
counts of query hits; only reconstructed coverage can support that rule.

## Plan without network access

```bash
python -m alma_duplicate.cli.mosaic_candidate_discovery \
  --pointings tests/fixtures/ot_pointings/c04_degrees.txt \
  --source P2B_C04_PRECISION --array 12m --confirm-fixed-icrs \
  --margin-arcsec 0 \
  --output-dir reports/mosaic-dev/ot-discovery-plan-01
```

Add `--live` with a new output directory to execute the queries against the official
Archive TAP service. The current file is a controlled parser test, not an IC1954
proposal. Use the intended OT file for science candidate discovery.

Runs accept 1–2000 unique proposed positions and a finite margin from 0 to 3600
arcsec. Each request has MAXREC 10000, a 2 MB response limit and a 30-second network
timeout. Requests are sequential. Raw responses, hashes, request URLs/ADQL and errors
are retained. TAP OVERFLOW, a response reaching MAXREC, invalid XML or HTTP failure
makes the run INCOMPLETE; successful batches remain available. Queries do not use
TOP and no failed batch is converted into an empty successful result.

Candidates group by project, Member UID and exact target name. Observed ASDM UIDs
and originating query indices are preserved, together with observed `geometry_flags`. Query indices indicate batch hits,
not verified per-point matches. Different targets are never merged merely because
they share a Member. Mosaic candidates still need reconstructed executions; Single Pointing candidates
use validated TAP centre metadata and AQ array evidence. Unknown geometry stays unresolved.

`discovery.json` retains all query status and provenance. `candidates.json` contains
identity-only entries for the candidate-assessment manifest: they will report missing
coverage until evidence paths and explicit SPW selections are supplied. Always inspect
`discovery.json` for INCOMPLETE status and recall limitations. The assessment loader
currently accepts at most 100 candidates; larger result sets require explicit batching,
not truncation. An empty identity list is a discovery result, not an executable
assessment request. Existing run directories are never overwritten.

Exit 0 means planning succeeded or every query completed, 3 means incomplete live
retrieval, and 2 means invalid input or local execution failure. Neither 0 nor 3
constitutes a duplication verdict.

## Live acceptance — 2026-10-23

The initial C04 live request combining spatial predicates with `OR s_region IS NULL`
timed out. Read-only diagnostic queries established that the service was reachable:
a known-Member query completed in about 3.2 seconds, a single IC1954 region query
in about 0.3 seconds, and the null-region count in about 1.0 seconds (zero rows at
that time). This suggested a query-shape issue rather than proving a server outage;
server execution plans were not inspected.

After separating the null-region fallback, official ESO TAP acceptance completed:

| Input | Margin | Requests | Candidates | Result |
| --- | --- | --- | --- | --- |
| C04 native test export | 0 arcsec | 2 | 0 | COMPLETED |
| 22 synthetic IC1954 centre probes | 0 arcsec | 3 | 2 | COMPLETED |
| Same IC1954 probes | 1 arcsec | 3 | 2 | COMPLETED |

Both IC1954 runs retained the expected Member `uid://A001/X1284/X28b7`; the other
Member was `uid://A001/X1284/X28b5`. Raw response hashes and row counts were verified.
Local receipts and responses are under `reports/mosaic-dev/` in the corresponding
`*-discovery-acceptance-*` directories. The summary is
`discovery-acceptance-summary-01.json`. The IC1954 inputs are synthetic probes at
known science centres, not an actual proposed observation or an OT export.

These checks establish live query execution and known-case recovery, not global
recall of reconstructed half-power coverage. The successful empty C04 result is
not a non-duplication verdict. Missing-region fallback is still mandatory even
though its result was empty during this acceptance run.
