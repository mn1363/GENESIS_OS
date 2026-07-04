"""Qdrant vector storage (Phase 4.2).

Production implementation of `src.services.memory.interfaces.VectorMemory`
(GEN-0026) — the Protocol Phase 3 explicitly called "the Qdrant
abstraction referred to in the Phase 3 decision." `MemoryService` and any
other caller depend on that Protocol, never on this class or on
`qdrant_client` directly, so `InMemoryVectorMemory` and
`QdrantVectorMemory` are interchangeable with no caller changes.
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.services.memory.interfaces import VectorMatch

# The VectorMemory Protocol's `id: str` is caller-chosen and arbitrary;
# Qdrant point IDs must be an unsigned int or a UUID. Deterministically
# derive a UUID5 from the caller's id and carry the original string in the
# payload so it can be recovered on `search()` — callers never see a UUID.
_ID_NAMESPACE = uuid.UUID("5f9b1b3a-1c2d-4e3f-9a8b-7c6d5e4f3a2b")
_ORIGINAL_ID_FIELD = "__genesis_original_id"


def _point_id(id: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, id))


class QdrantVectorMemory:
    """Production `VectorMemory` (GEN-0026), backed by Qdrant.

    The collection is created lazily on first `upsert`/`search`, once the
    vector dimension is known from the first vector written — Qdrant
    collections are dimension-fixed, and the Protocol has no explicit
    "configure dimension" step.
    """

    def __init__(
        self,
        client: AsyncQdrantClient,
        collection_name: str = "genesis_vector_memory",
        distance: Distance = Distance.COSINE,
    ) -> None:
        self._client = client
        self._collection_name = collection_name
        self._distance = distance
        self._collection_ready = False

    async def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_ready:
            return
        if not await self._client.collection_exists(self._collection_name):
            await self._client.create_collection(
                self._collection_name,
                vectors_config=VectorParams(size=vector_size, distance=self._distance),
            )
        self._collection_ready = True

    async def upsert(
        self, id: str, vector: list[float], metadata: dict[str, Any] | None = None
    ) -> None:
        await self._ensure_collection(len(vector))
        payload = {**(metadata or {}), _ORIGINAL_ID_FIELD: id}
        await self._client.upsert(
            self._collection_name,
            points=[PointStruct(id=_point_id(id), vector=vector, payload=payload)],
        )

    async def search(self, query_vector: list[float], top_k: int = 5) -> list[VectorMatch]:
        await self._ensure_collection(len(query_vector))
        result = await self._client.query_points(
            self._collection_name, query=query_vector, limit=top_k
        )
        return [
            VectorMatch(
                id=str((point.payload or {}).get(_ORIGINAL_ID_FIELD, point.id)),
                score=point.score,
                metadata={
                    k: v for k, v in (point.payload or {}).items() if k != _ORIGINAL_ID_FIELD
                },
            )
            for point in result.points
        ]

    async def delete(self, id: str) -> None:
        await self._client.delete(self._collection_name, points_selector=[_point_id(id)])
