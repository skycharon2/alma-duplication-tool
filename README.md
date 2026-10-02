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

## Installation

Use Python 3.11 or later. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

For the browser interface, also install the optional UI dependencies:

```bash
python -m pip install -e ".[ui]"
python -m flask --app alma_duplicate.ui.app:create_app run
```

Open the local URL printed by Flask. The home route opens the [proposed form](docs/ui_proposed_form.md)
at `/proposed`, which validates inputs and exports request JSON. Configure the
[browser assessment flow](docs/ui_offline_assessment.md) with Archive replay,
live Archive TAP and/or a Queue CSV and view each run's own report. Set
`ALMA_UI_LIVE_ARCHIVE=1` to opt into live TAP access; live TAP and Archive replay
are mutually exclusive, and live TAP never implies a live AQ lookup.
The read-only [report browser](docs/ui_report_browser.md) displays backend reports
and exports their original JSON plus inspection v3. To enable it, generate an
acceptance run and set `ALMA_UI_REPORT_DIR` to its output directory before starting
Flask; browse `/reports`. No new assessment is performed by this viewer.

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
in [rules](docs/rules.md). The [next-delivery checklist](docs/README.md#next-delivery)
tracks the completed dual-source engineering acceptance, the externally blocked
real-proposal review gate and the remaining interface work.
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
