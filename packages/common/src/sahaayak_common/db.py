"""Database engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from sahaayak_common.settings import REPO_ROOT, settings


def _engine_kwargs() -> dict:
    if settings.using_sqlite:
        # SQLite refuses cross-thread reuse by default, which FastAPI's
        # threadpool would trip over on the very first request.
        db_path = settings.resolved_database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


engine = create_engine(settings.resolved_database_url, echo=False, **_engine_kwargs())


def _alembic_config():
    from alembic.config import Config

    return Config(str(REPO_ROOT / "alembic.ini"))


def _has_legacy_schema() -> bool:
    required = {"language", "state", "benefit", "user_session"}
    with engine.connect() as connection:
        return required.issubset(inspect(connection).get_table_names())


def run_migrations() -> None:
    """Apply the checked-in Alembic revisions to the configured database."""
    from alembic import command

    config = _alembic_config()
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        has_version_table = "alembic_version" in tables

    # The repository shipped with create_all before Alembic. A local database
    # created by that version already has the 0001 schema, so stamp only that
    # baseline and then apply the provenance revision. Production databases
    # must be provisioned through the normal migration command instead.
    if settings.is_development and _has_legacy_schema() and not has_version_table:
        command.stamp(config, "20260802_0001")

    command.upgrade(config, "head")


def init_db() -> None:
    """Prepare the schema, using create_all only for isolated test databases."""
    import sahaayak_common.models  # noqa: F401  — registers tables on the metadata

    if settings.is_test:
        SQLModel.metadata.create_all(engine)
        return
    run_migrations()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session for scripts and background work."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
