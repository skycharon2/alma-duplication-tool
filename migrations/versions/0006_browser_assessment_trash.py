"""Record standalone assessment groups and browser-owned trash state."""
from alembic import op
import sqlalchemy as sa

revision = '0006_browser_assessment_trash'
down_revision = '0005_browser_history_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('browser_reports', sa.Column('assessment_group_id', sa.String(65)))
    # A snapshot is written once per standalone submission. Reports predating
    # snapshots have no durable shared submission identity.
    op.execute("""
        UPDATE browser_reports
        SET assessment_group_id = (
            SELECT links.snapshot_id
            FROM assessment_input_links AS links
            JOIN assessment_input_snapshots AS snapshots ON snapshots.id = links.snapshot_id
            WHERE links.report_id = browser_reports.id
              AND snapshots.owner_digest = browser_reports.owner_digest
        )
        WHERE batch_id IS NULL
    """)
    op.create_index('ix_browser_reports_assessment_group', 'browser_reports',
                    ['owner_digest', 'assessment_group_id'])
    op.create_table('browser_assessment_trash',
        sa.Column('owner_digest', sa.String(64), primary_key=True),
        sa.Column('assessment_kind', sa.String(8), primary_key=True),
        sa.Column('assessment_id', sa.String(65), primary_key=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('purge_after', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("assessment_kind IN ('REPORT', 'BATCH')",
                           name=op.f('ck_browser_assessment_trash_assessment_kind')),
        sa.CheckConstraint('purge_after >= deleted_at',
                           name=op.f('ck_browser_assessment_trash_purge_after_deletion')))


def downgrade():
    op.drop_table('browser_assessment_trash')
    op.drop_index('ix_browser_reports_assessment_group', table_name='browser_reports')
    op.drop_column('browser_reports', 'assessment_group_id')
