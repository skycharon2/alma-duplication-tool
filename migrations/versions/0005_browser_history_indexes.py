"""Index browser-owned history in pagination order."""
from alembic import op

revision = '0005_browser_history_indexes'
down_revision = '0004_assessment_input_snapshots'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_browser_batches_history', 'browser_batches',
                    ['owner_digest', 'created_at', 'id'])
    op.create_index('ix_browser_reports_history', 'browser_reports',
                    ['owner_digest', 'batch_id', 'created_at', 'id'])
    op.drop_index('ix_browser_batches_owner_digest', table_name='browser_batches')
    op.drop_index('ix_browser_reports_owner_digest', table_name='browser_reports')


def downgrade():
    op.create_index('ix_browser_batches_owner_digest', 'browser_batches', ['owner_digest'])
    op.create_index('ix_browser_reports_owner_digest', 'browser_reports', ['owner_digest'])
    op.drop_index('ix_browser_reports_history', table_name='browser_reports')
    op.drop_index('ix_browser_batches_history', table_name='browser_batches')
