"""Use ALMA_DATABASE_URL explicitly; never migrate on application startup."""
import os
from alembic import context
from alma_duplicate.persistence.db import database_engine
from alma_duplicate.persistence.models import metadata

config = context.config


def migrate(connection):
    context.configure(connection=connection, target_metadata=metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(dialect_name='postgresql', target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get('connection') is not None:
    migrate(config.attributes['connection'])
else:
    url = os.environ.get('ALMA_DATABASE_URL')
    if not url:
        raise RuntimeError('ALMA_DATABASE_URL is required for online migrations')
    engine = database_engine(url)
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()
