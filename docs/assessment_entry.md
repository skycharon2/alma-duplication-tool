# Shared assessment application entry

Report retention is selected separately with `report_detail='full'` (default v4)
or `'matches'` ([v5 contract](matching_report.md), browser default). All retained
contexts are evaluated in either mode; scientific options are unchanged.

`alma_duplicate.assessment.assess_observation(request, search_options, ...)`
accepts the existing request dictionaries and returns `AssessmentResult`.
It owns validation, valid SUN exemption, method/source selection checks,
search, source-specific evaluation and report assembly. No scientific method,
report version or default Queue method changes in this extraction.

## Ownership

- Application: validation and execution order; structured status and report.
- CLI: strict JSON file decoding, SHA-256 of the original bytes, argument parsing,
  path protection, client/provider construction, report writing and exit codes.
- UI: form/upload decoding, explicitly selecting formal Queue methods,
  displaying effective configuration and the same report, download handling.

The original entry extraction preceded browser delivery. The current browser
calls this entry; its [offline parity gate](ui_offline_assessment.md#offline-uicli-parity-gate)
is implemented. The optional live AQ wiring below does not add browser controls.

## Lazy source contract

`AssessmentSources.archive_provider` is called only after request and option
validation. It returns `ArchiveInput(client, replay_metadata, array_catalog)`;
the optional `array_catalog` supplies captured
[source-bound official array evidence](archive_array_evidence.md).
`archive_kind`
is `LIVE` or `REPLAY`, and must be supplied together with the provider. Neither
is supplied when Archive input is unavailable. `queue_loader` is the existing
lazy Queue loader accepted by candidate search. No default network client is
created by the application module.

Optional `archive_array_fetcher` runs only after completed TAP search with retained,
linked Archive Members. It requires LIVE Archive input and cannot coexist with a
preloaded catalog. The [live AQ assessment contract](live_aq_assessment.md) defines
skips, acquisition failures, query provenance and no-fallback behavior.

Invalid/non-search-ready requests return validation details and no document.
Valid SUN returns an exemption before method checks or any source provider call,
matching the existing CLI behavior. Invalid supplied SUN fields cannot bypass
request validation. Source query/load failures retain the candidate-search
layer's existing isolation. Provider construction errors propagate to the caller,
as they did in the CLI; this increment does not redefine source failure semantics.

## Execution status is not a science result

| Status | Meaning | Existing CLI handling |
| --- | --- | --- |
| REQUEST_NOT_SEARCH_READY | Validation/search readiness failed; no report | Diagnostics, exit 2 |
| SOLAR_EXEMPTION | Valid SUN; no source access | Exemption report, exit 0 |
| COMPLETED | Execution finished without unavailable selected sources | Report, exit 0 |
| SOURCES_UNAVAILABLE | At least one selected source FAILED, INCOMPLETE or NOT_PROVIDED, or enabled live AQ acquisition failed/is incomplete | Preserve report, exit 3 for currently exposed CLI paths; no live AQ CLI switch yet |

Exceptions remain exceptions; CLI maps its existing OSError/UnicodeError/ValueError
set to exit 2. COMPLETED never means criteria passed or that no duplicate exists.
Read context branches, pair criteria, source states and scope from the document.

## Method selection and provenance

`AssessmentOptions.nominal_conversion` defaults to `PORTAL_SCRIPT_V1`. It is
selected only for CONTINUUM with NOMINAL windows and no explicit setup
declaration; `None` disables it. Unknown names fail before source access.
The [project adoption](evidence/proposed_usable_bandwidth_decision_2026-10-07.md)
versions this proposed conversion as approved `continuum_setup_4`. Browser and
CLI share this default and retain the original request values in reports.

`AssessmentOptions` exposes the existing beam/filter options and explicit
`queue_common`, `queue_continuum`, `queue_line` booleans. Their defaults remain
False. Selecting Queue alone never enables formal Queue science. A UI must
explicitly enable the selected supported intents and display the report's
`evaluation_configuration`; it must not compute formulas itself.

`input_sha256` is optional: pass the digest of actual original input bytes when
available. Do not invent a file digest for a form dictionary. A missing digest
remains null. Report generation and inspection versions remain unchanged.

Output paths do not enter this API. CLI guards against replacing request, Queue,
replay manifest and replay response files. Its Solar/replay overwrite restriction
also remains intact. Other frontends must protect their own storage boundary.
