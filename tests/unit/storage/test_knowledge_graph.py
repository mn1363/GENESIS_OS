"""Unit tests for src/storage/knowledge_graph.py."""

from __future__ import annotations

import pytest
from src.services.memory.interfaces import GraphNode, KnowledgeGraph
from src.storage.database import DatabaseSessionManager
from src.storage.knowledge_graph import SQLAlchemyKnowledgeGraph


@pytest.fixture
async def graph() -> SQLAlchemyKnowledgeGraph:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    await manager.create_all()
    return SQLAlchemyKnowledgeGraph(manager)


async def test_add_node_returns_graph_node_with_labels_and_properties(
    graph: SQLAlchemyKnowledgeGraph,
) -> None:
    node = await graph.add_node("alice", labels=("person",), properties={"age": 30})

    assert node.id == "alice"
    assert node.labels == ("person",)
    assert node.properties == {"age": 30}


async def test_add_node_upserts_existing_node(graph: SQLAlchemyKnowledgeGraph) -> None:
    await graph.add_node("alice", labels=("person",), properties={"age": 30})
    await graph.add_node("alice", labels=("person", "engineer"), properties={"age": 31})

    await graph.add_node("carol")
    await graph.add_edge("carol", "alice", "knows")

    neighbors = await graph.neighbors("carol")

    assert neighbors == [
        GraphNode(id="alice", labels=("person", "engineer"), properties={"age": 31})
    ]


async def test_add_edge_returns_graph_edge(graph: SQLAlchemyKnowledgeGraph) -> None:
    await graph.add_node("alice")
    await graph.add_node("bob")

    edge = await graph.add_edge("alice", "bob", "knows", properties={"since": 2020})

    assert edge.source == "alice"
    assert edge.target == "bob"
    assert edge.relation == "knows"
    assert edge.properties == {"since": 2020}


async def test_neighbors_returns_connected_declared_nodes(
    graph: SQLAlchemyKnowledgeGraph,
) -> None:
    await graph.add_node("alice")
    await graph.add_node("bob")
    await graph.add_edge("alice", "bob", "knows")

    neighbors = await graph.neighbors("alice")

    assert [n.id for n in neighbors] == ["bob"]


async def test_neighbors_filters_by_relation(graph: SQLAlchemyKnowledgeGraph) -> None:
    await graph.add_node("alice")
    await graph.add_node("bob")
    await graph.add_node("carol")
    await graph.add_edge("alice", "bob", "knows")
    await graph.add_edge("alice", "carol", "blocks")

    knows = await graph.neighbors("alice", relation="knows")

    assert [n.id for n in knows] == ["bob"]


async def test_neighbors_excludes_edge_endpoints_never_declared_as_nodes(
    graph: SQLAlchemyKnowledgeGraph,
) -> None:
    """Matches InMemoryKnowledgeGraph: an edge to an id never passed to
    add_node() must not surface as a neighbor."""
    await graph.add_node("alice")
    await graph.add_edge("alice", "ghost", "knows")

    neighbors = await graph.neighbors("alice")

    assert neighbors == []


async def test_neighbors_of_unknown_node_returns_empty_list(
    graph: SQLAlchemyKnowledgeGraph,
) -> None:
    assert await graph.neighbors("missing") == []


async def test_neighbors_deduplicates_multiple_edges_to_the_same_target(
    graph: SQLAlchemyKnowledgeGraph,
) -> None:
    await graph.add_node("alice")
    await graph.add_node("bob")
    await graph.add_edge("alice", "bob", "knows")
    await graph.add_edge("alice", "bob", "likes")

    neighbors = await graph.neighbors("alice")

    assert [n.id for n in neighbors] == ["bob"]


async def test_neighbors_preserves_edge_insertion_order(
    graph: SQLAlchemyKnowledgeGraph,
) -> None:
    await graph.add_node("alice")
    await graph.add_node("bob")
    await graph.add_node("carol")
    await graph.add_edge("alice", "carol", "knows")
    await graph.add_edge("alice", "bob", "knows")

    neighbors = await graph.neighbors("alice")

    assert [n.id for n in neighbors] == ["carol", "bob"]


def test_sqlalchemy_knowledge_graph_satisfies_protocol() -> None:
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    assert isinstance(SQLAlchemyKnowledgeGraph(manager), KnowledgeGraph)
