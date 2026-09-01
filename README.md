# ALMA Duplication Check Tool

A decision-support tool for finding existing or planned ALMA observations that
may meet the duplication criteria in Appendix A of the ALMA User Policies.

The project is intended to support candidate discovery and explainable
assessment. It does not replace the final scientific or policy decision made
by ALMA reviewers.

## Project status

Production ingestion and deterministic reconstruction are implemented for two
data sources:

- the public ALMA Science Archive `ivoa.obscore` TAP view; and
- the current-cycle duplication-check Queue CSV.

Both pipelines preserve raw evidence, source metadata, units, provenance, and
the relationships that were actually present in the source. They report
incomplete, conflicting, or unsupported evidence instead of silently filling
gaps.

The next phase is the shared Archive--Queue comparison model. Formal
duplication rules, known-case assessment, automated Queue snapshot retrieval,
and the browser interface are not yet implemented.

### Archive pipeline

The Archive implementation includes:

- matched COUNT and retrieval ADQL queries;
- TAP `MAXREC` and `QUERY_STATUS` handling;
- `COMPLETE`, `OVERFLOW`, `COUNT_MISMATCH`, and `ERROR` outcomes;
- valid-empty-result and schema-drift validation;
- query provenance and per-field TAP metadata;
- runtime unit validation for the six Archive fields used by later
  comparison;
- typed frequency-coverage, resolution, and sensitivity evidence with
  missing/invalid statuses;
- optional broad frequency and angular-resolution candidate prefilters;
- parsing of bracket and brace forms of `frequency_support`;
- parsing of `obs_id`, including identifier-truncation detection;
- normalization of text, Boolean, timestamp, and identifier fields;
- surrogate identifiers for flattened Archive rows;
- deterministic source--execution--SPW reconstruction;
- sparse source--SPW associations and ambiguity reporting;
- an offline ECSV integration fixture; and
- an opt-in live TAP smoke test that continues through reconstruction.

### Queue CSV pipeline

The Queue implementation includes:

- a versioned 79-column ingestion contract;
- fingerprinting of the exact source bytes with SHA-256 and byte length, plus
  capture time, embedded dictionary, secondary header, and physical row
  identity;
- explicit field aliases, units, datatypes, and schema-drift checks;
- 16 same-number SPW triples, without Cartesian reconstruction;
- separate regular-SPW and spectral-scan (SPS) representations;
- frequency and velocity normalization with conversion provenance;
- requested-sensitivity evidence without relabelling it as achieved Archive
  sensitivity;
- spatial, mosaic, rectangle, request, array, and polarization evidence;
- reference-frequency coverage validation;
- preservation of exact duplicate rows as distinct source associations;
- factorization into spatial, spectral, and request components while retaining
  every observed row association;
- a small offline CSV integration fixture; and
- an opt-in acceptance test for the complete current-cycle snapshot.

The known SPS bandwidth unit conflict is retained as a structured warning. A
complete parse with that warning is valid for reconstruction; the conflicting
source declarations remain available for later review.

## Current development priorities

1. Confirm the Archive sky-frequency reference frame and the approved
   Archive--Queue frame mapping.
2. Agree how Queue requested sensitivity maps to Archive continuum and
   nominal 10-km/s estimates, including any spectral smoothing.
3. Confirm the official SPS bandwidth unit for the conflicting Queue export.
4. Define and implement the shared comparison-ready evidence model.
5. Validate the shared representation with confirmed duplicate and
   non-duplicate cases.
6. Map the Appendix A criteria into versioned, independently testable rules.
7. Add a controlled Queue snapshot download and update workflow.
8. Build the browser interface around the tested backend.

The ingestion pipelines deliberately do not decide whether two observations
are duplicates. Correlator mode, reference-frame alignment, mosaic overlap,
sensitivity comparison, spectral smoothing, and policy thresholds belong to
the comparison or rule layer.

## Development environment

- Python 3.11 or later
- Astropy
- Astroquery
- PyVO
- Pandas
- JupyterLab
- Pytest

## Installation

Clone the repository and create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Queue CSV usage

`QueueCsvClient` reads an exact local snapshot. `run_queue_pipeline` admits
only a complete parse and then reconstructs the relationships observed in the
CSV.

```python
from pathlib import Path

from alma_duplicate.clients import QueueCsvClient, run_queue_pipeline

snapshot_path = Path(
    "data/raw/projects_in_queue_cycle13_20260901.csv"
)

parse_result = QueueCsvClient().load(snapshot_path)
print(parse_result.status.value)
print(len(parse_result.raw_rows))
print(len(parse_result.row_inputs))

batch = run_queue_pipeline(parse_result)
print(len(batch.reconstruction.associations))
print(batch.reconstruction.sparse_group_count)
```

The full current-cycle CSV is kept outside version control. The committed
fixture in `tests/fixtures/queue/` exercises the same pipeline offline.

## Running the tests

Run the complete offline suite:

```bash
python -m pytest -q
```

The ordinary suite covers Archive and Queue contracts, clients, parsers,
normalization, reconstruction, malformed input, schema drift, sparse
relationships, exact duplicates, and input-order invariance. It does not
contact ALMA services or require the full Queue snapshot.

Run the live Archive smoke test explicitly:

```bash
python -m pytest -q -s \
  --run-live \
  tests/live/test_archive_tap_smoke.py
```

Run the full Queue snapshot acceptance test explicitly:

```bash
ALMA_QUEUE_CSV_SNAPSHOT="$PWD/data/raw/projects_in_queue_cycle13_20260901.csv" \
python -m pytest -q \
  tests/acceptance/test_queue_csv_snapshot.py
```

The pinned Cycle 13 snapshot contains 3,200 source rows and reconstructs 3,200
observed associations. The acceptance test also verifies the 79-column schema,
16,216 regular SPWs, one SPS record, 419 factorization groups, two sparse
groups, and the expected source checksum.

## Exploratory notebooks

The notebooks record the evidence used to design the production package:

- `01_archive_connection.ipynb`: TAP connectivity, metadata, and spatial
  queries.
- `02_archive_data_relationships.ipynb`: Archive row granularity and
  hierarchy.
- `02b_archive_relationship_visualization.ipynb`: relationship visualization.
- `03_frequency_support_exploration.ipynb`: frequency-support structure.
- `04_observation_modes.ipynb`: observation-mode-related metadata.
- `04b_archive_robustness_closure.ipynb`: parser and reconstruction robustness.
- `04c_archive_semantic_closure.ipynb`: live pipeline and Archive semantic
  closure.
- `05_queue_csv_exploration.ipynb`: Queue file layout, schema, units,
  cardinality, and reconstruction evidence.

Validated behaviour is migrated from notebooks into `src/` and covered by
automated tests. Notebooks are evidence records, not the production pipeline.

## Project structure

```text
alma-duplication-tool/
├── notebooks/
│   ├── 01_archive_connection.ipynb
│   ├── 02_archive_data_relationships.ipynb
│   ├── 02b_archive_relationship_visualization.ipynb
│   ├── 03_frequency_support_exploration.ipynb
│   ├── 04_observation_modes.ipynb
│   ├── 04b_archive_robustness_closure.ipynb
│   ├── 04c_archive_semantic_closure.ipynb
│   └── 05_queue_csv_exploration.ipynb
├── src/alma_duplicate/
│   ├── clients/
│   │   ├── archive_client.py
│   │   ├── archive_contract.py
│   │   ├── archive_field_contract.py
│   │   ├── archive_queries.py
│   │   ├── archive_adapter.py
│   │   ├── queue_csv_client.py
│   │   ├── queue_csv_contract.py
│   │   └── queue_csv_adapter.py
│   ├── domain/
│   │   ├── archive.py
│   │   ├── archive_evidence.py
│   │   ├── queue.py
│   │   ├── reconstruction.py
│   │   └── spectral.py
│   ├── parsers/
│   │   ├── frequency_support.py
│   │   ├── obs_id.py
│   │   └── queue_csv.py
│   ├── normalization.py
│   ├── queue_csv_contract.py
│   ├── queue_normalization.py
│   ├── reconstruction.py
│   └── queue_reconstruction.py
├── tests/
│   ├── acceptance/
│   ├── fakes/
│   ├── fixtures/
│   │   ├── archive/
│   │   └── queue/
│   ├── integration/
│   ├── live/
│   └── unit/
├── docs/
│   ├── archive_client_contract.md
│   ├── archive_data_dictionary.md
│   ├── data_model.md
│   ├── live_archive_smoke.md
│   └── queue_csv_contract.md
├── pyproject.toml
└── README.md
```

## Design principles

- Preserve raw data, units, and provenance.
- Use internal surrogate identifiers where source identifiers are not unique.
- Reconstruct only relationships observed in the source.
- Keep source-specific ingestion separate from the shared comparison model.
- Keep reconstruction separate from policy evaluation.
- Distinguish candidate relevance from confirmed duplication.
- Report missing, conflicting, or incomplete evidence explicitly.
- Keep scientific and policy rules versioned, explainable, and independently
  testable.

## Documentation

- [`docs/archive_client_contract.md`](docs/archive_client_contract.md): Archive
  query completeness, schema, provenance, and pipeline gating.
- [`docs/archive_data_dictionary.md`](docs/archive_data_dictionary.md): Archive
  field ownership, semantics, units, and limitations.
- [`docs/data_model.md`](docs/data_model.md): Archive and Queue reconstruction
  entities and relationships.
- [`docs/live_archive_smoke.md`](docs/live_archive_smoke.md): opt-in live TAP
  validation.
- [`docs/queue_csv_contract.md`](docs/queue_csv_contract.md): Queue layout,
  schema, units, parsing, and reconstruction contract.

## License

See [`LICENSE`](LICENSE).
