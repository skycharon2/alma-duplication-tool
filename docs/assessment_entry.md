# Shared assessment application entry

`alma_duplicate.assessment.assess_observation(request, search_options, ...)`
accepts the existing request dictionaries and returns `AssessmentResult`.
It owns validation, valid SUN exemption, method/source selection checks,
search, source-specific evaluation and report assembly. No scientific method,
report version or default Queue method changes in this extraction.

## Ownership

- Application: validation and execution order; structured status and report.
- CLI: strict JSON file decoding, SHA-256 of the original bytes, argument parsing,
  path protection, client/provider construction, report writing and exit codes.
- Future UI: form/upload decoding, explicitly selecting formal Queue methods,
  displaying effective configuration and the same report, download handling.

The browser UI is not included in this increment. Direct application calls and
CLI calls are compared using offline sources. A rendered UI agreement test
remains part of the UI delivery, not a completed claim here.

## Lazy source contract

`AssessmentSources.archive_provider` is called only after request and option
validation. It returns `ArchiveInput(client, replay_metadata)`; `archive_kind`
is `LIVE` or `REPLAY`, and must be supplied together with the provider. Neither
is supplied when Archive input is unavailable. `queue_loader` is the existing
lazy Queue loader accepted by candidate search. No default network client is
created by the application module.

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
| SOURCES_UNAVAILABLE | At least one source FAILED, INCOMPLETE or NOT_PROVIDED | Preserve report, exit 3 |

Exceptions remain exceptions; CLI maps its existing OSError/UnicodeError/ValueError
set to exit 2. COMPLETED never means criteria passed or that no duplicate exists.
Read context branches, pair criteria, source states and scope from the document.

## Method selection and provenance

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
