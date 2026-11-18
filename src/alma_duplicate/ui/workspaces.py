"""Personal workspace provisioning and revocable login session lookup."""
from datetime import datetime, timedelta, timezone
import hashlib
from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from alma_duplicate.persistence import models as m
from alma_duplicate.persistence.db import transaction


def _digest(secret):
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()


def create_login(engine, issuer, subject, *, token_expires_at):
    """Called only after verified OIDC claims; email never defines identity."""
    if (not isinstance(issuer, str) or not issuer or len(issuer) > 512 or
            not isinstance(subject, str) or not subject or len(subject) > 255):
        raise ValueError('Invalid verified identity')
    now = datetime.now(timezone.utc)
    expiry = min(now + timedelta(hours=8), token_expires_at)
    if expiry <= now:
        raise ValueError('Expired identity')
    secret = token_urlsafe(32)
    with transaction(engine) as session:
        dialect = session.get_bind().dialect.name
        insert = pg_insert if dialect == 'postgresql' else sqlite_insert
        session.execute(insert(m.users).values(id=uuid4().hex, issuer=issuer, subject=subject)
                        .on_conflict_do_nothing(index_elements=['issuer', 'subject']))
        user = session.execute(select(m.users).where(m.users.c.issuer == issuer,
            m.users.c.subject == subject).with_for_update()).mappings().one()
        workspace = session.execute(select(m.workspaces).where(m.workspaces.c.owner_id == user['id'])
                                    .order_by(m.workspaces.c.created_at, m.workspaces.c.id).limit(1)).mappings().first()
        if workspace is None:
            workspace = dict(id=uuid4().hex, owner_id=user['id'], name='Personal workspace')
            session.execute(m.workspaces.insert().values(**workspace))
        session.execute(m.auth_sessions.insert().values(id=_digest(secret), user_id=user['id'],
                        workspace_id=workspace['id'], expires_at=expiry))
    return secret


def resolve_login(engine, secret):
    if not isinstance(secret, str) or not 32 <= len(secret) <= 128:
        return None
    with transaction(engine) as session:
        clock = func.clock_timestamp() if session.get_bind().dialect.name == 'postgresql' else func.current_timestamp()
        row = session.execute(select(m.auth_sessions.c.user_id, m.auth_sessions.c.workspace_id,
            m.workspaces.c.name).join(m.workspaces, m.auth_sessions.c.workspace_id == m.workspaces.c.id)
            .where(m.auth_sessions.c.id == _digest(secret), m.auth_sessions.c.expires_at > clock,
                   m.workspaces.c.owner_id == m.auth_sessions.c.user_id)).mappings().first()
        return dict(row) if row else None


def revoke_login(engine, secret):
    if isinstance(secret, str) and len(secret) <= 128:
        with transaction(engine) as session:
            session.execute(m.auth_sessions.delete().where(m.auth_sessions.c.id == _digest(secret)))
