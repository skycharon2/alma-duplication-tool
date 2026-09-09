# ALMA Duplication Check Tool

A decision-support tool for discovering existing or planned ALMA observations
and explaining potential duplication. The intended workflow accepts a proposed
observation, retrieves Archive and Queue candidates, and evaluates applicable
conditions within a coherent context. Final scientific/policy decisions remain
with ALMA reviewers.

## Project status

| Capability | Status |
| --- | --- |
| Archive query, validation and reconstruction | Implemented |
| Queue parsing and reconstruction | Implemented |
| Local Queue source storage and independent parse summaries | Implemented |
| Offline proposed-observation validation | Implemented |
| Comparison-context construction from existing ingestion outputs | Implemented (offline, row-scoped; no matching) |
| Offline search plans and limited spatial evidence adaptation | Implemented; conditional geometry support |
| Request-driven candidate search across Archive and Queue | Planned |
| Formal duplication assessment | Planned |
| Browser interface | Planned |

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
The [next-delivery checklist](docs/README.md#next-delivery) coordinates service
integration using the existing request, comparison and search/spatial objects.
Reported CASE candidates are not confirmed duplicate/non-duplicate labels.

## License

No project license has been selected yet.
