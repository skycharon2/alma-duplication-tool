# Archive mirror failover

Live browser TAP and optional live AQ use Europe, East Asia, then North America:

1. `https://almascience.eso.org`
2. `https://almascience.nao.ac.jp`
3. `https://almascience.nrao.edu`

The evaluation CLI uses the same TAP policy for `--live-archive`. Offline replay,
captured AQ input and Queue download/activation are unchanged. Direct
`ArchiveClient(endpoint)` and `ArchiveAqClient(origin=...)` remain single-site
clients; shared-entry callers opt in by supplying the mirrored clients.

The official [Archive access guidance](https://help.almascience.org/kb/articles/i-can-t-access-the-archive-query-interface-at-my-arc-how-can-i-get-my-data)
identifies all three ARC mirrors as copies of the Archive. The official
[TAP notebook](https://almascience.nrao.edu/alma-data/archive/archive-notebooks/nb1_ALMA_Query_one_source.html)
lists the corresponding `/tap` services. Mirror availability does not establish
that simultaneous responses are byte-identical or constitute the same snapshot.

## Retry boundary

Each site is attempted at most once per operation. A successful complete result,
including zero rows, ends failover. Never query another site merely to obtain a
preferred scientific result, missing array label or more candidates.

- TAP retries transport/service errors, malformed responses, missing query status,
  invalid COUNT evidence, overflow and count mismatch. A new client repeats the
  whole query, including metadata and completeness checks. Query errors and core
  schema drift stop rather than silently changing the requested contract.
- AQ retries transport errors, invalid responses, incomplete batches and HTTP
  408/429/5xx. Other HTTP failures and invalid discovery endpoints stop. Discovery
  credentials are used only on the selected mirror's own validated HTTPS origin;
  discovery and search redirects remain disabled.
- AQ starts the entire unique Member batch again at the next site. Records from
  failed attempts are discarded. A successful partial Member prefix is never
  combined with another mirror's remaining Members.
- TAP and AQ switch independently. AQ still binds to the exact retained TAP
  Member/source identity; a missing or conflicting binding stays unresolved.
- When attempts are exhausted, TAP remains failed/incomplete and AQ leaves the
  retained candidates with unavailable array evidence. No replay, raw-label or
  successful non-duplication fallback is introduced.

Ordinary TAP HTTP 4xx failures other than 408/429 are treated as nonretryable
request errors. Programming errors and invalid caller arguments are not retried.

## Time and configuration

Each TAP search and each AQ batch has a separate 180-second scheduling budget.
Before a new HTTP request or mirror attempt, the remaining budget is checked.
Connect and idle-read timeouts are capped at 10 and 60 seconds respectively and
reduced when the remaining budget is smaller. There are no background retries,
sleeps or unbounded retry loops.

This is not a hard wall-clock deadline: a response that continuously delivers
bytes, local parsing, DNS resolution or scientific evaluation can extend elapsed
time. The budget does not forcibly cancel in-flight I/O. TAP and AQ have separate
budgets; the complete browser assessment has no fixed 180-second duration limit.

Python callers may select a nonempty unique subset/order of the three official
origins through `origins=...` and set `budget_seconds=...` on
`MirroredArchiveClient` or `MirroredArchiveAqClient`. Other origins are rejected.
The browser form also offers Automatic, Europe, East Asia and North America.
Automatic uses the default order; an explicit region restricts both TAP and live
AQ to that site, with no cross-region fallback. Each assessment uses its own
selection; it does not change server defaults or active Queue data. This transport
selection is separate from the scientific request JSON; reports retain actual
endpoints and attempt history.

## Provenance and reports

TAP keeps the successful (or last unsuccessful) query's endpoint, query hash,
run ID, statuses and counts. `source_metadata.provenance.mirror_attempts` adds
ordered attempt origins, timestamps, statuses, error kinds and query identities.
Final source-state gates prevent using unsuccessful rows for science.

AQ stores successful batch query URLs, response hashes and timestamps as before.
`array_evidence.acquisition.mirror_attempts` records attempted origins and safe
failure codes, including HTTP status and failing Member where available. API
keys, headers and response bodies are never included. Failed-batch source records
and response hashes are not retained as scientific evidence. Captured AQ manifests
accept only the exact official observation-search URL on one of the three origins.
Original URLs are preserved; captured data never triggers automatic network access.

These are additive transport provenance fields. Scientific method versions,
full report v4, matching-detail v6 and inspection v3 semantics are unchanged.
Older reports without mirror fields remain readable. The AQ view exposes attempts;
TAP attempts are included in the existing source metadata details and JSON export.

## Verification

On 2026-10-16, read-only checks at all three origins returned HTTP 200 for AQ
properties, a `SELECT TOP 1 member_ous_uid FROM ivoa.obscore` TAP query, and an AQ
query for that site's returned Member. Each TAP VOTable parsed successfully; each
AQ response had an exact total equal to returned hits, no timeout and zero failed
shards. This verifies basic interface compatibility, not continuous availability
or identical cross-site snapshots. No credentials or observation contents were
saved by the probe.

Offline tests inject failures and verify retry order, whole-batch restart,
complete-empty stopping, nonretryable errors, all-site failure, time budget,
source provenance, same-origin credentials and browser exports. No default test
contacts a live service.

## Browser status

The proposal form places an Archive connection selector in Data sources alongside
Queue source status. The default is Automatic; selecting a region restricts the
connection to that site. Selection survives form edits and validation. Loading
the form never probes remote services; retrieval begins only on assessment.
Replay and unconfigured modes do not offer live connection choices. Each report shows its own TAP and optional
AQ retrieval status, actual region and whether a successful mirror switch occurred.
The Details button shows ordered attempts and completion timestamps. Failed or
incomplete retrieval stays visibly marked "Needs attention". Recorded/replay data
is identified separately, and older reports without attempt metadata show that
history as unrecorded. These are per-assessment observations, not a persistent or
current service-health monitor, and opening a report performs no new requests.

On the proposal form, Archive connection settings are contained in a Details
popover beside the compact Archive summary, matching the Queue status pattern.
The summary reflects the selected site; the popover says "Not checked" until an
assessment runs. Done, Escape or an outside click closes the popover without
submitting the form or discarding the selection. The hidden popover's select is
still part of the observation form and is submitted normally.
