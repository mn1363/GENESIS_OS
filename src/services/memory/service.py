"""Memory Service — registers Short-Term/Vector/Knowledge-Graph capabilities.

Implements the `Service` protocol so it can be registered with the Kernel
via `kernel.register_service()`; the capability handlers below are what
`kernel.dispatch("memory.*@v1", ...)` resolves to.
"""

from __future__ import annotations

from typing import Any

from src.services.memory.in_memory import (
    InMemoryKnowledgeGraph,
    InMemoryShortTermMemory,
    InMemoryVectorMemory,
)
from src.services.memory.interfaces import KnowledgeGraph, ShortTermMemory, VectorMemory


class MemoryService:
    """Composite Hybrid Memory service.

    Depends only on the three Protocols (interfaces.py), not on the
    in-memory implementations — production backends can be substituted by
    passing different instances at construction, with no change to this
    class or to any capability handler signature.
    """

    def __init__(
        self,
        short_term: ShortTermMemory | None = None,
        vector: VectorMemory | None = None,
        graph: KnowledgeGraph | None = None,
    ) -> None:
        self.short_term: ShortTermMemory = short_term or InMemoryShortTermMemory()
        self.vector: VectorMemory = vector or InMemoryVectorMemory()
        self.graph: KnowledgeGraph = graph or InMemoryKnowledgeGraph()

    # ---- Service protocol ---------------------------------------------------------

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def health_check(self) -> bool:
        """Genuinely probes `short_term` and `graph` through their own
        Protocol methods — a session/key and a `node_id` that don't
        exist, which both return an empty/`None` result if the backend is
        reachable and raise if it isn't. A Redis or database outage now
        correctly surfaces as an unhealthy `Service` to the Kernel's
        `boot()` sequence (`KERNEL_ARCHITECTURE_PROPOSAL.md` §6) instead
        of the previous unconditional `return True`.

        Deliberately does **not** actively probe `vector`: every
        `VectorMemory` method that could serve as a probe has a real
        side-effect risk. `upsert`/`search` both lazily create the
        backing collection sized to whatever vector they're first called
        with (`QdrantVectorMemory._ensure_collection`) — probing with
        either would permanently lock in a throwaway dimension before any
        real data exists, corrupting real usage later. `delete` avoids
        that, but raises for a collection that doesn't exist yet, which
        would make a freshly wired, perfectly healthy vector store report
        as unhealthy on first boot. There is no way to safely probe
        reachability through this Protocol alone, so `vector` is left
        unchecked here rather than risk either failure mode.
        """
        try:
            await self.short_term.get("__health_check__", "__health_check__")
            await self.graph.neighbors("__health_check__")
        except Exception:  # noqa: BLE001 - any backend failure means "unhealthy", not a crash
            return False
        return True

    async def on_failure(self, error: BaseException) -> None:
        pass

    # ---- Capability handlers (registered under these names in Kernel.register_service) --

    async def short_term_get(self, payload: dict[str, Any]) -> Any | None:
        return await self.short_term.get(payload["session_id"], payload["key"])

    async def short_term_set(self, payload: dict[str, Any]) -> None:
        await self.short_term.set(payload["session_id"], payload["key"], payload["value"])

    async def vector_upsert(self, payload: dict[str, Any]) -> None:
        await self.vector.upsert(payload["id"], payload["vector"], payload.get("metadata"))

    async def vector_search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        matches = await self.vector.search(payload["query_vector"], payload.get("top_k", 5))
        return [{"id": m.id, "score": m.score, "metadata": m.metadata} for m in matches]

    async def graph_add_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        node = await self.graph.add_node(
            payload["id"], tuple(payload.get("labels", ())), payload.get("properties")
        )
        return {"id": node.id, "labels": node.labels, "properties": node.properties}

    async def graph_add_edge(self, payload: dict[str, Any]) -> dict[str, Any]:
        edge = await self.graph.add_edge(
            payload["source"], payload["target"], payload["relation"], payload.get("properties")
        )
        return {"source": edge.source, "target": edge.target, "relation": edge.relation}

    async def graph_neighbors(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = await self.graph.neighbors(payload["node_id"], payload.get("relation"))
        return [{"id": n.id, "labels": n.labels, "properties": n.properties} for n in nodes]

    def capability_handlers(self) -> dict[str, Any]:
        """Convenience for callers wiring this into Kernel.register_service()."""
        return {
            "memory.short_term.get@v1": self.short_term_get,
            "memory.short_term.set@v1": self.short_term_set,
            "memory.vector.upsert@v1": self.vector_upsert,
            "memory.vector.search@v1": self.vector_search,
            "memory.graph.add_node@v1": self.graph_add_node,
            "memory.graph.add_edge@v1": self.graph_add_edge,
            "memory.graph.neighbors@v1": self.graph_neighbors,
        }
