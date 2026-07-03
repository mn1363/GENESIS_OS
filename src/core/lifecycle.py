"""Service lifecycle contract and states.

Implements KERNEL_ARCHITECTURE_PROPOSAL.md §8: every registered service
exposes start()/stop()/health_check()/on_failure(), and moves through a
fixed set of lifecycle states that the Kernel (not the service itself)
enforces transitions between.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable


class ServiceState(StrEnum):
    """KERNEL_ARCHITECTURE_PROPOSAL.md §8 service lifecycle states."""

    REGISTERED = "registered"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


# States from which a transition to FAILED is legal.
FAILURE_REACHABLE_FROM = frozenset(
    {ServiceState.STARTING, ServiceState.HEALTHY, ServiceState.DEGRADED}
)


@runtime_checkable
class Service(Protocol):
    """The lifecycle contract every Kernel-registered service must implement.

    KERNEL_ARCHITECTURE_PROPOSAL.md §8: `start()`, `stop()`, `health_check()`,
    `on_failure(error)`.
    """

    async def start(self) -> None:
        """Initialize the service. Called once, in dependency order, at boot."""
        ...

    async def stop(self) -> None:
        """Tear down the service. Called once, in reverse dependency order, at shutdown."""
        ...

    async def health_check(self) -> bool:
        """Return True if the service is healthy enough to serve dispatched calls."""
        ...

    async def on_failure(self, error: BaseException) -> None:
        """Called by the Kernel when the service transitions to FAILED or DEGRADED."""
        ...


class ServiceLifecycleError(RuntimeError):
    """Raised when an illegal service state transition is attempted."""


def validate_transition(current: ServiceState, target: ServiceState) -> None:
    """Raise ServiceLifecycleError if current -> target is not a legal transition.

    Legal transitions (KERNEL_ARCHITECTURE_PROPOSAL.md §8):
        REGISTERED -> STARTING
        STARTING   -> HEALTHY | FAILED
        HEALTHY    -> DEGRADED | STOPPING | FAILED
        DEGRADED   -> HEALTHY | STOPPING | FAILED
        STOPPING   -> STOPPED
    FAILED and STOPPED are terminal for this validator (recovery, if any,
    is a new registration, not a resurrection of the old state object).
    """
    legal = {
        ServiceState.REGISTERED: {ServiceState.STARTING},
        ServiceState.STARTING: {ServiceState.HEALTHY, ServiceState.FAILED},
        ServiceState.HEALTHY: {
            ServiceState.DEGRADED,
            ServiceState.STOPPING,
            ServiceState.FAILED,
        },
        ServiceState.DEGRADED: {
            ServiceState.HEALTHY,
            ServiceState.STOPPING,
            ServiceState.FAILED,
        },
        ServiceState.STOPPING: {ServiceState.STOPPED},
        ServiceState.STOPPED: set(),
        ServiceState.FAILED: set(),
    }
    if target not in legal[current]:
        raise ServiceLifecycleError(f"Illegal service state transition: {current} -> {target}")
