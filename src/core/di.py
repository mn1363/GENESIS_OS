"""DI Container.

KERNEL_ARCHITECTURE_PROPOSAL.md §4: constructor injection only, resolved
by the Kernel in dependency order at boot time; dependencies are declared
and injected by capability, not by concrete service reference.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Factory = Callable[..., Any]


class DIContainer:
    """Minimal constructor-injection container.

    Services are constructed by the Kernel's boot sequencer (§6) calling
    `build(name)` in dependency order (ServiceRegistry.dependency_order()).
    A factory receives already-built dependencies as keyword arguments
    keyed by dependency name.
    """

    def __init__(self) -> None:
        self._factories: dict[str, Factory] = {}
        self._dependencies: dict[str, list[str]] = {}
        self._built: dict[str, Any] = {}

    def register_factory(
        self, name: str, factory: Factory, dependencies: list[str] | None = None
    ) -> None:
        self._factories[name] = factory
        self._dependencies[name] = list(dependencies or [])

    def build(self, name: str) -> Any:
        """Build (or return the cached build of) the named component.

        Recursively builds dependencies first. Raises RecursionError-safe
        ValueError on cycles via the same style of check as
        ServiceRegistry.dependency_order(); in practice the Kernel calls
        build() in an order already validated by ServiceRegistry, so this
        is a defense-in-depth check, not the primary cycle detector.
        """
        if name in self._built:
            return self._built[name]
        if name not in self._factories:
            raise KeyError(f"No factory registered for: {name}")

        kwargs = {dep: self.build(dep) for dep in self._dependencies[name]}
        instance = self._factories[name](**kwargs)
        self._built[name] = instance
        return instance

    def get_built(self, name: str) -> Any | None:
        return self._built.get(name)

    def reset(self) -> None:
        """Clear built instances (not factories) — used between test runs."""
        self._built.clear()
