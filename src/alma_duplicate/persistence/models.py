"""Metadata only. Scientific reports remain immutable external artifacts.

Composite foreign keys prevent cross-workspace associations, but do not replace
server-side authorization. No ORM cascades or database schema creation on import.
"""
from uuid import uuid4

from sqlalchemy import (MetaData, Table, Column, String, Integer, BigInteger,
                        Float, DateTime, JSON, ForeignKey, ForeignKeyConstraint,
                        UniqueConstraint, CheckConstraint, Index, func)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(naming_convention={
    'ix': 'ix_%(table_name)s_%(column_0_name)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
})
json_type = JSON().with_variant(JSONB(), 'postgresql')


def identity():
    return Column('id', String(65), primary_key=True, default=lambda: uuid4().hex)


def created():
    return Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())


def scope():
    return Column('workspace_id', String(65), ForeignKey('workspaces.id'), nullable=False)


users = Table('users', metadata, identity(), created(),
    Column('issuer', String(512), nullable=False),
    Column('subject', String(255), nullable=False),
    UniqueConstraint('issuer', 'subject'))
workspaces = Table('workspaces', metadata, identity(), created(),
    Column('owner_id', String(65), ForeignKey('users.id'), nullable=False),
    Column('name', String(255), nullable=False))
submissions = Table('submissions', metadata, identity(), created(), scope(),
    Column('kind', String(16), nullable=False),
    Column('settings', json_type, nullable=False),
    Column('input_sha256', String(64), nullable=False),
    Column('queue_snapshot_sha256', String(64)),
    Column('queue_snapshot_key', String(512)),
    UniqueConstraint('workspace_id', 'id'),
    CheckConstraint("kind IN ('SINGLE', 'MULTI', 'MOSAIC')", name='kind'),
    CheckConstraint('length(input_sha256) = 64', name='input_hash_length'),
    CheckConstraint('(queue_snapshot_sha256 IS NULL AND queue_snapshot_key IS NULL) OR '
                    '(queue_snapshot_sha256 IS NOT NULL AND length(queue_snapshot_sha256) = 64 '
                    'AND queue_snapshot_key IS NOT NULL)', name='snapshot_binding'))
sources = Table('sources', metadata, identity(), created(), scope(),
    Column('submission_id', String(65), nullable=False),
    Column('ordinal', Integer, nullable=False),
    Column('name', String(255), nullable=False),
    Column('ra_deg', Float, nullable=False), Column('dec_deg', Float, nullable=False),
    Column('redshift', Float), Column('original_input', json_type, nullable=False),
    ForeignKeyConstraint(['workspace_id', 'submission_id'], ['submissions.workspace_id', 'submissions.id']),
    UniqueConstraint('workspace_id', 'submission_id', 'id'),
    UniqueConstraint('submission_id', 'ordinal'),
    CheckConstraint('ordinal >= 0', name='ordinal'),
    CheckConstraint('ra_deg >= 0 AND ra_deg < 360 AND dec_deg >= -90 AND dec_deg <= 90', name='coordinates'),
    CheckConstraint('redshift IS NULL OR (redshift > -1 AND redshift < 1e308)', name='redshift'))
jobs = Table('jobs', metadata, identity(), created(), scope(),
    Column('submission_id', String(65), nullable=False), Column('source_id', String(65), nullable=False),
    Column('purpose', String(16), nullable=False),
    Column('state', String(16), nullable=False, server_default='PENDING'),
    Column('attempt', Integer, nullable=False, server_default='0'),
    Column('lease_token', String(65)), Column('lease_expires_at', DateTime(timezone=True)),
    Column('heartbeat_at', DateTime(timezone=True)),
    ForeignKeyConstraint(['workspace_id', 'submission_id', 'source_id'],
                         ['sources.workspace_id', 'sources.submission_id', 'sources.id']),
    UniqueConstraint('workspace_id', 'id'), UniqueConstraint('source_id', 'purpose'),
    CheckConstraint("purpose IN ('LINE', 'CONTINUUM')", name='purpose'),
    CheckConstraint("state IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')", name='state'),
    CheckConstraint('attempt >= 0', name='attempt'),
    CheckConstraint("(state = 'RUNNING' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL "
                    "AND heartbeat_at IS NOT NULL AND attempt > 0) OR (state <> 'RUNNING' "
                    "AND lease_token IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL)", name='lease'))
Index('ix_jobs_dispatch', jobs.c.state, jobs.c.lease_expires_at, jobs.c.created_at)
runs = Table('runs', metadata, identity(), created(), scope(),
    Column('job_id', String(65), nullable=False), Column('attempt', Integer, nullable=False),
    Column('report_schema', String(128), nullable=False),
    Column('assessment_status', String(64), nullable=False),
    Column('source_provenance', json_type, nullable=False),
    ForeignKeyConstraint(['workspace_id', 'job_id'], ['jobs.workspace_id', 'jobs.id']),
    UniqueConstraint('workspace_id', 'id'), UniqueConstraint('job_id', 'attempt'),
    CheckConstraint('attempt > 0', name='attempt'))
artifacts = Table('artifacts', metadata, identity(), created(), scope(),
    Column('run_id', String(65), nullable=False), Column('kind', String(64), nullable=False),
    Column('storage_key', String(512), nullable=False, unique=True),
    Column('sha256', String(64), nullable=False), Column('byte_size', BigInteger, nullable=False),
    ForeignKeyConstraint(['workspace_id', 'run_id'], ['runs.workspace_id', 'runs.id']),
    UniqueConstraint('run_id', 'kind'), CheckConstraint('byte_size >= 0', name='byte_size'),
    CheckConstraint('length(sha256) = 64', name='hash_length'))

# Opaque browser secrets are hashed before storage; deleting a row revokes it.
auth_sessions = Table('auth_sessions', metadata,
    Column('id', String(64), primary_key=True), created(),
    Column('user_id', String(65), ForeignKey('users.id'), nullable=False),
    Column('workspace_id', String(65), ForeignKey('workspaces.id'), nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False),
    CheckConstraint('length(id) = 64', name='digest_length'))
Index('ix_auth_sessions_expiry', auth_sessions.c.expires_at)
