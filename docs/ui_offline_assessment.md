# Offline browser assessment

The browser can execute its current form against configured local reference data:
form → shared validator → `assess_observation()` → independent report → exports.
Scientific formulas, method versions, source association and aggregation remain
owned by the existing backend. This increment does not connect live Archive access.

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
Neither form validation nor application startup reads assessment source files.

Run assessment appears when either reference path is configured. The browser
cannot supply file paths. Selecting an unconfigured source yields the backend's
NOT_PROVIDED state. Source files are read for each run, so their backend hashes
and provenance describe that run. A fresh replay client is created for each call.
No live Archive client or network fallback is constructed.

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

`ui/runs.py` supplies lazy `RecordedArchiveClient` and `QueueCsvClient` providers.
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
is not an available form mode. Network calls are forbidden throughout the gate.

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

This gate covers offline HTTP routes and rendering. Live Archive execution,
browser JavaScript interaction and independent real-proposal review require
their own verification.
