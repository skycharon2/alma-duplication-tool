# Browser assessment sources

The browser can execute its current form against explicitly configured sources:
form → shared validator → `assess_observation()` → independent report → exports.
Archive access is `NONE`, replay or live TAP; Queue remains an optional local CSV.
Scientific formulas, method versions, source association and aggregation remain
owned by the existing backend. Live TAP alone does not enable live AQ. An
additional explicit operator flag enables the existing post-TAP AQ backend;
no scientific scope is added.

## Run locally

From the repository root, with `.[test,ui]` installed:

```bash
export ALMA_UI_ARCHIVE_REPLAY="$PWD/examples/confirmed_line/archive/manifest.json"
export ALMA_UI_QUEUE_CSV="$PWD/examples/acceptance/queue/dual-source-line.csv"
python -m flask --app alma_duplicate.ui.app:create_app run --host 127.0.0.1 --port 5001
```

Open http://127.0.0.1:5001/proposed. These committed examples are synthetic
engineering reference data, not current observatory holdings or reviewed real
proposals. Existing `ALMA_UI_REPORT_DIR` configuration is independent and optional.
Neither form validation nor application startup reads assessment source files or
contacts Archive TAP.

For live Archive TAP, do not configure `ALMA_UI_ARCHIVE_REPLAY`; instead set
`ALMA_UI_LIVE_ARCHIVE=1`. The live flag accepts explicit boolean spellings and
rejects unrecognized values. Live TAP and replay are mutually exclusive. The live
Archive client is created only for a valid, search-ready Run assessment that
selected ARCHIVE; GET, validation, request download, invalid input, Solar and
QUEUE-only execution do not create it.

Run assessment appears when at least one assessment source is configured. The
browser enables it only for fixed single-point requests, and rejects other
observation types at the server before execution. Moving/Mosaic and Sun selections
remain available for validation and valid-request export; see
[observation support](ui_proposed_form.md#observation-type-and-support).
The browser cannot supply file paths. Selecting an unconfigured source yields the
backend's NOT_PROVIDED state. Source files are read for each run, so their backend
hashes and provenance describe that run. Providers are constructed per selected
execution. A live Archive failure is not replaced by replay results.

Optional `ALMA_UI_ARCHIVE_ARRAY_EVIDENCE` supplies a captured official AQ
manifest to the same lazy Archive provider. It must correspond to the actual
Archive science sources for that run; unmatched sources remain UNKNOWN. A live
TAP run does not automatically refresh or acquire AQ evidence. The browser keeps
one original candidate with both complete diameter paths when the backend
returns mixed evidence, displays the binding provenance and exports the original
report/inspection. TP's physical 12-m aperture does not remove its unsupported
scientific scope. See the [array adapter](archive_array_evidence.md).

### Explicit live AQ configuration

For live TAP plus live AQ, start from a shell with no replay or captured AQ path:

```bash
unset ALMA_UI_ARCHIVE_REPLAY ALMA_UI_ARCHIVE_ARRAY_EVIDENCE
export ALMA_UI_LIVE_ARCHIVE=1
export ALMA_UI_LIVE_ARCHIVE_AQ=1
python -m flask --app alma_duplicate.ui.app:create_app run --host 127.0.0.1 --port 5001
```

`ALMA_UI_LIVE_ARCHIVE_AQ` maps to Flask configuration `LIVE_AQ`. It uses the same
explicit boolean parsing as `LIVE_ARCHIVE`; direct application configuration
requires actual booleans. These are operator settings, not researcher form fields.

| Archive mode | Additional AQ evidence | Allowed |
| --- | --- | --- |
| Live TAP | None, captured manifest, or live AQ (one route only) | Yes |
| Replay TAP | None or captured manifest | Yes |
| Replay TAP | Live AQ | No |
| No live TAP | Live AQ | No |
| Live TAP | Captured manifest and live AQ together | No |

Conflicting settings fail during application construction without source access.
An absent/false AQ flag preserves the previous TAP-only or captured-evidence
behavior. The form displays the configured route without exposing local paths.

The browser passes a lazy callback to the shared entry; it does not extract
Members or interpret arrays. The AQ client is constructed inside that callback
only after successful TAP search has retained linked Members. Startup, GET,
validation, request export, invalid/unsupported requests, Solar, Queue-only runs,
failed/incomplete TAP, empty retained results and no linked Members never create
the AQ client. One batch call may make multiple HTTP requests internally.

Report Sources show TAP status and AQ provenance/acquisition separately.
COMPLETED with zero hits, FAILED, INCOMPLETE and SKIPPED have distinct messages.
Skipped runs display the backend reason. AQ failure still produces an available
report with retained candidates, unresolved Archive array evidence and independent
Queue results. It is not the exception path that creates no report. Planned
Members are not mislabeled as completed queries; failed batches retain no partial
query results. No captured, TAP-label or replay fallback is added.

Both saved reports and current runs render only their own provenance, even after
operator configuration changes. Older reports without acquisition fields remain
readable without claiming a live lookup. Query details include zero-hit records,
timestamps, endpoint and response hash. External text is escaped. Report,
inspection and request downloads retain original bytes; viewing, pagination and
downloads never re-run acquisition. Each execution creates a separate catalog and
run. No background worker, automatic retry or stage-progress estimate is added.

`tests/ui/test_live_aq.py` verifies the matrix, lazy lifecycle, failure messages,
stored-report compatibility, escaped values, run isolation and exact exports.
Browser/shared-entry parity uses a fixed AQ clock and the existing normalization
of execution timestamps. Real network access is forbidden in these tests. This
does not establish live service availability or a reviewed real-proposal result.

### Guide B form check

| Input | Value |
| --- | --- |
| RA / Dec | 201.365 / -43.019, both DEG |
| Purposes | LINE |
| Requested angular resolution | 0.3 arcsec |
| Source redshift | 0.024 |
| Requested line / SPW centre frequency | 230.538 GHz, REST (LINE opens the first entry; Add line / window adds more) |
| Declared correlator mode | FDM |
| Planned LINE resolution / RMS | 20 km/s / 0.3 mJy/beam |
| Complete window list | Checked |
| Search radius | 30 arcsec |
| Sources | ARCHIVE and QUEUE |
| Candidate display limit | 1 |

Window and setup identities are supplied by the form. Click Run assessment.
The response redirects to `/runs/<id>`. Expect report v4, separate source states,
independent branch/pair evidence and explicit effective evaluation configuration.
This is a new computation using the entered fields, not a saved acceptance report.

Download the complete report, inspection v3 and this run's input request. Refresh
or repeat a download: the report bytes, generated timestamp and SHA-256 stay the
same. Editing and running a different input creates another ID and does not
replace the first report. The display limit never trims the report's evaluated
contexts or the complete download.

### Deliberate partial and failure checks

- Omit SPWs for a CONTINUUM request with representative 230 GHz and aggregate
  0.1 mJy/beam: a valid, search-ready input still runs. Setup-width evidence
  remains missing, not satisfied by selecting CONTINUUM. Alternatively, explicitly
  confirm the [setup declaration](continuum_setup_declaration.md) to use researcher
  evidence for this criterion. Do not mark an omitted window list complete.
- Enter negative RMS or omit the search radius: no assessment is invoked; the
  form retains the entered values and validator diagnostics.
- Change radius to 31 arcsec: the replay query no longer matches. Preserve the
  backend's Archive failure and any available Queue results; no live fallback.
- Omit Queue configuration but select QUEUE: preserve NOT_PROVIDED alongside
  available Archive results.
- A missing/malformed replay manifest can fail provider construction. Show an
  execution error with the form preserved; do not create a fabricated report.

Archive replay matches exact query/maxrec, including coordinates, radius and
search strategy. It is not an offline database for arbitrary targets. Capture
metadata and fixture kind come from the backend report. Queue snapshot provenance
is shown in source evidence; parse time is not represented as the source date.

## Ownership and execution

`ui/runs.py` supplies lazy replay/live Archive and `QueueCsvClient` providers.
Archive mode is explicit: no Archive provider, replay or live TAP. Replay and live
TAP cannot be configured together, and no provider falls back to the other mode.
Only selected sources receive providers. It explicitly sets `queue_common` for
QUEUE selection and `queue_continuum` / `queue_line` for the selected intents.
Legacy beam strategies and AQ-equivalent filters remain at their backend defaults.
Existing backend implications and preflight checks remain authoritative.

Validation and request download continue to call only the shared validator. Run
assessment validates current values, then calls the shared application entry.
The report's `input_sha256` stays null: a form has no original input-file bytes.
The separately retained request download is the wire mapping submitted by the
form; no fabricated original-file digest is inserted into report v4.

`ui/reports.py` builds one viewer artifact from exact report bytes and derives
inspection v3 once. `/runs/<id>` reuses the existing report template/pagination.
Existing `/reports` artifacts are not modified or mixed into the run store.
Execution COMPLETED does not imply duplication criteria passed. Source failures
can return a usable report and SOURCES_UNAVAILABLE. Unexpected construction or
serialization failures do not become scientific outcomes.

## Temporary local retention

Reports are process-local, with defaults of 20 runs and 32 MiB of total serialized
request/report/inspection bytes. Flask configuration `MAX_RETAINED_RUNS` and
`MAX_RETAINED_BYTES` control those bounds. Parsed-object overhead is additional;
this is not a strict resident-memory cap. An oversized single report is rejected
without evicting existing runs; otherwise oldest runs are evicted first.

A restart clears all runs. Unknown/evicted IDs return 404 with an explanation.
There are no disk writes or shared mutable "last report". There is no user-account
isolation: run IDs are references, not authorization. Use one local process bound
to 127.0.0.1; persistent/multi-user hosting is outside this increment. Refresh uses
GET after a 303 redirect and does not rerun. Repeated POSTs create separate runs;
job queues and duplicate-submission suppression are not implemented here.

## Verification scope

UI tests exercise actual offline shared-entry execution for LINE, CONTINUUM and
mixed requests; explicit Queue methods; invalid/unready no-execution paths;
source failure isolation; optional SPWs; exact report and inspection downloads;
run independence; retention; and no network access. The existing report-browser
suite also runs the pinned acceptance catalog.

### Offline UI/CLI parity gate

`tests/ui/test_cli_parity.py` checks the current form and offline execution
configuration through Flask's test client and the real CLI entry. Run it with:

```bash
python -m pytest tests/ui/test_cli_parity.py -q
```

The gate verifies the pinned catalog's input/source/reference checksums and
uses all 15 input cases to populate supported form fields. Each form submission
produces a retained report and request download; the CLI receives those exact
downloaded request bytes, the same source files and explicit formal Queue flags.
This compares the same wire request, including the form's sensitivity IDs.
Historical catalog options, including legacy beam settings, are not substituted
for the current UI configuration. Original catalog runs and their expected
scientific assertions remain independently checked by the report-browser suite.

Additional cases cover dual-source mixed intents, setup declaration without
SPWs, contradictory complete-list evidence, alternate supported units and 21
contexts across two pages with a display limit of one. Solar is tested through
the execution adapter, CLI and report viewer, with source access forbidden; it
is selectable for validation/export but cannot execute through the form. Network
calls are forbidden throughout the gate.

Full report dictionaries are compared, including method versions, reasons,
outcomes, source states, snapshot hashes, configuration and pair associations.
Only these execution-time fields are normalized:

- `generated_at`
- `search_started_at`
- `search_finished_at`
- `sources.QUEUE.source_metadata.snapshot.parsed_at`

Input provenance is checked separately: the CLI's `input_sha256` must match the
actual request-file bytes, and the form report's value must be null. Capture
dates and all other provenance remain in the comparison. Inspection v3
documents must match without normalization. Refresh, pagination and downloads
must preserve the original report/request/inspection bytes and must not execute
the assessment again. A comparator regression test protects against silently
excluding scientific or provenance differences.

This gate remains the offline UI/CLI parity check. Live Archive browser wiring
is covered separately by `tests/ui/test_live_source.py`: environment parsing,
replay/live mutual exclusion, lazy construction, no replay fallback, no implicit
live AQ lookup and shared-entry execution are tested with real network access
forbidden. Live service availability, browser JavaScript interaction and
independent real-proposal review remain separate verification.
