"""Unit tests for src/storage/database.py."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from src.storage.database import DatabaseSessionManager


@pytest.fixture
async def session_manager() -> DatabaseSessionManager:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    await manager.create_all()
    return manager


async def test_create_all_creates_expected_table(session_manager: DatabaseSessionManager) -> None:
    async with session_manager.session() as session:
        result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in result.all()}
    assert "storage_records" in tables


async def test_session_commits_on_success(session_manager: DatabaseSessionManager) -> None:
    async with session_manager.session() as session:
        await session.execute(
            text(
                "INSERT INTO storage_records (collection, item_id, data) "
                "VALUES ('tasks', 't1', '{}')"
            )
        )
    async with session_manager.session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM storage_records"))
        assert result.scalar_one() == 1


async def test_session_rolls_back_on_error(session_manager: DatabaseSessionManager) -> None:
    with pytest.raises(RuntimeError):
        async with session_manager.session() as session:
            await session.execute(
                text(
                    "INSERT INTO storage_records (collection, item_id, data) "
                    "VALUES ('tasks', 't2', '{}')"
                )
            )
            raise RuntimeError("simulated failure")

    async with session_manager.session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM storage_records"))
        assert result.scalar_one() == 0


async def test_dispose_is_idempotent(session_manager: DatabaseSessionManager) -> None:
    await session_manager.dispose()
    await session_manager.dispose()  # must not raise


def test_safe_url_strips_credentials() -> None:
    manager = DatabaseSessionManager("postgresql+asyncpg://user:secret@localhost:5432/genesis")
    assert manager._safe_url() == "postgresql+asyncpg://***@localhost:5432/genesis"  # noqa: SLF001


def test_safe_url_passes_through_when_no_credentials() -> None:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///./genesis.db")
    assert manager._safe_url() == "sqlite+aiosqlite:///./genesis.db"  # noqa: SLF001
