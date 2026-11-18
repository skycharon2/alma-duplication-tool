"""Initial scoped metadata schema. No scientific report blobs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_persistence_foundation'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('issuer', sa.String(length=512), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('issuer', 'subject', name=op.f('uq_users_issuer'))
    )
    op.create_table('workspaces',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('owner_id', sa.String(length=65), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_workspaces_owner_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspaces'))
    )
    op.create_table('submissions',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('workspace_id', sa.String(length=65), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('settings', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('input_sha256', sa.String(length=64), nullable=False),
    sa.Column('queue_snapshot_sha256', sa.String(length=64), nullable=True),
    sa.Column('queue_snapshot_key', sa.String(length=512), nullable=True),
    sa.CheckConstraint("kind IN ('SINGLE', 'MULTI', 'MOSAIC')", name=op.f('ck_submissions_kind')),
    sa.CheckConstraint('(queue_snapshot_sha256 IS NULL AND queue_snapshot_key IS NULL) OR (queue_snapshot_sha256 IS NOT NULL AND length(queue_snapshot_sha256) = 64 AND queue_snapshot_key IS NOT NULL)', name=op.f('ck_submissions_snapshot_binding')),
    sa.CheckConstraint('length(input_sha256) = 64', name=op.f('ck_submissions_input_hash_length')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_submissions_workspace_id_workspaces')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_submissions')),
    sa.UniqueConstraint('workspace_id', 'id', name=op.f('uq_submissions_workspace_id'))
    )
    op.create_table('sources',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('workspace_id', sa.String(length=65), nullable=False),
    sa.Column('submission_id', sa.String(length=65), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('ra_deg', sa.Float(), nullable=False),
    sa.Column('dec_deg', sa.Float(), nullable=False),
    sa.Column('redshift', sa.Float(), nullable=True),
    sa.Column('original_input', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.CheckConstraint('ordinal >= 0', name=op.f('ck_sources_ordinal')),
    sa.CheckConstraint('ra_deg >= 0 AND ra_deg < 360 AND dec_deg >= -90 AND dec_deg <= 90', name=op.f('ck_sources_coordinates')),
    sa.CheckConstraint('redshift IS NULL OR (redshift > -1 AND redshift < 1e308)', name=op.f('ck_sources_redshift')),
    sa.ForeignKeyConstraint(['workspace_id', 'submission_id'], ['submissions.workspace_id', 'submissions.id'], name=op.f('fk_sources_workspace_id_submissions')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_sources_workspace_id_workspaces')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sources')),
    sa.UniqueConstraint('submission_id', 'ordinal', name=op.f('uq_sources_submission_id')),
    sa.UniqueConstraint('workspace_id', 'submission_id', 'id', name=op.f('uq_sources_workspace_id'))
    )
    op.create_table('jobs',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('workspace_id', sa.String(length=65), nullable=False),
    sa.Column('submission_id', sa.String(length=65), nullable=False),
    sa.Column('source_id', sa.String(length=65), nullable=False),
    sa.Column('purpose', sa.String(length=16), nullable=False),
    sa.Column('state', sa.String(length=16), server_default='PENDING', nullable=False),
    sa.Column('attempt', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lease_token', sa.String(length=65), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(state = 'RUNNING' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL AND attempt > 0) OR (state <> 'RUNNING' AND lease_token IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL)", name=op.f('ck_jobs_lease')),
    sa.CheckConstraint("purpose IN ('LINE', 'CONTINUUM')", name=op.f('ck_jobs_purpose')),
    sa.CheckConstraint("state IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')", name=op.f('ck_jobs_state')),
    sa.CheckConstraint('attempt >= 0', name=op.f('ck_jobs_attempt')),
    sa.ForeignKeyConstraint(['workspace_id', 'submission_id', 'source_id'], ['sources.workspace_id', 'sources.submission_id', 'sources.id'], name=op.f('fk_jobs_workspace_id_sources')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_jobs_workspace_id_workspaces')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_jobs')),
    sa.UniqueConstraint('source_id', 'purpose', name=op.f('uq_jobs_source_id')),
    sa.UniqueConstraint('workspace_id', 'id', name=op.f('uq_jobs_workspace_id'))
    )
    op.create_index('ix_jobs_dispatch', 'jobs', ['state', 'lease_expires_at', 'created_at'], unique=False)
    op.create_table('runs',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('workspace_id', sa.String(length=65), nullable=False),
    sa.Column('job_id', sa.String(length=65), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('report_schema', sa.String(length=128), nullable=False),
    sa.Column('assessment_status', sa.String(length=64), nullable=False),
    sa.Column('source_provenance', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.CheckConstraint('attempt > 0', name=op.f('ck_runs_attempt')),
    sa.ForeignKeyConstraint(['workspace_id', 'job_id'], ['jobs.workspace_id', 'jobs.id'], name=op.f('fk_runs_workspace_id_jobs')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_runs_workspace_id_workspaces')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_runs')),
    sa.UniqueConstraint('job_id', 'attempt', name=op.f('uq_runs_job_id')),
    sa.UniqueConstraint('workspace_id', 'id', name=op.f('uq_runs_workspace_id'))
    )
    op.create_table('artifacts',
    sa.Column('id', sa.String(length=65), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('workspace_id', sa.String(length=65), nullable=False),
    sa.Column('run_id', sa.String(length=65), nullable=False),
    sa.Column('kind', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('byte_size', sa.BigInteger(), nullable=False),
    sa.CheckConstraint('byte_size >= 0', name=op.f('ck_artifacts_byte_size')),
    sa.CheckConstraint('length(sha256) = 64', name=op.f('ck_artifacts_hash_length')),
    sa.ForeignKeyConstraint(['workspace_id', 'run_id'], ['runs.workspace_id', 'runs.id'], name=op.f('fk_artifacts_workspace_id_runs')),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_artifacts_workspace_id_workspaces')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_artifacts')),
    sa.UniqueConstraint('run_id', 'kind', name=op.f('uq_artifacts_run_id')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_artifacts_storage_key'))
    )

def downgrade():
    op.drop_table('artifacts')
    op.drop_table('runs')
    op.drop_index('ix_jobs_dispatch', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('sources')
    op.drop_table('submissions')
    op.drop_table('workspaces')
    op.drop_table('users')
