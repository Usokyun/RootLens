"""Tests for runtime KG edit service helpers."""

from __future__ import annotations

import pytest

from kgtracevis.kg.graph import KGEdge, KGNode
from kgtracevis.service.kg_runtime_edit import (
    RuntimeKGEdgeConfidenceRequest,
    RuntimeKGEdgeRequest,
    RuntimeKGNodeRequest,
    delete_runtime_kg_edge,
    delete_runtime_kg_node,
    update_runtime_kg_edge_confidence,
    upsert_runtime_kg_edge,
    upsert_runtime_kg_node,
)


class FakeRuntimeKGRepository:
    """In-memory test double for writable Neo4j edit calls."""

    def __init__(self) -> None:
        self.nodes: dict[str, KGNode] = {}
        self.edges: dict[str, KGEdge] = {}

    def upsert_node(self, node: KGNode) -> KGNode:
        self.nodes[node.id] = node
        return node

    def delete_node(self, node_id: str) -> dict[str, int]:
        if node_id not in self.nodes:
            return {"deleted_node_count": 0, "deleted_relationship_count": 0}
        del self.nodes[node_id]
        incident_edge_ids = [
            edge_id
            for edge_id, edge in self.edges.items()
            if edge.head == node_id or edge.tail == node_id
        ]
        for edge_id in incident_edge_ids:
            del self.edges[edge_id]
        return {
            "deleted_node_count": 1,
            "deleted_relationship_count": len(incident_edge_ids),
        }

    def upsert_edge(self, edge: KGEdge) -> KGEdge:
        self.edges[edge.edge_id] = edge
        return edge

    def update_edge_confidence(self, edge_id: str, confidence: float) -> KGEdge:
        edge = self.edges.get(edge_id)
        if edge is None:
            raise ValueError(f"unknown KG edge: {edge_id}")
        updated = KGEdge(
            **{
                **edge.__dict__,
                "confidence": confidence,
                "weight": round(1.0 - confidence, 6),
            }
        )
        self.edges[edge_id] = updated
        return updated

    def delete_edge(self, edge_id: str) -> dict[str, int]:
        if edge_id not in self.edges:
            return {"deleted_edge_count": 0}
        del self.edges[edge_id]
        return {"deleted_edge_count": 1}


def test_upsert_node_records_runtime_node_payload() -> None:
    """Node edits should round-trip through the service DTOs."""
    repository = FakeRuntimeKGRepository()

    response = upsert_runtime_kg_node(
        RuntimeKGNodeRequest(
            id="ManualConcept",
            name="Manual concept",
            label="Concept",
            scenario="shared",
            aliases=["manual", " operator  edit "],
            description="operator curated",
        ),
        repository=repository,
    )

    assert response.status == "upserted"
    assert response.node["aliases"] == ["manual", "operator edit"]
    assert repository.nodes["ManualConcept"].scenario == "shared"


def test_upsert_edge_derives_weight_and_requires_source_evidence() -> None:
    """Edge edits should enforce source-constrained KG fields."""
    repository = FakeRuntimeKGRepository()

    response = upsert_runtime_kg_edge(
        RuntimeKGEdgeRequest(
            head="ManualConcept",
            relation="related_to",
            tail="ManualTarget",
            scenario="mvtec",
            source="manual_api",
            evidence="operator supplied relation",
            confidence=0.7,
        ),
        repository=repository,
    )

    assert response.edge["relation"] == "RELATED_TO"
    assert response.edge["weight"] == 0.3
    with pytest.raises(ValueError, match="source must not be empty"):
        RuntimeKGEdgeRequest(
            head="ManualConcept",
            relation="RELATED_TO",
            tail="ManualTarget",
            scenario="mvtec",
            source="",
            evidence="operator supplied relation",
            confidence=0.7,
        )


def test_update_edge_confidence_and_delete_helpers() -> None:
    """Confidence updates and deletes should expose stable affected counts."""
    repository = FakeRuntimeKGRepository()
    edge_request = RuntimeKGEdgeRequest(
        head="ManualConcept",
        relation="RELATED_TO",
        tail="ManualTarget",
        scenario="mvtec",
        source="manual_api",
        evidence="operator supplied relation",
        confidence=0.7,
    )
    edge = upsert_runtime_kg_edge(edge_request, repository=repository).edge

    updated = update_runtime_kg_edge_confidence(
        str(edge["edge_id"]),
        RuntimeKGEdgeConfidenceRequest(confidence=0.42),
        repository=repository,
    )
    deleted_edge = delete_runtime_kg_edge(str(edge["edge_id"]), repository=repository)
    delete_runtime_kg_node(
        RuntimeKGNodeRequest(
            id="ManualNode",
            name="Manual node",
            label="Concept",
            scenario="mvtec",
        ).id,
        repository=FakeRuntimeKGRepositoryWithNode(),
    )

    assert updated.edge["confidence"] == 0.42
    assert updated.edge["weight"] == 0.58
    assert deleted_edge.deleted_count == 1
    with pytest.raises(ValueError, match="unknown KG edge"):
        delete_runtime_kg_edge(str(edge["edge_id"]), repository=repository)


class FakeRuntimeKGRepositoryWithNode(FakeRuntimeKGRepository):
    """Fake repository seeded with one node."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes["ManualNode"] = KGNode(
            id="ManualNode",
            name="Manual node",
            label="Concept",
            scenario="mvtec",
            aliases=(),
        )
