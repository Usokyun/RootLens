"""Runtime KG Studio reads use Neo4j and preserve bounded, traceable previews."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import AuthError, ServiceUnavailable

from kgtracevis.kg.graph import KGEdge, KGNode, KnowledgeGraph
from kgtracevis.kg.import_neo4j import Neo4jConfig
from kgtracevis.service import kg_studio
from kgtracevis.service.api import create_app


class SnapshotRepository:
    """Small repository double; never used by the running application."""

    def __init__(self, graph: KnowledgeGraph, *, fail: bool = False) -> None:
        self.graph = graph
        self.fail = fail
        self.scenarios: list[str | None] = []
        self.closed = False

    def to_knowledge_graph(self, *, scenario: str | None = None) -> KnowledgeGraph:
        self.scenarios.append(scenario)
        if self.fail:
            raise ServiceUnavailable("database unavailable")
        return self.graph

    def close(self) -> None:
        self.closed = True


def _snapshot() -> KnowledgeGraph:
    nodes = []
    edges = []
    for scenario in ("mvtec", "shared", "tep", "wafer"):
        tail = f"{scenario}Effect"
        nodes.append(KGNode(tail, "Observed effect", "AnomalyType", scenario, ()))
        for index in range(21):
            head = f"{scenario}Cause{index:02}"
            nodes.append(KGNode(head, "Possible cause", "RootCause", scenario, ()))
            edges.append(
                KGEdge(
                    head=head,
                    relation="SUGGESTS_PLAUSIBLE_MECHANISM",
                    tail=tail,
                    scenario=scenario,
                    source=f"source_{scenario}",
                    evidence=f"source text {scenario} {index}",
                    confidence=0.6,
                    weight=0.4,
                    review_status="auto",
                    feedback_count=0,
                    accepted_count=0,
                    rejected_count=0,
                )
            )
    return KnowledgeGraph(nodes, edges)


def _connect_repository(monkeypatch: pytest.MonkeyPatch, repository: SnapshotRepository) -> None:
    def connect(config: Neo4jConfig) -> SnapshotRepository:
        assert config.database
        return repository

    monkeypatch.setattr(kg_studio.Neo4jKGRepository, "connect", connect)


def _reject_artifact_lookup(*args: object) -> None:
    pytest.fail("runtime graph must not discover candidate artifacts")


def test_runtime_snapshot_preserves_totals_provenance_and_stable_preview(tmp_path: Path) -> None:
    """The limit bounds the preview, with full counts and every scenario retained."""
    graph = _snapshot()
    repository = SnapshotRepository(graph)
    payload = kg_studio.kg_studio_payload(
        repository=repository,
        source_registry_path=tmp_path / "no_registry.csv",
        source_docs_dir=tmp_path / "no_docs",
        graph_edge_limit=6,
    )

    assert repository.scenarios == [None]
    assert not repository.closed  # Injected repository ownership stays with the caller.
    assert payload.status == "ok"
    assert payload.graph_origin == "neo4j"
    assert payload.candidate_dir is payload.nodes_path is payload.edges_path is None
    assert payload.manifest_path is payload.summary_path is None
    assert payload.validation_summary is payload.construction_manifest is None
    assert payload.node_count == 88
    assert payload.edge_count == 84
    assert payload.scenario_counts == {
        scenario: 21 for scenario in ("mvtec", "shared", "tep", "wafer")
    }
    assert payload.review_status_counts == {"auto": 84}
    assert payload.source_counts == {
        f"source_{scenario}": 21 for scenario in payload.scenario_counts
    }
    assert payload.confidence_summary == {"count": 84, "min": 0.6, "mean": 0.6, "max": 0.6}
    assert len(payload.graph_edges) == 6
    assert {edge.scenario for edge in payload.graph_edges} == set(payload.scenario_counts)
    assert {node.node_id for node in payload.graph_nodes} == {
        node_id for edge in payload.graph_edges for node_id in (edge.head, edge.tail)
    }
    original_edges = {edge.edge_id: edge for edge in graph.edges}
    for edge, target in zip(payload.graph_edges, payload.review_targets, strict=True):
        original = original_edges[edge.edge_id]
        assert edge.target_key == f"edge:{original.edge_id}"
        assert edge.source == original.source
        assert edge.evidence == original.evidence
        assert edge.confidence == original.confidence
        assert edge.weight == original.weight
        assert edge.review_status == original.review_status
        assert target.target_id == original.edge_id
        assert target.target_key == edge.target_key

    reversed_repository = SnapshotRepository(
        KnowledgeGraph(graph.nodes.values(), reversed(graph.edges))
    )
    reloaded = kg_studio.kg_studio_payload(repository=reversed_repository, graph_edge_limit=6)
    assert reloaded.graph_edges == payload.graph_edges


def test_runtime_default_uses_owned_repository_without_artifact_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The maintained default connects to Neo4j and closes its own driver."""
    repository = SnapshotRepository(_snapshot())
    _connect_repository(monkeypatch, repository)
    monkeypatch.setattr(kg_studio, "_first_candidate_artifacts", _reject_artifact_lookup)
    payload = kg_studio.kg_studio_payload()
    assert payload.graph_origin == "neo4j"
    assert len(payload.graph_edges) == kg_studio.GRAPH_PREVIEW_EDGE_LIMIT
    assert repository.scenarios == [None]
    assert repository.closed


@pytest.mark.parametrize(
    "error", [ServiceUnavailable("offline"), AuthError("denied"), ValueError("config")]
)
def test_runtime_connection_failures_surface_as_503_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """Connection or authentication failure never returns CSV or an empty success."""

    def connect(config: Neo4jConfig) -> SnapshotRepository:
        raise error

    monkeypatch.setattr(kg_studio.Neo4jKGRepository, "connect", connect)
    monkeypatch.setattr(kg_studio, "_first_candidate_artifacts", _reject_artifact_lookup)
    response = TestClient(create_app()).get("/api/kg/studio")
    assert response.status_code == 503
    assert "runtime Neo4j graph" in response.json()["detail"]
    assert "graph_nodes" not in response.json()


def test_runtime_snapshot_failure_closes_owned_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """A query failure releases the driver and propagates the runtime error."""
    repository = SnapshotRepository(_snapshot(), fail=True)
    _connect_repository(monkeypatch, repository)
    monkeypatch.setattr(kg_studio, "_first_candidate_artifacts", _reject_artifact_lookup)
    with pytest.raises(kg_studio.KGStudioRuntimeError):
        kg_studio.kg_studio_payload()
    assert repository.closed


def test_runtime_empty_database_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuinely empty Neo4j snapshot is distinguishable from a failed connection."""
    repository = SnapshotRepository(KnowledgeGraph([], []))
    _connect_repository(monkeypatch, repository)
    response = TestClient(create_app()).get("/api/kg/studio")
    assert response.status_code == 200
    payload = response.json()
    assert payload["graph_origin"] == "neo4j"
    assert payload["status"] == "empty"
    assert payload["node_count"] == payload["edge_count"] == 0
    assert payload["graph_nodes"] == payload["graph_edges"] == payload["review_targets"] == []


@pytest.mark.parametrize("limit", [0, -1])
def test_runtime_nonpositive_preview_limit_keeps_full_counts(limit: int) -> None:
    """Disabling the preview leaves the runtime aggregate counts intact."""
    payload = kg_studio.kg_studio_payload(
        repository=SnapshotRepository(_snapshot()), graph_edge_limit=limit
    )
    assert payload.edge_count == 84
    assert payload.graph_nodes == payload.graph_edges == payload.review_targets == []


def test_complete_runtime_snapshot_retains_isolated_entities() -> None:
    graph = KnowledgeGraph([KGNode("isolated", "Independent concept", "Concept", "mvtec", ())], [])
    payload = kg_studio.kg_studio_payload(
        repository=SnapshotRepository(graph), graph_edge_limit=2000
    )
    assert [node.node_id for node in payload.graph_nodes] == ["isolated"]
    assert payload.graph_edges == []
