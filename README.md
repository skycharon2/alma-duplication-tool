# ALMA Duplication Check Tool



A decision-support tool for discovering existing or planned ALMA observations
and explaining potential duplication. The intended workflow accepts a proposed
observation, retrieves Archive and Queue candidates, and evaluates applicable
conditions within a coherent context. Final scientific/policy decisions remain
with ALMA reviewers.

## Project status

Archive fixed-target, single-point continuum and LINE evaluation are implemented.
Queue ingestion/search and conditional mode diagnostics are implemented. Queue
continuum and Queue LINE evaluation are available in the supported coherent
single-field Queue scope ([continuum contract](docs/queue_continuum.md),
[LINE contract](docs/queue_line_pairing.md)). Same-request Archive+Queue
engineering acceptance, cross-source/SPW isolation and source-state completeness
coverage are delivered. A genuine proposal has not been supplied for independent
real-proposal review; broader array/mode coverage and persistent multi-user
browser operation remain unfinished.
See the [capability matrix](docs/status.md), [documentation guide](docs/README.md)
and [engineering roadmap](docs/roadmap.md).

Existing ingestion adapters retain evidence and source associations. Reconstruction
does not establish comparability. Request-side READY indicates spatial search
prerequisites, not successful retrieval or a duplication verdict. See the
[mapping boundary](docs/data_model.md#spectral-mapping-boundary) for current
whole-result spectral validation and future per-quantity usability.

## Run locally from GitHub

For a local browser test, follow the steps below. **You do not need a copy of
this project's local `data` folder:** the Queue downloader can acquire the
official CSV on your computer. Operational CSV snapshots are not committed to
Git. The small CSV fixtures included in the repository are synthetic or reduced
engineering datasets, not the full current Queue.

These commands use **macOS or Linux**, Python 3.11+, and a terminal opened in the
project folder (for example, VS Code's integrated terminal). On Windows, use
WSL with a Linux Python environment for this workflow: managed Queue commands
use POSIX file locking and are not native PowerShell commands.
Internet access is needed to install dependencies, download Queue data and query
live Archive services.

### Linux prerequisites (Ubuntu/Debian)

On Ubuntu or Debian, install the basic tools before cloning. Other Linux
systems should use their distribution's package manager for equivalent tools.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ca-certificates curl
python3 --version
```

The Python interpreter used below **must be 3.11 or newer**. On systems with an
older default Python, install a supported interpreter and its matching `venv`
package, then use that interpreter (for example, `python3.11 -m venv .venv`).
Do not replace the Linux system Python just to run this project.

### 1. Download and install

Clone the repository, or use GitHub's **Code → Download ZIP**, extract it and
open the extracted project folder. If cloning:

```bash
git clone https://github.com/skycharon2/alma-duplication-tool.git
cd alma-duplication-tool
```

Cloning checks out GitHub's default `main` branch. Changes on an unpublished
local branch are not included; push the intended branch before checking it out
on the Linux machine if you need those changes.

From the project root (the folder containing `pyproject.toml`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[ui]"
python -m pip check
```

Confirm that `python3` is version 3.11 or later before creating the environment.
For development or notebooks, additionally install `.[dev]`; it is not required
to launch the browser interface.

**Archive-only quick start:** after installing, you can test live Archive
queries without downloading or activating Queue CSV data:

```bash
unset ALMA_UI_QUEUE_CSV ALMA_UI_QUEUE_SNAPSHOT_ROOT
unset ALMA_UI_ARCHIVE_REPLAY ALMA_UI_ARCHIVE_ARRAY_EVIDENCE ALMA_UI_REPORT_DIR
export ALMA_UI_LIVE_ARCHIVE=1
export ALMA_UI_LIVE_ARCHIVE_AQ=1
python -m flask --app alma_duplicate.ui.app:create_app run \
  --host 127.0.0.1 --port 5051
```

Open `http://127.0.0.1:5051/proposed` and select ARCHIVE only. Press Ctrl+C
to stop this server before proceeding to the combined Archive + Queue setup.

### 2. Download and activate the initial Queue snapshot

Skip this step for Archive-only testing. To test real Queue observations, run:

```bash
python -m alma_duplicate.cli.queue_update --once \
  --store-root data/cache/queue-snapshots
```

The command creates local storage, downloads the official CSV and validates it.
A successful check reports `NEW_VALIDATED` or `UNCHANGED`, with `source_id` and
`run_id` in its JSON output. Downloading does **not** activate the snapshot.
If download or validation fails, resolve the reported error before continuing.

Review the source date, checksum and parser warnings in the output and linked
source/run manifests. Replace both placeholders below with the actual IDs from
the successful check, then explicitly select that snapshot for assessments:

```bash
python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots activate \
  --source-id SOURCE_ID_FROM_OUTPUT \
  --run-id RUN_ID_FROM_OUTPUT \
  --reason "Reviewed initial official Queue snapshot for local testing"

python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots status
```

Verify that the status identifies the active snapshot before testing Queue.
Keep the whole snapshot store: the active selection refers to both original CSV
bytes and parse-run evidence. See [snapshot activation](docs/queue_active_snapshot.md).

### 3. Start the webpage with Archive and Queue

In the same terminal, with the environment still activated:

```bash
unset ALMA_UI_QUEUE_CSV ALMA_UI_ARCHIVE_REPLAY ALMA_UI_ARCHIVE_ARRAY_EVIDENCE
unset ALMA_UI_REPORT_DIR
export ALMA_UI_QUEUE_SNAPSHOT_ROOT="$PWD/data/cache/queue-snapshots"
export ALMA_UI_LIVE_ARCHIVE=1
export ALMA_UI_LIVE_ARCHIVE_AQ=1

python -m flask --app alma_duplicate.ui.app:create_app run \
  --host 127.0.0.1 --port 5051
```

Open **http://127.0.0.1:5051/proposed** on the same computer. Keep the terminal
running; press **Ctrl+C** to stop the server. If the port is already occupied,
choose another port and use the matching URL.

- **Archive + Queue:** use the configuration above and select the desired sources
  on the form. Archive TAP and AQ retrieve data online; Queue reads the active
  local snapshot. Check Queue's data-source details in the form.
- **Archive only:** omit the Queue export above, or run
  `unset ALMA_UI_QUEUE_SNAPSHOT_ROOT ALMA_UI_QUEUE_CSV` before starting. Select
  ARCHIVE only. No local CSV is needed.
- **Queue only:** after activating a snapshot, unset
  `ALMA_UI_LIVE_ARCHIVE ALMA_UI_LIVE_ARCHIVE_AQ` before starting and select QUEUE only.
- **Form validation only:** with no assessment sources configured, the form can
  validate and export inputs; it cannot run a source assessment.

Live TAP alone does not enable live AQ: both flags above are intentional.
Missing or invalid Queue data is reported as unavailable/failed, not as proof of
no duplication. Opening the webpage or running an assessment never downloads or
updates Queue data.

Reports generated by this browser session are accessible through **Existing
reports** at `/reports`. They are temporary and may expire or disappear on server
restart; download important reports. `ALMA_UI_REPORT_DIR` is an optional, separate
setting for preloaded read-only reports, not a requirement for new assessments.
See [browser source configuration](docs/ui_offline_assessment.md),
[managed Queue configuration](docs/queue_managed_ui.md) and
[report browsing](docs/ui_report_browser.md).

### Updating Queue data later

Run the same `queue_update --once` command to check the official source again.
Changed valid data is saved as a new candidate; it does not overwrite the active
snapshot. Review it and run `queue_active activate` with its actual IDs to use it
in subsequent assessments. Existing reports retain their original data identity.
A successful download today does not mean the CSV's scientific data date is today.

**Scheduled checking requires separate setup.** Cloning the repository or
starting Flask does not install a background updater. The repository provides
[Linux systemd timer/service examples](docs/queue_operations_deployment.md).
They automate acquisition and validation, but adopting a new snapshot still
requires explicit activation. They do not run automatically on macOS or Windows.
For a short local test, a manual update check is sufficient.

This launch command is for local testing. Institutional hosting needs a separate
service, access-control and persistence setup; see the
[deployment guide](docs/queue_operations_deployment.md).

### Access a remote Linux host from your laptop

If Flask is running on a remote Linux computer, keep its `--host 127.0.0.1`
setting. From a separate terminal on your own laptop, establish an SSH tunnel
(replace the placeholders with your actual SSH login and host):

```bash
ssh -N -L 5051:127.0.0.1:5051 USERNAME@LINUX_HOST
```

Keep the tunnel open and visit `http://127.0.0.1:5051/proposed` **on your laptop**.
The address `127.0.0.1` otherwise refers to whichever machine runs the browser.
SSH access must already be authorized and configured. If local port 5051 is in
use, choose another local port in `-L` and in the laptop browser URL. Do not
use `--host 0.0.0.0` to expose the Flask development server to the network.

### Basic checks and troubleshooting

In another terminal on the Linux host, check that Flask responds:

```bash
curl -fsS http://127.0.0.1:5051/healthz
```

This confirms the HTTP process is reachable, **not** that Archive queries or
Queue downloads work. If setup fails, check these common causes:

- `python3 -m venv` fails: install the `venv` package matching your Python version.
- `No module named flask`: activate `.venv` and reinstall `.[ui]`.
- Port 5051 is occupied: choose another port and update the browser/tunnel URL.
- Queue unavailable: check `queue_active ... status`; downloading alone does
  not activate a snapshot. Preserve the full snapshot store.
- Archive unavailable: verify outbound HTTPS/DNS and review application logs;
  source failure is not a non-duplication result.
- Old browser reports missing: temporary run history may expire or disappear
  after restarting the process; download reports you need to retain.

For automated Linux services, refer to the [deployment guide](docs/queue_operations_deployment.md)
instead of exposing this development server.

## Minimal example

Validate the committed partial observation request without network access:

```bash
python examples/validate_proposed_observation.py
```

Exercise Queue ingestion with the committed fixture:

```python
from pathlib import Path
from alma_duplicate.clients import QueueCsvClient, run_queue_pipeline

result = QueueCsvClient().load(
    Path("tests/fixtures/queue/queue_pipeline_v1.csv")
)
print(result.status.value)
batch = run_queue_pipeline(result)
print(len(batch.reconstruction.associations))
```

Run this from the repository root. This fixture is an engineering test dataset;
it is not the full current queue. The [Queue contract](docs/queue_csv_contract.md)
describes source requirements and the [storage guide](docs/queue_snapshot_store.md)
distinguishes reading a historical source from reparsing it.

## Tests

Default tests, including the UI tests, do not contact ALMA services. In a clean
environment, install the runtime, test and optional UI dependencies before
running the full suite:

```bash
python -m pip install -e ".[test,ui]"
python -m pip check
python -m pytest -q
```

The Python tests CI workflow installs `.[test,ui]` so it also exercises the
browser interface. The separate Live Archive smoke workflow runs only the
Archive smoke tests and uses `.[test]`. Notebook and plotting tools remain in
`.[dev]`; UI dependencies remain optional for backend-only use. Dependency
versions are not locked; a 60-second CI pip timeout mitigates network stalls,
not incompatibilities.

Optional full Queue snapshot acceptance requires an explicit external file:

```bash
ALMA_QUEUE_CSV_SNAPSHOT="$PWD/data/raw/projects_in_queue_cycle13_20260901.csv" \
python -m pytest -q tests/acceptance/test_queue_csv_snapshot.py
```

Optional live Archive smoke tests:

```bash
python -m pytest -q -s --run-live tests/live/test_archive_tap_smoke.py
```

The [fixture notes](tests/fixtures/queue/README.md) describe offline data.
Pinned snapshot assertions live in the
[acceptance test](tests/acceptance/test_queue_csv_snapshot.py).
A test count should be reported with its tested commit and environment, not
treated as a permanent capability claim.

## Documentation

Start with the [documentation guide](docs/README.md) for candidate-search and
formal-rule reading paths, document responsibilities and status meanings.
The [current data model](docs/data_model.md) describes implemented objects and
invariants. Original [conceptual ERDs](docs/design/conceptual_data_model.md) and
[historical snapshots](docs/evidence/exploration_snapshots.md) have separate homes.

Production code is in [src/alma_duplicate](src/alma_duplicate/), with automated
checks in [tests](tests/). [Notebooks](notebooks/) retain dated exploration
evidence; their outputs do not establish current production capabilities.
The [candidate-search service](docs/candidate_search.md) connects existing request,
comparison and search/spatial objects; per-context rule evaluation is documented
in [rules](docs/rules.md). The [delivery status and remaining work](docs/README.md#delivery-status-and-remaining-work)
tracks the completed engineering increments, the externally blocked
real-proposal review gate and the remaining lifecycle/broader-mode work.
Archive continuum and line branch aggregation and input/CLI closure are implemented;
search-wide absence conclusions are intentionally not provided. Existing CASE
retrieval evidence remains retrieval evidence:
reported CASE candidates are not confirmed duplicate/non-duplicate labels.

## License

No project license has been selected yet.

## Offline candidate-beam replay

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/single_point/request.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --queue-candidate-beam --output reports/candidate-beam.json
```

The source-documented Queue profile derives the beam from the candidate's
frequency and supported array evidence. It needs no hand-written sidecar.
The original `examples/proposed_observation.json` remains the incomplete-input
example. Read the [profile contract](docs/queue_candidate_beam.md) and
[verified official sources](docs/evidence/official_sources.md) for scientific
scope, source-version corrections and unresolved cases. This is a provisional
Queue-only replay, not a completed duplication verdict.

## Reproducible acceptance before the interface

```bash
python -m alma_duplicate.cli.acceptance \
  --catalog examples/acceptance/catalog.json \
  --output-dir reports/acceptance-run-1
```

Use a new output directory. The fifteen offline cases save report v4,
comparison results and gap summaries. A passing replay does not confer human
scientific review; the catalog currently contains zero reviewed real-proposal
cases. See [case provenance and references](docs/acceptance_cases.md) and the
[thin-interface contract](docs/thin_interface_contract.md).
