"""Explicit PostgreSQL connection and transaction boundaries; no implicit fallback."""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def database_engine(url):
    parsed = make_url(url)
    if parsed.drivername != 'postgresql+psycopg':
        raise ValueError('Use an explicit postgresql+psycopg database URL')
    return create_engine(parsed, pool_pre_ping=True, hide_parameters=True)


@contextmanager
def transaction(engine):
    """Commit once on success; rollback and close on any failure."""
    with Session(engine) as session, session.begin():
        yield session
