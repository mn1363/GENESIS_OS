"""Shared base for the three foundation agents.

"Agents communicate through the Kernel Scheduler and Event Bus. The Kernel
remains the only orchestration point." (Phase 3 architecture decision.)
Concretely: agents never hold a reference to each other. Coordination
between them happens exclusively via (a) `kernel.submit_task()` — one
agent asking the Scheduler to admit work for another agent's capability —
and (b) publishing/subscribing on the Event Bus. No agent class in this
package imports another agent class.
"""

from __future__ import annotations


class AgentServiceBase:
    """Common `Service` protocol boilerplate. Subclasses add capability handlers."""

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def on_failure(self, error: BaseException) -> None:
        pass
