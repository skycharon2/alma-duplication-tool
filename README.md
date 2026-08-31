# ALMA Duplication Check Tool

A browser-based decision-support tool for identifying existing or planned
ALMA observations that may satisfy the formal duplication criteria defined in
Appendix A of the ALMA User Policies.

The tool is intended to support candidate discovery and explainable
duplication assessment. It does not replace the final scientific or policy
decision made by ALMA reviewers.

## Project status

The Archive-structure exploration phase and the first Archive production
client phase have been completed for the current project scope. The project
contains tested Python components for querying, parsing, normalizing, and
deterministically reconstructing ALMA Science Archive records.

Implemented components include:

- construction of matched COUNT and retrieval ADQL queries;
- explicit TAP MAXREC and `QUERY_STATUS` handling;
- `COMPLETE`, `OVERFLOW`, `COUNT_MISMATCH`, and `ERROR` query outcomes;
- valid-empty-result and versioned schema-drift validation;
- immutable query provenance and source-neutral TAP responses;
- an offline fake TAP executor and pipeline ECSV fixture;
- parsing of bracket and brace forms of `frequency_support`;
- parsing of `obs_id`, including identifier-truncation detection;
- normalization of Archive text, Boolean, timestamp, and identifier fields;
- internal surrogate identifiers for raw Archive rows;
- deterministic reconstruction of source--execution--SPW relationships;
- support for sparse source--SPW associations;
- explicit frequency-support mapping and ambiguity reporting; and
- automated testing with Python 3.11 and 3.12.

The current implementation is a backend foundation rather than a complete
duplication-checking application.

## Main findings from Archive exploration

The exploratory notebooks established the following design requirements:

- a flattened Archive row must not be treated as a complete observation;
- Archive identifiers must be preserved, but cannot be assumed to be unique
  internal row keys;
- source--SPW relationships must be reconstructed from observed records and
  must not be generated as a Cartesian product;
- raw, parsed, normalized, and derived values must remain distinguishable;
- missing, conflicting, truncated, or ambiguous metadata must be reported
  explicitly;
- incomplete TAP responses cannot support a negative candidate conclusion;
- candidate retrieval must remain separate from formal duplication assessment.

The current evidence and reconstruction model are documented in
[`docs/data_model.md`](docs/data_model.md) and
[`docs/archive_data_dictionary.md`](docs/archive_data_dictionary.md).

## Current development priorities

The next development phases are:

1. investigate and implement the current-cycle queue adapter;
2. define the shared comparison-ready observation model;
3. implement broad candidate retrieval across Archive and queue sources;
4. map and implement the Appendix A duplication criteria;
5. validate the workflow using confirmed duplicate and non-duplicate cases;
6. develop the browser-based interface.

The current-cycle adapter, duplication-rule engine, known-case assessment
workflow, and web application are not yet complete.

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

## Running the tests

Run the complete offline suite:

```bash
python -m pytest -q
```

The test suite covers:

- Archive query parameter and ADQL construction;
- PyVO-to-source-neutral TAP response adaptation;
- COUNT/retrieval reconciliation and query provenance;
- overflow, count mismatch, valid empty, schema drift, and error states;
- offline normalization--parsing--reconstruction integration;
- `frequency_support` parsing;
- `obs_id` parsing and truncation handling;
- Archive metadata normalization;
- source--execution--SPW reconstruction;
- sparse and ambiguous associations;
- conflicting and incomplete records; and
- reconstruction invariance under input-row reordering.

Ordinary tests do not contact the live ALMA TAP service. Tests requiring live
Archive services will be maintained separately and invoked explicitly.

## Exploratory notebooks

The notebooks document the evidence used to design the production package:

- `01_archive_connection.ipynb`: TAP connectivity, metadata, and spatial queries.
- `02_archive_data_relationships.ipynb`: Archive row granularity and hierarchy.
- `02b_archive_relationship_visualization.ipynb`: relationship visualization.
- `03_frequency_support_exploration.ipynb`: frequency-support structure.
- `04_observation_modes.ipynb`: observation-mode-related metadata.
- `04b_archive_robustness_closure.ipynb`: robustness and closure validation.

Validated behaviour is migrated from notebooks into `src/` and covered by
automated tests. Notebooks are evidence records, not the production pipeline.

## Project structure

```text
alma-duplication-tool/
├── notebooks/
├── src/alma_duplicate/
│   ├── clients/
│   │   ├── archive_contract.py
│   │   ├── archive_queries.py
│   │   ├── archive_client.py
│   │   └── archive_adapter.py
│   ├── domain/
│   ├── parsers/
│   ├── normalization.py
│   └── reconstruction.py
├── tests/
│   ├── fakes/
│   ├── fixtures/archive/
│   ├── integration/
│   └── unit/
├── docs/
│   ├── archive_client_contract.md
│   ├── archive_data_dictionary.md
│   └── data_model.md
├── pyproject.toml
└── README.md
```

## Design principles

- Preserve raw data and provenance.
- Use internal surrogate identifiers.
- Represent observational relationships explicitly.
- Keep source-specific ingestion separate from the shared domain model.
- Keep reconstruction separate from policy evaluation.
- Distinguish candidate relevance from confirmed duplication.
- Never interpret incomplete searches or missing metadata as scientific
  conclusions.
- Keep scientific and policy rules independently testable and explainable.

## Documentation

- [`docs/archive_client_contract.md`](docs/archive_client_contract.md): TAP
  completeness, schema, provenance, and pipeline-gating contract.
- [`docs/data_model.md`](docs/data_model.md): internal Archive reconstruction
  model and evidence.
- [`docs/archive_data_dictionary.md`](docs/archive_data_dictionary.md):
  field-level ownership, semantics, units, and known limitations.

## License

See [`LICENSE`](LICENSE).
