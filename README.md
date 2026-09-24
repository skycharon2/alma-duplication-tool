# ALMA Duplication Check Tool



A decision-support tool for discovering existing or planned ALMA observations
and explaining potential duplication. The intended workflow accepts a proposed
observation, retrieves Archive and Queue candidates, and evaluates applicable
conditions within a coherent context. Final scientific/policy decisions remain
with ALMA reviewers.

## Project status

Archive fixed-target, single-point continuum and LINE evaluation are implemented.
Queue ingestion/search and conditional mode diagnostics are implemented; complete
Queue continuum is available in the opt-in coherent single-field Queue row scope
([contract](docs/queue_continuum.md)); Queue LINE, wider arrays and the browser UI remain unfinished.
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

Default tests do not contact ALMA services. Full Queue acceptance requires an
explicit external file:

```bash
python -m pytest -q
```

Optional full Queue snapshot acceptance:

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
tracks the remaining interface and real-case review work after Archive line numerical evaluation.
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

Use a new output directory. The nine offline cases save report v4, comparison
results and gap summaries. A passing replay does not confer human scientific
review. See [case provenance and references](docs/acceptance_cases.md) and the
[thin-interface contract](docs/thin_interface_contract.md).
