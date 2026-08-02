"""Database engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from sahaayak_common.settings import settings


def _engine_kwargs() -> dict:
    if settings.using_sqlite:
        # SQLite refuses cross-thread reuse by default, which FastAPI's
        # threadpool would trip over on the very first request.
        db_path = settings.resolved_database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


engine = create_engine(settings.resolved_database_url, echo=False, **_engine_kwargs())


def init_db() -> None:
    """Create any missing tables.

    Fine for a build-season timeline; swap in Alembic before this schema has
    data worth migrating.
    """
    import sahaayak_common.models  # noqa: F401  — registers tables on the metadata

    SQLModel.metadata.create_all(engine)


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
