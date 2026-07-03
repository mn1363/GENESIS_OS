"""Service Registry (§3) and Capability Registry (§3a).

KERNEL_ARCHITECTURE_PROPOSAL.md:
  "Every registered Service must declare one or more Capabilities it
   provides... The Kernel dispatches requests based on Capabilities
   instead of concrete Service implementations."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.lifecycle import Service, ServiceLifecycleError, ServiceState, validate_transition
from src.core.logging import get_logger

logger = get_logger(__name__)


class CapabilityNotFoundError(RuntimeError):
    """Raised when dispatch() is called for a capability with no registered provider."""


class DuplicateServiceError(RuntimeError):
    """Raised when a service name is registered twice."""


@dataclass
class ServiceEntry:
    """§3 registry entry: name/contract/instance/health_check/dependencies/capabilities."""

    name: str
    instance: Service
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    state: ServiceState = ServiceState.REGISTERED


@dataclass
class CapabilityEntry:
    """§3a registry entry: {capability_name, version, provider_service, contract_schema}."""

    capability: str
    provider_service: str
    contract_schema: dict[str, Any] | None = None


class ServiceRegistry:
    """§3 — what is registered, and is it healthy.

    Not exposed for direct mutation by services; only the Kernel's
    registration API may add/remove entries.
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceEntry] = {}

    def register(
        self,
        name: str,
        instance: Service,
        dependencies: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> ServiceEntry:
        if name in self._services:
            raise DuplicateServiceError(f"Service already registered: {name}")
        entry = ServiceEntry(
            name=name,
            instance=instance,
            dependencies=list(dependencies or []),
            capabilities=list(capabilities or []),
        )
        self._services[name] = entry
        logger.info("service_registered", service=name, capabilities=entry.capabilities)
        return entry

    def get(self, name: str) -> ServiceEntry | None:
        return self._services.get(name)

    def all(self) -> list[ServiceEntry]:
        return list(self._services.values())

    def set_state(self, name: str, target: ServiceState) -> None:
        entry = self._services.get(name)
        if entry is None:
            raise KeyError(f"Unknown service: {name}")
        try:
            validate_transition(entry.state, target)
        except ServiceLifecycleError:
            logger.error(
                "illegal_service_transition", service=name, current=entry.state, target=target
            )
            raise
        entry.state = target
        logger.info("service_state_changed", service=name, state=target)

    def dependency_order(self) -> list[str]:
        """Topologically sort registered services by declared dependencies.

        Raises ValueError on a circular dependency (KERNEL_ARCHITECTURE_PROPOSAL.md §4:
        "Circular dependencies between core services are a boot-time error").
        """
        visited: dict[str, int] = {}  # 0 = visiting, 1 = done
        order: list[str] = []

        def visit(name: str, stack: tuple[str, ...]) -> None:
            if visited.get(name) == 1:
                return
            if visited.get(name) == 0:
                path = " -> ".join(stack + (name,))
                raise ValueError(f"Circular service dependency detected: {path}")
            visited[name] = 0
            entry = self._services.get(name)
            if entry is not None:
                for dep in entry.dependencies:
                    visit(dep, stack + (name,))
            visited[name] = 1
            order.append(name)

        for service_name in self._services:
            visit(service_name, ())
        return order


class CapabilityRegistry:
    """§3a — who do I call for X.

    Kernel dispatch (§5) is always addressed against this registry, never
    against a service name directly.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, list[CapabilityEntry]] = {}
        self._withdrawn: set[tuple[str, str]] = set()  # (capability, provider_service)

    def register(
        self,
        capability: str,
        provider_service: str,
        contract_schema: dict[str, Any] | None = None,
    ) -> None:
        entry = CapabilityEntry(
            capability=capability,
            provider_service=provider_service,
            contract_schema=contract_schema,
        )
        self._capabilities.setdefault(capability, []).append(entry)
        logger.info("capability_registered", capability=capability, provider=provider_service)

    def withdraw(self, capability: str, provider_service: str) -> None:
        """A HEALTHY service may withdraw a single capability without failing entirely
        (KERNEL_ARCHITECTURE_PROPOSAL.md §3a — capability withdrawal is more granular
        than service failure).
        """
        self._withdrawn.add((capability, provider_service))

    def restore(self, capability: str, provider_service: str) -> None:
        self._withdrawn.discard((capability, provider_service))

    def resolve(self, capability: str) -> str:
        """Return the provider_service name for `capability`.

        Default resolution policy (§3a): first active (non-withdrawn) registered
        provider. Load-balanced/priority policies are a documented future
        extension, not implemented here.
        """
        candidates = [
            e
            for e in self._capabilities.get(capability, [])
            if (capability, e.provider_service) not in self._withdrawn
        ]
        if not candidates:
            raise CapabilityNotFoundError(f"No active provider for capability: {capability}")
        return candidates[0].provider_service

    def providers(self, capability: str) -> list[str]:
        return [e.provider_service for e in self._capabilities.get(capability, [])]

    def all_capabilities(self) -> list[str]:
        return list(self._capabilities.keys())
