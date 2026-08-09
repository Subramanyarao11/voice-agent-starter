"""Alembic environment for the Sahaayak SQLModel schema."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from alembic.config import Config
from sqlalchemy import engine_from_config, pool, text
from sqlmodel import SQLModel

import sahaayak_common.models  # noqa: F401 — registers all tables
from sahaayak_common.settings import settings

config: Config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    """Use the same URL resolution as the application and CLI scripts."""
    return settings.resolved_database_url.replace("%", "%%")


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=settings.using_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # API and worker processes all call init_db() during startup. A
        # PostgreSQL advisory lock makes that safe when Compose starts them at
        # the same time; without it, two migration runners can both create the
        # same enum/table and leave an otherwise healthy stack returning 500s.
        migration_lock_acquired = False
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_lock(736168431)"))
            # SQLAlchemy begins an implicit transaction for the lock query.
            # Commit it before Alembic opens its own migration transaction;
            # otherwise the migration can appear to run successfully but be
            # rolled back when the connection is closed.
            connection.commit()
            migration_lock_acquired = True
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                render_as_batch=settings.using_sqlite,
            )

            with context.begin_transaction():
                context.run_migrations()
        finally:
            if migration_lock_acquired:
                connection.execute(text("SELECT pg_advisory_unlock(736168431)"))
                connection.commit()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
