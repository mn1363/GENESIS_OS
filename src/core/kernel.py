"""Runtime Kernel.

Ties together everything specified in KERNEL_ARCHITECTURE_PROPOSAL.md:
Service Registry (§3), Capability Registry (§3a), Kernel Scheduler (§3b),
DI Container (§4), Event Bus (§5), Task State Store, boot sequence (§6),
shutdown sequence (§7), and capability-addressed dispatch.

Phase 2 scope: this implements the Kernel itself plus the four other
Phase 2 roadmap objectives (Configuration System, Event System, Service
Registry, Logging). It does not implement any Runtime-layer subsystem
(Planner, Memory, Agent Runtime, Execution Engine, Quality Engine) — those
are Phase 3+ and are exercised here only via a minimal example service in
tests, to prove the Kernel boots, dispatches, and shuts down correctly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from src.config.settings import Settings, get_settings
from src.core.di import DIContainer
from src.core.events import EventBus
from src.core.lifecycle import Service, ServiceState
from src.core.logging import configure_logging, get_logger
from src.core.registry import CapabilityRegistry, ServiceEntry, ServiceRegistry
from src.core.scheduler import KernelScheduler
from src.core.tasks import Task, TaskStateStore

logger = get_logger(__name__)

CapabilityHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class KernelBootError(RuntimeError):
    """Raised when a mandatory service fails its boot-time health check."""


class Kernel:
    """The Runtime Kernel — see KERNEL_ARCHITECTURE_PROPOSAL.md.

    Usage:
        kernel = Kernel()
        kernel.register_service("echo", EchoService(), capability_handlers={...})
        await kernel.boot()
        result = await kernel.dispatch("echo.say@v1", {"text": "hi"})
        await kernel.shutdown()
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        configure_logging(self.settings.log_level)

        self.services = ServiceRegistry()
        self.capabilities = CapabilityRegistry()
        self.events = EventBus()
        self.tasks = TaskStateStore()
        self.di = DIContainer()

        self.scheduler = KernelScheduler(
            task_store=self.tasks,
            event_bus=self.events,
            dispatch_fn=self.dispatch,
            max_concurrent_tasks=self.settings.scheduler_max_concurrent_tasks,
            default_timeout_seconds=self.settings.scheduler_default_task_timeout_seconds,
            default_max_retries=self.settings.scheduler_default_max_retries,
            retry_backoff_base_seconds=self.settings.scheduler_retry_backoff_base_seconds,
        )

        self._capability_handlers: dict[tuple[str, str], CapabilityHandler] = {}
        self._mandatory_services: set[str] = set()
        self._booted = False

    # ---- Registration -----------------------------------------------------------------

    def register_service(
        self,
        name: str,
        instance: Service,
        capability_handlers: dict[str, CapabilityHandler] | None = None,
        dependencies: list[str] | None = None,
        mandatory: bool = True,
    ) -> ServiceEntry:
        """Register a service and its declared capabilities.

        KERNEL_ARCHITECTURE_PROPOSAL.md §3a: "Every registered Service must
        declare one or more Capabilities it provides."
        """
        capability_handlers = capability_handlers or {}
        entry = self.services.register(
            name=name,
            instance=instance,
            dependencies=dependencies,
            capabilities=list(capability_handlers.keys()),
        )
        for capability, handler in capability_handlers.items():
            self.capabilities.register(capability, provider_service=name)
            self._capability_handlers[(capability, name)] = handler
        if mandatory:
            self._mandatory_services.add(name)
        logger.info("service_registration_complete", service=name)
        return entry

    # ---- Dispatch (§5, §3a) ------------------------------------------------------------

    async def dispatch(self, capability: str, payload: dict[str, Any] | None = None) -> Any:
        """Capability-addressed synchronous dispatch.

        Resolves `capability` to a provider via the Capability Registry,
        never addresses a service by name directly (KERNEL_ARCHITECTURE_PROPOSAL.md §5).
        """
        provider = self.capabilities.resolve(capability)
        handler = self._capability_handlers.get((capability, provider))
        if handler is None:
            raise RuntimeError(f"No handler registered for {capability} on {provider}")
        return await asyncio.wait_for(
            handler(payload or {}), timeout=self.settings.kernel_dispatch_timeout_seconds
        )

    async def submit_task(
        self,
        capability: str,
        payload: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> Task:
        """Submit work to the Kernel Scheduler (§3b) rather than dispatching directly.

        Use dispatch() for an immediate synchronous call; use submit_task()
        when the caller wants scheduling (priority/queueing/concurrency/retry).
        """
        return await self.scheduler.submit(capability, payload, priority=priority)

    # ---- Boot sequence (§6) -------------------------------------------------------------

    async def boot(self) -> None:
        """Boot sequence per KERNEL_ARCHITECTURE_PROPOSAL.md §6, steps 4-10.

        Steps 1-3 (config load, logging init, infra connections) are the
        caller's responsibility for Phase 2 (no Storage/Qdrant/Redis
        integration exists yet — see tasks.py's Phase 2 scope note); this
        method covers Kernel construction (already done in __init__) through
        service startup and ready state.
        """
        if self._booted:
            return
        logger.info("kernel_boot_starting")

        order = self.services.dependency_order()
        for name in order:
            entry = self.services.get(name)
            if entry is None:
                continue
            self.services.set_state(name, ServiceState.STARTING)
            try:
                await asyncio.wait_for(
                    entry.instance.start(), timeout=self.settings.boot_health_check_timeout_seconds
                )
                healthy = await asyncio.wait_for(
                    entry.instance.health_check(),
                    timeout=self.settings.boot_health_check_timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                self.services.set_state(name, ServiceState.FAILED)
                await entry.instance.on_failure(exc)
                if name in self._mandatory_services:
                    logger.error("mandatory_service_boot_failed", service=name, error=str(exc))
                    raise KernelBootError(f"Mandatory service failed to boot: {name}") from exc
                logger.warning("optional_service_boot_failed", service=name, error=str(exc))
                continue

            if healthy:
                self.services.set_state(name, ServiceState.HEALTHY)
            else:
                self.services.set_state(name, ServiceState.DEGRADED)
                if name in self._mandatory_services:
                    raise KernelBootError(f"Mandatory service unhealthy at boot: {name}")

        await self.scheduler.start()
        self._booted = True
        await self.events.publish("system.boot.completed", {})
        logger.info("kernel_boot_completed")

    # ---- Shutdown sequence (§7) ---------------------------------------------------------

    async def shutdown(self) -> None:
        """Shutdown sequence per KERNEL_ARCHITECTURE_PROPOSAL.md §7."""
        if not self._booted:
            return
        logger.info("kernel_shutdown_starting")
        await self.events.publish("system.shutdown.requested", {})

        await self.scheduler.stop(grace_period_seconds=self.settings.shutdown_grace_period_seconds)

        for name in reversed(self.services.dependency_order()):
            entry = self.services.get(name)
            if entry is None or entry.state in (ServiceState.FAILED, ServiceState.STOPPED):
                continue
            try:
                self.services.set_state(name, ServiceState.STOPPING)
                await entry.instance.stop()
                self.services.set_state(name, ServiceState.STOPPED)
            except Exception as exc:  # noqa: BLE001
                logger.error("service_shutdown_error", service=name, error=str(exc))

        self._booted = False
        await self.events.publish("system.shutdown.completed", {})
        logger.info("kernel_shutdown_completed")
