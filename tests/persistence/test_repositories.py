"""Repository contracts run on SQLite and opt-in PostgreSQL fixtures."""
from datetime import datetime, timedelta, timezone

import pytest
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from alma_duplicate.persistence import models as m
from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.repositories import WorkspaceRepository, RecordUnavailable, StaleAttempt
from tests.persistence.test_foundation import connection as connection_fixture, seed

connection = connection_fixture


def source():
    return dict(name='same name', ra_deg=12, dec_deg=-30, redshift=None,
                original_input={'ra': '12', 'dec': '-30'})


def create(repo, **kwargs):
    return repo.create_submission(**(dict(kind='MULTI', settings={'frequency_reference': 'REST'},
        input_sha256='a'*64, sources=[source(), source()], purposes=['LINE', 'CONTINUUM']) | kwargs))


def test_order_duplicates_scoping_and_detached_metadata(connection):
    seed(connection)
    with transaction(connection) as session:
        repo = WorkspaceRepository(session, 'a')
        identity = create(repo)
        rows = repo.sources_for_submission(identity)
        jobs = repo.jobs_for_submission(identity)
        assert [r['ordinal'] for r in rows] == [0, 1]
        assert rows[0]['id'] != rows[1]['id'] and rows[0]['redshift'] is None
        assert len(jobs) == 4 and all(j['state'] == 'PENDING' for j in jobs)
        assert [j['source_id'] for j in jobs] == [rows[0]['id']]*2 + [rows[1]['id']]*2
        detached = repo.get_submission(identity)
        detached['settings']['frequency_reference'] = 'SKY'
        assert repo.get_submission(identity)['settings']['frequency_reference'] == 'REST'
        other = WorkspaceRepository(session, 'b')
        assert other.list_submissions() == []
        for getter, key in [(other.get_submission, identity), (other.sources_for_submission, identity),
                            (other.jobs_for_submission, identity), (other.get_source, rows[0]['id']),
                            (other.get_job, jobs[0]['id'])]:
            with pytest.raises(RecordUnavailable, match='Record unavailable'):
                getter(key)


def test_atomic_creation_and_validation_before_writes(connection):
    seed(connection)
    with pytest.raises(RuntimeError), transaction(connection) as session:
        create(WorkspaceRepository(session, 'a'))
        raise RuntimeError('abort after creation')
    with transaction(connection) as session:
        assert session.scalar(select(func.count()).select_from(m.submissions)) == 1
        repo = WorkspaceRepository(session, 'a')
        with pytest.raises(ValueError):
            create(repo, sources=[source(), source() | {'ra_deg': float('nan')}])
        with pytest.raises(ValueError):
            create(repo, queue_snapshot_key='snapshot')
        with pytest.raises(ValueError):
            create(repo, input_sha256='z'*64)
        assert session.scalar(select(func.count()).select_from(m.submissions)) == 1


def test_run_attempt_fencing_and_no_overwrite(connection):
    seed(connection)
    now = datetime.now(timezone.utc)
    with transaction(connection) as session:
        repo = WorkspaceRepository(session, 'a')
        identity = create(repo, purposes=['LINE'], sources=[source()])
        job = repo.jobs_for_submission(identity)[0]['id']
        args = dict(attempt=1, lease_token='token', report_schema='v4',
                    assessment_status='UNKNOWN', source_provenance={'ARCHIVE': {'status': 'FAILED'}})
        with pytest.raises(StaleAttempt):
            repo.record_run(job, **args)
        session.execute(m.jobs.update().where(m.jobs.c.id == job).values(state='RUNNING', attempt=1,
            lease_token='token', heartbeat_at=now, lease_expires_at=now + timedelta(hours=1)))
        with pytest.raises(StaleAttempt):
            repo.record_run(job, **(args | {'lease_token': 'old-token'}))
        run_id = repo.record_run(job, **args)
        assert repo.get_run(run_id)['assessment_status'] == 'UNKNOWN'
        assert repo.get_job(job)['state'] == 'RUNNING'  # Metadata is not completed publication.
        with pytest.raises(RecordUnavailable):
            WorkspaceRepository(session, 'b').get_run(run_id)
    with pytest.raises(IntegrityError), transaction(connection) as session:
        WorkspaceRepository(session, 'a').record_run(job, **args)
    with transaction(connection) as session:
        session.execute(m.jobs.update().where(m.jobs.c.id == job).values(lease_expires_at=now-timedelta(hours=1)))
        with pytest.raises(StaleAttempt):
            WorkspaceRepository(session, 'a').record_run(job, **args)
        assert session.scalar(select(func.count()).select_from(m.runs)) == 1
