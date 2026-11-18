# Persistence foundation — Phase 2, step 03

This is an opt-in schema and transaction foundation. The Web application still
uses its existing temporary RunStore and BatchStore; installing these dependencies
does not change request execution, report URLs, scientific results or retention.
No database connection or schema mutation occurs on module import.

## Install and review

From a source checkout, in the project environment:

```sh
python -m pip install -e '.[persistence]'
python -m alembic upgrade head --sql > /tmp/alma-schema.sql
```

Online migrations require `ALMA_DATABASE_URL` with the explicit
`postgresql+psycopg://` driver, supplied through the deployment's secret
configuration. Do not commit credentials. There is no SQLite production fallback,
implicit database creation, or startup migration. After configuring a dedicated
database, the explicit migration command is `python -m alembic upgrade head`.
Review migrations and back up existing data before deployment. Downgrading the
initial revision removes these tables and their data; it is for disposable-test
rollback, not recovery of published reports.

## Schema boundary

- `users`: OIDC issuer plus subject identity, not email or a password store.
- `workspaces`: initial personal workspace ownership; membership/authentication
  workflows are deferred. A user may own multiple workspaces.
- `submissions`: Single/Multi/Mosaic identity, shared settings, input digest and
  optional paired immutable Queue snapshot key/digest.
- `sources`: ordered input rows, original input provenance, ICRS coordinates and
  optional redshift; duplicate names and coordinates remain independent rows.
- `jobs`: one scientific purpose per source, execution state, attempt counter and
  lease fields. Running jobs require a lease, heartbeat and positive attempt.
- `runs`: a job attempt's report identity, schema and scientific status, plus
  source provenance (including actual Archive acquisition evidence when supplied).
- `artifacts`: external storage key, digest, size and kind. Full report JSON and
  inspection files belong in artifact storage, not database JSON columns.

Workspace-scoped composite foreign keys connect Submission → Source → Job → Run
→ Artifact. They reject cross-workspace parent links; they do not authorize reads
or writes. The next repository layer must require workspace scope on every
operation. Foreign keys deliberately do not cascade deletion of research records.
Stable string identifiers accommodate existing run IDs, but no legacy IDs or
reports are migrated in this step.

JSON metadata uses PostgreSQL JSONB; timestamps use timezone-aware database types.
The source input digest and artifact digest currently have length constraints;
the future repository must validate hexadecimal encoding, canonical keys and
bounded input payloads. This schema does not yet enforce immutable updates,
lease claiming, heartbeat renewal, retry fencing or atomic artifact publication.
Those operations belong to later repository, artifact and worker increments.
Do not expose this foundation as a multi-user service by itself.

## Verification

```sh
python -m pytest -q tests/persistence
```

Without `ALMA_TEST_DATABASE_URL`, PostgreSQL integration variants skip explicitly.
SQLite tests enable foreign keys, exercise actual Alembic upgrades/downgrades,
check metadata drift, transaction rollback and integrity failures. Offline SQL
checks cover PostgreSQL JSONB, timezone timestamps and composite foreign keys.
These checks do not substitute for PostgreSQL execution.

Set `ALMA_TEST_DATABASE_URL` to a **test** PostgreSQL database using the explicit
psycopg URL to run both variants. The test role must be able to create schemas.
Each test creates a random `test_alma_...` schema, migrates it, and drops only that
schema in cleanup. No existing application schema is targeted. The dedicated
CI workflow supplies a disposable PostgreSQL service for these tests.

The migration contains frozen table definitions, not imports of current model
metadata. Future changes require a new reviewed migration. Reference APIs:
[SQLAlchemy composite constraints](https://docs.sqlalchemy.org/en/20/core/constraints.html)
and [Alembic migration environments](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
