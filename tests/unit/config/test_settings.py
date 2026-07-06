"""Unit tests for src/config/settings.py."""

from __future__ import annotations

from src.config.settings import Settings


def test_database_backend_sqlite() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///./genesis.db")
    assert settings.database_backend == "sqlite"


def test_database_backend_postgresql() -> None:
    settings = Settings(database_url="postgresql+asyncpg://user:pass@localhost/db")
    assert settings.database_backend == "postgresql"


def test_database_backend_default_matches_default_url() -> None:
    settings = Settings()
    assert settings.database_backend == "sqlite"


def test_database_backend_handles_scheme_with_no_driver_suffix() -> None:
    settings = Settings(database_url="sqlite:///./genesis.db")
    assert settings.database_backend == "sqlite"
