"""Managed hosts inject bare postgres URLs; local Compose already has +psycopg."""

from sahaayak_common.settings import normalize_database_url


def test_normalize_leaves_psycopg_driver_urls_unchanged() -> None:
    url = "postgresql+psycopg://sahaayak:sahaayak@localhost:5433/sahaayak"
    assert normalize_database_url(url) == url


def test_normalize_rewrites_postgresql_scheme() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )


def test_normalize_rewrites_postgres_scheme() -> None:
    assert (
        normalize_database_url("postgres://user:pass@db:5432/app")
        == "postgresql+psycopg://user:pass@db:5432/app"
    )


def test_normalize_leaves_sqlite_unchanged() -> None:
    url = "sqlite:////tmp/sahaayak.db"
    assert normalize_database_url(url) == url
