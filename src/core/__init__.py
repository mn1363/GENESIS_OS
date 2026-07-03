"""Sealed Core Architecture.

Per README.md and GEN-0002_Core_Principles.md, this package is immutable
once implemented: runtime/plugin code may depend on it, but must never be
depended on by it, and must never modify it.

Public API (everything a Runtime-layer or Plugin-layer module is allowed
to import from src.core):
"""

from src.core.events import Event, EventBus
from src.core.kernel import Kernel, KernelBootError
from src.core.lifecycle import Service, ServiceState
from src.core.registry import CapabilityNotFoundError, DuplicateServiceError
from src.core.tasks import Task, TaskState

__all__ = [
    "Kernel",
    "KernelBootError",
    "Service",
    "ServiceState",
    "Event",
    "EventBus",
    "Task",
    "TaskState",
    "CapabilityNotFoundError",
    "DuplicateServiceError",
]
