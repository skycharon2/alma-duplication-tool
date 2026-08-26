# ALMA Duplication Check Tool

A browser-based decision-support tool for identifying existing or planned
ALMA observations that may satisfy the formal duplication criteria defined in
Appendix A of the ALMA User Policies.

The tool is intended to support candidate discovery and explainable
duplication assessment. It does not replace the final scientific or policy
decision made by ALMA reviewers.

## Project status

The Archive-structure exploration phase has been completed for the current
project scope. The project now contains tested Python components for parsing,
normalizing, and deterministically reconstructing ALMA Science Archive records.

Implemented components include:

- parsing of bracket and brace forms of `frequency_support`;
- parsing of `obs_id`, including identifier-truncation detection;
- normalization of Archive text, Boolean, timestamp, and identifier fields;
- internal surrogate identifiers for raw Archive rows;
- deterministic reconstruction of source--execution--SPW relationships;
- support for sparse source--SPW associations;
- explicit frequency-support mapping and ambiguity reporting;
- unit tests and automated testing with Python 3.11 and 3.12.

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
- candidate retrieval must remain separate from formal duplication assessment.

The current evidence and reconstruction model are documented in
[`docs/data_model.md`](docs/data_model.md) and
[`docs/archive_data_dictionary.md`](docs/archive_data_dictionary.md).

## Current development priorities

The next development phases are:

1. implement the production ALMA Archive query client;
2. migrate query-completeness and provenance checks from the notebooks;
3. investigate and implement the current-cycle queue adapter;
4. define the shared comparison-ready observation model;
5. implement broad candidate retrieval;
6. map and implement the Appendix A duplication criteria;
7. validate the workflow using confirmed duplicate and non-duplicate cases;
8. develop the browser-based interface.

The Archive client, current-cycle adapter, duplication-rule engine, and web
application are not yet complete.

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

```bash
python -m pytest -q
```

The current unit-test suite covers:

- `frequency_support` parsing;
- `obs_id` parsing and truncation handling;
- Archive metadata normalization;
- source--execution--SPW reconstruction;
- sparse and ambiguous associations;
- conflicting and incomplete records;
- reconstruction invariance under input-row reordering.

Tests that require live Archive services will be maintained separately from
deterministic local unit tests.

## Exploratory notebooks

The notebooks document the evidence used to design the production package:

- `01_archive_connection.ipynb`  
  TAP connectivity, query execution, metadata inspection, and spatial queries.

- `02_archive_data_relationships.ipynb`  
  Archive row granularity and Project, Member OUS, source, ASDM, and SPW
  relationships.

- `02b_archive_relationship_visualization.ipynb`  
  Interactive visualization of Archive relationships.

- `03_frequency_support_exploration.ipynb`  
  Structure and interpretation of the `frequency_support` field.

- `04_observation_modes.ipynb`  
  Observation-mode, resolution, sensitivity, mosaic, and related metadata.

- `04b_archive_robustness_closure.ipynb`  
  Archive-wide robustness checks, identifier risks, sparse associations,
  brace grammar, spatial-region families, and deterministic reconstruction.

Validated behaviour is migrated from the notebooks into `src/` and covered by
automated tests. The notebooks are evidence and development records; they are
not part of the production application pipeline.

## Project structure

```text
alma-duplication-tool/
├── notebooks/                  # Exploratory and reproducible investigations
├── src/alma_duplicate/
│   ├── clients/                # External data-access clients
│   ├── domain/                 # Internal data and result objects
│   ├── parsers/                # Structured Archive-field parsers
│   ├── normalization.py        # Archive metadata normalization
│   └── reconstruction.py       # Archive relationship reconstruction
├── tests/
│   ├── fixtures/               # Reproducible local test data
│   └── unit/                   # Deterministic unit tests
├── docs/
│   ├── archive_data_dictionary.md
│   └── data_model.md
├── pyproject.toml
└── README.md
```

The directory structure will evolve incrementally as the Archive client,
current-cycle adapter, application services, rule engine, and web interface
are implemented.

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

- [`docs/data_model.md`](docs/data_model.md): internal Archive reconstruction
  model and evidence.
- [`docs/archive_data_dictionary.md`](docs/archive_data_dictionary.md):
  field-level ownership, semantics, units, and known limitations.
- The project plan describes the target architecture and future development
  phases.

## License

See [`LICENSE`](LICENSE).