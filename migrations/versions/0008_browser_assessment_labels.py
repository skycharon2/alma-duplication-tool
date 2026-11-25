"""Store history display names independently of scientific assessments."""
from alembic import op
import sqlalchemy as sa

revision = '0008_browser_assessment_labels'
down_revision = '0007_browser_artifact_cleanup'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('browser_assessment_labels',
        sa.Column('owner_digest', sa.String(64), primary_key=True),
        sa.Column('assessment_kind', sa.String(8), primary_key=True),
        sa.Column('assessment_id', sa.String(65), primary_key=True),
        sa.Column('display_name', sa.String(80), nullable=False))


def downgrade():
    op.drop_table('browser_assessment_labels')
