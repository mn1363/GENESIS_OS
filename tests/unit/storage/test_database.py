"""Unit tests for src/storage/database.py."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys

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


def test_construction_does_not_create_an_engine() -> None:
    """GEN-0025: constructing DatabaseSessionManager must not require the
    URL's DBAPI driver to be importable — engine creation is deferred to
    first actual use."""
    manager = DatabaseSessionManager("postgresql+asyncpg://user:pass@localhost/db")
    assert manager._engine is None  # noqa: SLF001
    assert manager._sessionmaker is None  # noqa: SLF001


async def test_construction_succeeds_even_for_an_unimportable_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GEN-0025's core regression guard: block the driver module entirely
    and confirm construction still succeeds; only first real use fails."""

    class _Blocker(importlib.abc.MetaPathFinder):
        def find_spec(
            self, name: str, path: object, target: object = None
        ) -> importlib.machinery.ModuleSpec | None:
            if name == "aiosqlite" or name.startswith("aiosqlite."):
                raise ModuleNotFoundError(f"simulated: {name} not installed")
            return None

    for name in list(sys.modules):
        if name.startswith("aiosqlite"):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, "meta_path", [_Blocker(), *sys.meta_path])

    manager = DatabaseSessionManager("sqlite+aiosqlite:///./should_not_be_touched.db")

    with pytest.raises(ModuleNotFoundError):
        await manager.create_all()


async def test_dispose_without_prior_use_is_a_no_op_and_needs_no_driver() -> None:
    """GEN-0025: disposing a never-used manager must not construct an
    engine just to tear it down."""
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    await manager.dispose()
    assert manager._engine is None  # noqa: SLF001


async def test_engine_is_created_once_and_reused_across_calls() -> None:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    await manager.create_all()
    first_engine = manager._engine  # noqa: SLF001
    async with manager.session():
        pass
    assert manager._engine is first_engine  # noqa: SLF001
