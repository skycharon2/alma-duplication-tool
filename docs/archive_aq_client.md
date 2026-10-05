# Live Archive AQ acquisition client

LIVE-AQ-2 provides an independent HTTP client. Import and construction perform no
network access. Only an explicit `fetch_members()` call retrieves AQ records.
The [assessment entry](live_aq_assessment.md) can now call an explicitly supplied
fetcher after TAP search. CLI and browser configurations do not enable it yet.

## Interface

```python
from alma_duplicate.clients import ArchiveAqClient

result = ArchiveAqClient(max_hits=100).fetch_members(member_ous_uids)
catalog = result.catalog
queries = result.queries
```

An optional `request` callable follows `requests.request(method, url, **kwargs)`;
it lets tests exercise the same interface with fake HTTP responses. Members must
be `uid://<part>/<part>/<part>` identifiers with alphanumeric parts. All inputs
are validated before HTTP. Duplicate Members are queried once in first-seen
order; empty input returns an empty LIVE catalog and no queries without discovery.

The client discovers the search base through the official properties endpoint,
then POSTs one exact Member query with `track_total_hits=true` and the configured
`size`. Only the observed HTTPS host and `/aq/service/api/search` path are
accepted, with no user information, query or fragment and no nonstandard port.
The observation endpoint is constructed explicitly. Redirects are disabled for
both discovery and search. Connect/read timeouts are 10/60 seconds per request;
there is no automatic retry, pagination or total batch deadline.

Every Member response must explicitly have `timed_out=false`, zero failed
shards, an exact nonnegative integer total, and a hit count equal to that total
and no greater than `max_hits`. Early termination is rejected. Missing or
malformed completeness fields are errors. HTTP status must be 200. Malformed
JSON, duplicate JSON keys and non-finite JSON literals are rejected.

Every hit retains its ID, Member, source name and optional array label. Returned
Members must equal the requested Member. The client preserves all sources,
including calibrators and duplicate hits; it does not choose a target or interpret
array labels. Missing/unknown labels remain available for the existing
[exact binder](archive_array_evidence.md) to classify as unresolved.

## Results and failures

`ArchiveAqFetchResult` contains:

- a catalog with LIVE provenance and no captured manifest hash;
- one `ArchiveAqMemberQuery` per successful Member, including zero-hit queries;
- the properties endpoint used for discovery.

Each query records Member scope, search endpoint, UTC response-receipt time,
SHA-256 of original response bytes, exact total and requested maximum. Records
carry the same response identity and timestamp. Request projection and exact
Member query semantics are fixed by this client contract. No credentials,
properties response, headers or raw response body are saved in these results.
There are no disk writes. The optional properties API key is used only in the
validated search request's Authorization header.

A failure raises `ArchiveAqError` with a stable code and, for Member requests,
the affected Member. Codes are `TRANSPORT_ERROR`, `HTTP_ERROR`, `JSON_INVALID`,
`DISCOVERY_INVALID`, `RESPONSE_INVALID` and `INCOMPLETE`. Public exception messages
omit response bodies, credential values and underlying HTTP error text. Invalid
caller arguments raise `ValueError` before acquisition. No partial result is
returned if a later Member fails. A successful empty response is distinct from
acquisition failure. Callers must not convert errors into an empty successful
catalog or a negative duplication result.

The service is a web-application endpoint, not a promised stable ingestion API.
This client retains the binding semantics established by the
[dated probe](evidence/live_aq_source_binding_probe_2026-10-02.md), without claiming
that offline verification establishes current remote availability.

## Verification and next steps

`tests/unit/test_archive_aq_client.py` uses fake HTTP, including replay of the
five unchanged official response captures. It checks complete, empty, truncated,
malformed and failed results; identity scope; duplicates; URL and redirect
restrictions; credentials; and all-or-nothing multi-Member acquisition.

LIVE-AQ-3 now connects retained TAP candidates to unique-Member acquisition and
carries query provenance through assessment/report assembly when explicitly
configured by a Python caller. LIVE-AQ-4 will expose
explicit browser configuration. These integrations must preserve failed versus
empty acquisition, exact source binding, and independent TAP/AQ provenance.
No scientific method, rule version, TP scope or historical capture is changed
by this client increment.
