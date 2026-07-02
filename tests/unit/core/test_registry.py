"""Unit tests for src/core/registry.py."""

from __future__ import annotations

import pytest
from src.core.registry import (
    CapabilityNotFoundError,
    CapabilityRegistry,
    DuplicateServiceError,
    ServiceRegistry,
)


class DummyService:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health_check(self) -> bool:
        return True

    async def on_failure(self, error: BaseException) -> None: ...


def test_service_registry_rejects_duplicate_names() -> None:
    reg = ServiceRegistry()
    reg.register("a", DummyService())
    with pytest.raises(DuplicateServiceError):
        reg.register("a", DummyService())


def test_service_registry_dependency_order() -> None:
    reg = ServiceRegistry()
    reg.register("memory", DummyService())
    reg.register("planner", DummyService(), dependencies=["memory"])
    reg.register("execution", DummyService(), dependencies=["planner"])
    order = reg.dependency_order()
    assert order.index("memory") < order.index("planner") < order.index("execution")


def test_service_registry_detects_cycles() -> None:
    reg = ServiceRegistry()
    reg.register("a", DummyService(), dependencies=["b"])
    reg.register("b", DummyService(), dependencies=["a"])
    with pytest.raises(ValueError):
        reg.dependency_order()


def test_capability_registry_resolve() -> None:
    caps = CapabilityRegistry()
    caps.register("memory.retrieve_context@v1", provider_service="memory")
    assert caps.resolve("memory.retrieve_context@v1") == "memory"


def test_capability_registry_no_provider_raises() -> None:
    caps = CapabilityRegistry()
    with pytest.raises(CapabilityNotFoundError):
        caps.resolve("nonexistent@v1")


def test_capability_registry_withdraw_and_restore() -> None:
    caps = CapabilityRegistry()
    caps.register("memory.semantic_search@v1", provider_service="memory")
    caps.withdraw("memory.semantic_search@v1", "memory")
    with pytest.raises(CapabilityNotFoundError):
        caps.resolve("memory.semantic_search@v1")
    caps.restore("memory.semantic_search@v1", "memory")
    assert caps.resolve("memory.semantic_search@v1") == "memory"


def test_capability_registry_multiple_providers_first_active_wins() -> None:
    caps = CapabilityRegistry()
    caps.register("execution.run_step@v1", provider_service="engine_a")
    caps.register("execution.run_step@v1", provider_service="engine_b")
    assert caps.resolve("execution.run_step@v1") == "engine_a"
    caps.withdraw("execution.run_step@v1", "engine_a")
    assert caps.resolve("execution.run_step@v1") == "engine_b"
