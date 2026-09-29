"""Use the same database configuration as the app, or a supplied test connection."""

from alembic import context

from app.db.models import Base
from app.db.session import create_db_engine
from app.core.config import get_settings

config = context.config


def run(connection):
    context.configure(
        connection=connection, target_metadata=Base.metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=config.get_main_option("sqlalchemy.url") or get_settings().database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = config.attributes.get("connection")
    if connection is not None:
        run(connection)
    else:
        engine = create_db_engine(
            config.get_main_option("sqlalchemy.url") or get_settings().database_url
        )
        try:
            with engine.connect() as connection:
                run(connection)
        finally:
            engine.dispose()
