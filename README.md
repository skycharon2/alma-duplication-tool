# ALMA Duplication Check Tool

A decision-support tool for identifying possible duplication of ALMA
observations.

The tool will query the ALMA Science Archive and the current-cycle observing
queue, normalize the returned observations, and evaluate them according to
the duplication criteria defined in the ALMA Users' Policies.

## Current status

Initial development and exploration of programmatic access to the ALMA Science
Archive.

## Planned components

- ALMA Science Archive query client
- Current-cycle CSV query client
- Unified observation data model
- Duplication rule engine
- Browser-based user interface
- Automated testing and documentation

## Development environment

- Python 3.12
- Astropy
- Astroquery
- PyVO
- Pandas
- JupyterLab
- Pytest

## Project structure

- `notebooks/`: Archive exploration and validation notebooks
- `src/alma_duplicate/`: Reusable Python package
- `tests/`: Automated tests
- `docs/`: Technical and user documentation