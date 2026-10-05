# Live AQ evidence in shared assessment

LIVE-AQ-3 connects the independent AQ client to `assess_observation()` through
an explicitly supplied `AssessmentSources.archive_array_fetcher`. No default AQ
client is constructed by the shared entry. The browser now has an
[explicit AQ flag](ui_offline_assessment.md#explicit-live-aq-configuration);
the CLI has no live AQ switch yet.
The [client](archive_aq_client.md) and [exact binder](archive_array_evidence.md)
retain their existing scientific and transport contracts.

## Interface and order

```python
from alma_duplicate.assessment import ArchiveInput, AssessmentSources, assess_observation
from alma_duplicate.clients import ArchiveAqClient

# tap_client and the request dictionaries are supplied by the caller.
aq = ArchiveAqClient()  # Construction does not access the network.
sources = AssessmentSources(
    archive_kind="LIVE",
    archive_provider=lambda: ArchiveInput(tap_client),
    archive_array_fetcher=aq.fetch_members,
)
result = assess_observation(request, search_options, sources=sources)
```

The fetcher accepts a tuple of unique Member UIDs and returns
`ArchiveAqFetchResult`. Tests inject fake HTTP through the same AQ client.

1. Validate the request, handle valid Solar exemption, and check configuration.
2. Construct the lazy Archive provider. Reject a preloaded `array_catalog` together
   with a fetcher before TAP search; neither source of array evidence wins silently.
3. Complete candidate search with existing TAP/Queue behavior.
4. From **all retained Archive contexts**, collect Members from linked
   Source–SPW associations, deduplicating in retained-context order. Display limits
   do not affect acquisition or evaluation. Excluded rows and unlinked contexts
   supply no Member to query. A linked row with a source-name conflict still
   reaches the exact binder, which keeps that conflict unresolved.
5. Acquire AQ records, bind exact source identities and evaluate every retained
   candidate. Member is only query scope, never a substitute for source identity.
6. Assemble report v4 with separate TAP and AQ provenance, then return execution
   status. Queue criteria and source status are independent of AQ acquisition.

Live AQ requires ARCHIVE selection and `archive_kind="LIVE"`. Replay plus live
AQ is rejected before provider construction. Invalid/non-search-ready and valid
Solar requests return before any provider or fetcher access, preserving the
existing exemption order. Conflicting configuration cannot silently enable AQ.

## State contract

When a fetcher is configured, an array catalog is always supplied to evaluation,
including on failure or skip. Passing `None` would enable legacy TAP-only
inference, so this path never does that. Empty catalogs used on failure represent
unavailable evidence, not successful empty acquisition.

| AQ acquisition state | Meaning | Array evaluation and execution status |
| --- | --- | --- |
| Not configured | Existing captured catalog or legacy TAP-only route | Existing behavior and report shape |
| COMPLETED, matches present | Whole requested batch passed client checks | Exact binder determines each context's array evidence |
| COMPLETED, zero hits or missing target | Successful queries are retained, including zero-hit records | Affected contexts remain UNKNOWN; execution may be COMPLETED |
| FAILED | An expected acquisition error, including discovery, HTTP, transport or invalid response | No partial catalog; retained Archive contexts remain unresolved; result status SOURCES_UNAVAILABLE |
| INCOMPLETE | Timeout flag, truncation or another client completeness rejection | Same no-fallback behavior; result status SOURCES_UNAVAILABLE |
| SKIPPED / TAP_NOT_COMPLETED | TAP did not finish successfully | No AQ call; preserve TAP failure/incompleteness and its candidates contract |
| SKIPPED / NO_RETAINED_ARCHIVE_CONTEXTS | No candidate needs array evidence | No AQ call; no scientific absence verdict is added |
| SKIPPED / NO_LINKED_ARCHIVE_MEMBERS | Retained contexts lack linked Member identities | No AQ call; contexts remain unresolved; execution may be COMPLETED |

Only `ArchiveAqError` is converted to FAILED/INCOMPLETE. Unexpected exceptions
and violated provider contracts propagate. Returned catalogs must be LIVE,
query Members must exactly match the requested unique tuple, and record counts,
URLs, timestamps and response hashes must agree with their query records.

The AQ client is all-or-nothing: if a later Member fails, no earlier successful
records are used. `requested_members` records the planned batch, not proof that
every Member was contacted. On failure, `queries` is empty because the client
returns no successful acquisition result; `error.member_ous_uid` identifies the
failing Member when available. Discovery errors may have no Member. No response
body, credential or underlying exception text is added to the report.

## Report and inspection

The existing `sources.ARCHIVE.status` continues to describe TAP retrieval.
AQ status does not overwrite TAP status. The optional
`sources.ARCHIVE.array_evidence.acquisition` object contains:

- `status`, optional skip `reason`, and planned `requested_members`;
- successful `queries`, each with Member, endpoint, capture time, original-byte
  SHA-256, total hits and maximum hits;
- safe `error` code and Member on acquisition failure;
- UTC `started_at` / `finished_at` for an attempted batch, null when skipped;
- the discovery `properties_url` on success.

The containing array evidence metadata retains LIVE scope, record count and
binding method identity without a captured manifest hash. For this explicitly
enabled path, report v4 also includes `assessment_status`, matching the returned
`AssessmentResult.status`. AQ failure makes it SOURCES_UNAVAILABLE even when
TAP and Queue retrieval both succeeded. `assessment=NOT_AGGREGATED` and the
absence of a search-wide duplication verdict remain unchanged.

Inspection v3 adds one `ARCHIVE_AQ_FAILED` or `ARCHIVE_AQ_INCOMPLETE` occurrence
at `sources/ARCHIVE/array_evidence/acquisition`, categorized as
SOURCE_OR_SEARCH_INCOMPLETE. Context evidence gaps remain separate occurrences.
Versions 1/2 retain their historical behavior and do not add this new acquisition
summary. Reports without live acquisition retain their existing inspection output.

Scientific method identities, exact binder behavior, D7/D12 complete-branch OR,
TP position/scope rules, units and original candidate identities are unchanged.
No acquisition result can borrow a calibrator label for the science target.

## Verification and remaining work

Offline integration tests cover ordered TAP/AQ execution, hidden candidates,
deduplication, exclusion/unlinked handling, empty/failing/incomplete acquisition,
no fallback, source isolation, configuration guards, provider contract errors,
complete beam alternatives, report serialization and inspection pair pointers.
Existing report consumers can read the additive evidence; no UI control is added.

LIVE-AQ-4 adds explicit browser configuration and renders acquisition status
in the execution flow. A CLI switch remains separate work. Live-service smoke
verification and real-proposal scientific acceptance are not claimed by these
fake-HTTP tests.
