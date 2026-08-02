from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=(settings.env == "development"))


def init_db() -> None:
    """Create tables. Call once on startup (swap for Alembic migrations later)."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
