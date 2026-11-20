"""Browser-scoped persistent reports and completed batches."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0003_browser_reports'
down_revision = '0002_auth_sessions'
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.create_table('browser_batches',
        sa.Column('id', sa.String(65), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('owner_digest', sa.String(64), nullable=False),
        sa.Column('manifest', json_type, nullable=False))
    op.create_index('ix_browser_batches_owner_digest', 'browser_batches', ['owner_digest'])
    op.create_table('browser_reports',
        sa.Column('id', sa.String(65), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('owner_digest', sa.String(64), nullable=False),
        sa.Column('assessment_status', sa.String(64), nullable=False),
        sa.Column('artifact_manifest', json_type, nullable=False),
        sa.Column('overview', json_type, nullable=False),
        sa.Column('batch_id', sa.String(65), sa.ForeignKey('browser_batches.id', name='fk_browser_reports_batch_id_browser_batches')))
    op.create_index('ix_browser_reports_owner_digest', 'browser_reports', ['owner_digest'])


def downgrade():
    op.drop_table('browser_reports')
    op.drop_table('browser_batches')
