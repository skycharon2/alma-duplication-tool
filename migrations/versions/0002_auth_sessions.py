"""Revocable server-side login sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0002_auth_sessions'
down_revision = '0001_persistence_foundation'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_sessions',
        sa.Column('id', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('user_id', sa.String(65), nullable=False),
        sa.Column('workspace_id', sa.String(65), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_auth_sessions'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_auth_sessions_user_id_users'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_auth_sessions_workspace_id_workspaces'),
        sa.CheckConstraint('length(id) = 64', name='ck_auth_sessions_digest_length'))
    op.create_index('ix_auth_sessions_expiry', 'auth_sessions', ['expires_at'])


def downgrade():
    op.drop_index('ix_auth_sessions_expiry', table_name='auth_sessions')
    op.drop_table('auth_sessions')
