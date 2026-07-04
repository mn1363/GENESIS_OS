"""Event-routing decorator for `BasePlugin` subclasses.

Lets a plugin author write one method per event instead of a single
`handle_event` with an if/elif chain — `BasePlugin.handle_event` looks up
the decorated method for the incoming `Event.name` and calls it directly.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

_EVENT_NAME_ATTR = "_genesis_event_name"

F = TypeVar("F", bound=Callable[..., Awaitable[None]])


def on_event(event_name: str) -> Callable[[F], F]:
    """Mark a `BasePlugin` method as the handler for `event_name`.

    Usage::

        class MyPlugin(BasePlugin):
            @on_event("task.completed")
            async def handle_task_completed(self, event, publish):
                ...
    """

    def decorator(func: F) -> F:
        setattr(func, _EVENT_NAME_ATTR, event_name)
        return func

    return decorator


def event_name_of(handler: Callable[..., Any]) -> str | None:
    """Return the event name `@on_event` attached to `handler`, if any."""
    return cast(str | None, getattr(handler, _EVENT_NAME_ATTR, None))
