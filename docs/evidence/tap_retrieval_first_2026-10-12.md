# Live Archive retrieval-first comparison — 2026-10-12

## Scope and result

One sequential CASE1 continuum comparison used the production browser backend,
live ESO TAP, live AQ and temporary browser report storage. The input was identical
for both policies. The reviewed code baseline is `a920761` plus the local profiling,
compact-report and retrieval-first changes; this record does not claim a new commit.

| Measured phase | COUNT_FIRST | STATUS_THEN_COUNT |
|---|---:|---:|
| Whole profiled workflow | 110.796 s | 61.429 s |
| TAP, including metadata and parsing | 94.918 s | 47.496 s |
| Independent COUNT | 47.040 s | Not executed |
| Retrieval | 47.358 s | 47.274 s |
| AQ | 15.102 s | 13.094 s |

The observed workflow reduction was about 44.6%. The removed COUNT explains
about 47 seconds; AQ latency also varied. This is one pair, not a general speed
guarantee. Retrieval itself still takes about 47 seconds. HTTP, Jinja rendering
and browser painting are excluded. Local regression tests ran during portions
of the investigation; server load and caching were uncontrolled.

## Input and identity checks

CASE1: RA `18:33:39.920`, Dec `-21:03:39.900`, angular resolution `0.23 arcsec`,
representative SKY frequency `290.420 GHz`, aggregate RMS `0.02 mJy/beam`, and an
explicit continuum setup declaration. AUTO retrieval and ARCHIVE were selected.
The complete request and original request-file SHA-256 are in the
[machine-readable record](tap_retrieval_first_2026-10-12.json).

Both runs returned:

- 336 identical TAP rows as a multiset, preserving duplicate occurrences;
- 336 retained comparison contexts;
- 16 matching comparisons across 4 Member OUS identifiers;
- 320 comparisons not meeting the continuum criteria;
- successful TAP and AQ acquisition, with 68 Member requests each.

The expected CASE1 project `2021.A.00028.S`, target `PKS1830-211`, Member
`uid://A001/X2df9/X1b`, ASDM `uid://A002/Xfd251c/X7ba5`, and SPWs 25/27/29/31
remain represented in the matching results.

Comparison of all context records resolves shared summary references, replaces
each run's generated TAP query ID with a common token, and excludes only AQ
`retrieved_at` and `response_sha256` fields. All remaining context identity,
array evidence, criteria, comparison values, method versions and branch records
agree. The original reports retain their own timestamps, query IDs and response
hashes; they are not byte-identical. Report hashes are recorded for traceability.
Local diagnostic reports and scripts are under
`reports/tap-retrieval-first-2026-10-12/` and are not repository fixtures.

## Completeness boundary

The [client contract](../archive_client_contract.md#browser-retrieval-first-policy)
defines the exact checks. The browser omits COUNT only for a fully parsed, explicit
successful VOTable response with the required columns and fewer rows than MAXREC.
This relies on the service's overflow reporting as required by
[TAP 1.1](https://www.ivoa.net/documents/TAP/20190927/REC-TAP-1.1.html), sections
2.7.4 and 3.4. It cannot independently detect a nonconforming server silently
omitting rows while claiming success. Direct/CLI clients and replay defaults
retain independent COUNT reconciliation.

The original query predicate and AUTO radius are unchanged. Planned COUNT ADQL
remains available to exact query binding even when not executed; provenance then
records `count_attempted=false` and a null expected count. The browser does not
invent an independently measured total. Unknown completeness cannot authorize
reconstruction or a negative duplication conclusion.

A separate conservative declination-bound probe returned the same 336 rows but
took 47.732 seconds for COUNT alone. That change was not adopted.

## Validation

- Full suite: **1932 passed, 12 skipped**.
- Ruff F checks and `git diff --check`: passed.
- Tests cover valid empty results, exactly MAXREC, mismatched counts, OVERFLOW,
  missing/unknown status, schema drift, failed COUNT, failed retrieval and
  malformed/truncated VOTable responses.
- Real VOTable parsing tests include a trailing OVERFLOW and missing status.
- Shared-entry tests exercise the production Archive client, query binding,
  retained Member acquisition and identical context records with fixed evidence.
- Browser provider tests check selection of the retrieval-first policy and
  preserve lazy initialization and failure behavior.

This is an engineering and result-parity check for one live continuum input.
It does not extend support to mosaic, moving targets or TP, and does not establish
complete scientific acceptance across all Archive and Queue cases.
