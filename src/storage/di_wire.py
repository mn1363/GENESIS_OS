from .task_repository import TaskRepository
from .event_repository import EventRepository
from .memory_repository import MemoryRepository
from .repositories import RepositoryRegistry


def wire_storage(container) -> RepositoryRegistry:
    """
    Bind storage layer into DI container.
    """

    registry = RepositoryRegistry()

    registry.register("tasks", TaskRepository())
    registry.register("events", EventRepository())
    registry.register("memory", MemoryRepository())

    container.register("storage", registry)

    return registry