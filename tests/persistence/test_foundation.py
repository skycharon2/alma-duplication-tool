"""SQLite fast checks plus opt-in PostgreSQL isolation in a disposable schema."""
import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.exc import IntegrityError
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alma_duplicate.persistence.db import database_engine, transaction
from alma_duplicate.persistence import models as m

ROOT = Path(__file__).parents[2]


def config(connection=None, output=None):
    cfg = Config(str(ROOT / 'alembic.ini'), output_buffer=output)
    cfg.set_main_option('script_location', str(ROOT / 'migrations'))
    if connection is not None:
        cfg.attributes['connection'] = connection
    return cfg


@pytest.fixture(params=['sqlite', 'postgresql'])
def connection(request):
    schema = None
    if request.param == 'postgresql':
        url = os.environ.get('ALMA_TEST_DATABASE_URL')
        if not url:
            pytest.skip('Set ALMA_TEST_DATABASE_URL for PostgreSQL integration tests')
        engine = database_engine(url)
    else:
        engine = create_engine('sqlite://')
    with engine.connect() as conn:
        if request.param == 'postgresql':
            schema = 'test_alma_' + uuid4().hex
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET search_path TO "{schema}"'))
        else:
            conn.execute(text('PRAGMA foreign_keys=ON'))
        conn.commit()
        try:
            command.upgrade(config(conn), 'head')
            conn.commit()
            yield conn
        finally:
            conn.rollback()
            if schema:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                conn.commit()
    engine.dispose()


def seed(conn):
    with transaction(conn) as session:
        session.execute(m.users.insert().values(id='u', issuer='issuer', subject='subject'))
        for w in ['a', 'b']:
            session.execute(m.workspaces.insert().values(id=w, owner_id='u', name=w))
        session.execute(m.submissions.insert().values(id='s', workspace_id='a', kind='MULTI',
                        settings={}, input_sha256='a'*64))
        session.execute(m.sources.insert().values(id='src', workspace_id='a', submission_id='s',
                        ordinal=0, name='target', ra_deg=1, dec_deg=2, original_input={}))


def test_migration_matches_metadata_and_can_upgrade_again(connection):
    assert compare_metadata(MigrationContext.configure(connection), m.metadata) == []
    connection.commit()
    command.downgrade(config(connection), 'base')
    connection.commit()
    command.upgrade(config(connection), 'head')
    connection.commit()
    assert compare_metadata(MigrationContext.configure(connection), m.metadata) == []


def test_workspace_constraints_and_transaction_rollback(connection):
    seed(connection)
    with pytest.raises(IntegrityError), transaction(connection) as session:
        session.execute(m.sources.insert().values(id='wrong', workspace_id='b', submission_id='s',
                        ordinal=1, name='wrong', ra_deg=1, dec_deg=2, original_input={}))
    with pytest.raises(RuntimeError), transaction(connection) as session:
        session.execute(m.workspaces.insert().values(id='rollback', owner_id='u', name='x'))
        raise RuntimeError('abort')
    assert connection.scalar(select(func.count()).select_from(m.workspaces)) == 2
    connection.commit()


def test_job_lease_and_artifact_scope_constraints(connection):
    seed(connection)
    with pytest.raises(IntegrityError), transaction(connection) as session:
        session.execute(m.jobs.insert().values(id='bad', workspace_id='a', submission_id='s',
                        source_id='src', purpose='LINE', state='RUNNING'))
    with transaction(connection) as session:
        session.execute(m.jobs.insert().values(id='job', workspace_id='a', submission_id='s',
                        source_id='src', purpose='LINE'))
        session.execute(m.runs.insert().values(id='run', workspace_id='a', job_id='job', attempt=1,
                        report_schema='v1', assessment_status='UNKNOWN', source_provenance={}))
    with pytest.raises(IntegrityError), transaction(connection) as session:
        session.execute(m.artifacts.insert().values(workspace_id='b', run_id='run', kind='report',
                        storage_key='key', sha256='a'*64, byte_size=1))
    with pytest.raises(IntegrityError), transaction(connection) as session:
        session.execute(m.artifacts.insert().values(workspace_id='a', run_id='run', kind='report',
                        storage_key='key', sha256='a'*64, byte_size=-1))


def test_postgresql_offline_ddl_and_explicit_driver():
    output = io.StringIO()
    command.upgrade(config(output=output), 'head', sql=True)
    sql = output.getvalue()
    assert 'JSONB' in sql and 'TIMESTAMP WITH TIME ZONE' in sql
    assert 'FOREIGN KEY(workspace_id, submission_id, source_id)' in sql
    with pytest.raises(ValueError):
        database_engine('sqlite://')


def test_source_submission_binding_and_attempt_uniqueness(connection):
    seed(connection)
    with transaction(connection) as session:
        session.execute(m.submissions.insert().values(id='other', workspace_id='a', kind='SINGLE',
                        settings={}, input_sha256='b'*64))
    # Same workspace is not sufficient: the source must belong to this submission.
    with pytest.raises(IntegrityError), transaction(connection) as session:
        session.execute(m.jobs.insert().values(id='wrong', workspace_id='a', submission_id='other',
                        source_id='src', purpose='LINE'))
    with transaction(connection) as session:
        session.execute(m.jobs.insert().values(id='j', workspace_id='a', submission_id='s',
                        source_id='src', purpose='LINE'))
        session.execute(m.runs.insert().values(id='r1', workspace_id='a', job_id='j', attempt=1,
                        report_schema='v1', assessment_status='UNKNOWN', source_provenance={}))
    with pytest.raises(IntegrityError), transaction(connection) as session:
        session.execute(m.runs.insert().values(id='r2', workspace_id='a', job_id='j', attempt=1,
                        report_schema='v1', assessment_status='UNKNOWN', source_provenance={}))
