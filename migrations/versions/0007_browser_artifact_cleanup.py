"""Persist browser artifact cleanup work across service restarts."""
from alembic import op
import sqlalchemy as sa

revision = '0007_browser_artifact_cleanup'
down_revision = '0006_browser_assessment_trash'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('browser_artifact_cleanup',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('storage_key', sa.String(512), primary_key=True),
        sa.Column('kind', sa.String(32), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True)))


def downgrade():
    op.drop_table('browser_artifact_cleanup')
