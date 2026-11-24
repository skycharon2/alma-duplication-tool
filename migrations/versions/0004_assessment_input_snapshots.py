"""Store browser-owned input snapshots and link published assessments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0004_assessment_input_snapshots'
down_revision = '0003_browser_reports'
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.create_table('assessment_input_snapshots',
        sa.Column('id', sa.String(65), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('owner_digest', sa.String(64), nullable=False),
        sa.Column('snapshot', json_type, nullable=False),
        sa.Column('upload', json_type))
    op.create_index('ix_assessment_input_snapshots_owner_digest', 'assessment_input_snapshots', ['owner_digest'])
    op.create_table('assessment_input_links',
        sa.Column('id', sa.String(65), primary_key=True),
        sa.Column('snapshot_id', sa.String(65), sa.ForeignKey('assessment_input_snapshots.id'), nullable=False),
        sa.Column('report_id', sa.String(65), sa.ForeignKey('browser_reports.id', ondelete='CASCADE'), unique=True),
        sa.Column('batch_id', sa.String(65), sa.ForeignKey('browser_batches.id', ondelete='CASCADE'), unique=True),
        sa.CheckConstraint('(report_id IS NULL) <> (batch_id IS NULL)', name='ck_assessment_input_links_one_parent'))
    op.create_index('ix_assessment_input_links_snapshot_id', 'assessment_input_links', ['snapshot_id'])


def downgrade():
    op.drop_table('assessment_input_links')
    op.drop_table('assessment_input_snapshots')
