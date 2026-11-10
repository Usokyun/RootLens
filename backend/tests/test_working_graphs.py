"""Working-graph activation, isolation and integration against explicitly selected test DBs."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_visual_profile_reasoning import evidence_for, linear_mask, visual_graph

from kgtracevis.kg.graph import KnowledgeGraph
from kgtracevis.kg.visual_profile_compiler import compile_visual_profiles
from kgtracevis.service import working_graphs as service
from kgtracevis.service.api import app


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def create(self, record):
        assert record.graph_id not in self.rows
        self.rows[record.graph_id] = record.model_copy(deep=True)

    def update(self, record):
        self.rows[record.graph_id] = record.model_copy(deep=True)

    def get(self, graph_id):
        return self.rows[graph_id].model_copy(deep=True)

    def list_ready(self):
        return [r for r in self.rows.values() if r.status == "ready"]


def write_build(tmp_path: Path, monkeypatch, graph=None):
    import csv
    from dataclasses import asdict

    graph = graph or visual_graph()
    node_path, edge_path, profile_path = [
        tmp_path / p for p in ("nodes.csv", "edges.csv", "profiles.json")
    ]
    nodes = [{**asdict(n), "aliases": "|".join(n.aliases)} for n in graph.nodes.values()]
    edges = [e.model_dump() for e in graph.edges]
    for path, rows in ((node_path, nodes), (edge_path, edges)):
        with path.open("w") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    profile_path.write_text(
        json.dumps({"visual_runtime": compile_visual_profiles(graph).model_dump()})
    )
    paths = {"nodes": node_path, "edges": edge_path, "domain_profiles": profile_path}
    monkeypatch.setattr(
        service, "get_kg_construction_build_artifact_path", lambda _, key: paths[key]
    )
    return graph


def test_activation_never_reports_ready_after_failed_graph_write(tmp_path, monkeypatch):
    write_build(tmp_path, monkeypatch)
    store = MemoryStore()

    class FailedRepository:
        def write_new(self, graph):
            assert isinstance(graph, KnowledgeGraph)
            raise RuntimeError("injected storage failure")

        def close(self):
            pass

    with pytest.raises(RuntimeError, match="injected"):
        service.activate_compiler_build(
            "fixture",
            service.ActivateWorkingGraphRequest(),
            store=store,
            repository_factory=lambda _: FailedRepository(),
        )
    record = next(iter(store.rows.values()))
    assert record.status == "failed"
    assert store.list_ready() == []


def test_working_graph_list_and_incompatible_strategy_are_explicit(monkeypatch):
    from kgtracevis.workflows.root_cause_provider_selection import build_pipeline

    store = MemoryStore()
    service.configure_working_graph_store_for_testing(store)
    try:
        assert TestClient(app).get("/api/kg/working-graphs").json() == {"graphs": []}
        with pytest.raises(ValueError, match="visual profile"):
            build_pipeline(graph_id="new", reasoning_profile_id="generic_graph_path_default")
    finally:
        service.configure_working_graph_store_for_testing(None)


@pytest.mark.skipif(os.getenv("ROOTLENS_TEST_DATABASES") != "1", reason="isolated test DB opt-in")
def test_real_storage_roundtrip_and_legacy_graph_isolation(tmp_path, monkeypatch):
    """Uses only the separate compose.test.yaml databases, never configured application DBs."""
    from urllib.parse import urlparse

    import psycopg

    from kgtracevis.kg.import_neo4j import resolve_neo4j_config
    from kgtracevis.kg.neo4j_repository import Neo4jKGRepository
    from kgtracevis.kg.working_graph_repository import WorkingGraphRepository
    from kgtracevis.service.postgres import resolve_postgres_config
    from kgtracevis.service.runs import create_run_from_upload, get_run_detail
    from kgtracevis.workflows.root_cause_provider_selection import build_pipeline

    neo4j_config, pg_config = resolve_neo4j_config(), resolve_postgres_config()
    assert urlparse(neo4j_config.uri).port == 57687
    assert urlparse(pg_config.dsn).port == 55433
    assert urlparse(pg_config.dsn).path == "/rootlens_test"
    graph = write_build(tmp_path, monkeypatch)
    repository = Neo4jKGRepository.connect(neo4j_config)
    before = repository.to_knowledge_graph(scenario="mvtec")
    store = service.PostgresWorkingGraphStore(pg_config)
    records = []
    uploaded_run_ids = []
    shared_case_id = "storage_" + uuid.uuid4().hex
    try:
        for index in range(2):
            if index == 1:
                graph = KnowledgeGraph(
                    graph.nodes.values(),
                    [edge for edge in graph.edges if edge.tail != "MechanicalContact"],
                )
                write_build(tmp_path, monkeypatch, graph)
            record = service.activate_compiler_build(
                "fixture_" + uuid.uuid4().hex,
                service.ActivateWorkingGraphRequest(),
                store=store,
            )
            records.append(record)
            restored = store.get(record.graph_id)
            assert restored.status == "ready"
            scoped = WorkingGraphRepository.connect(record.graph_id)
            try:
                snapshot = scoped.to_knowledge_graph(scenario="mvtec")
            finally:
                scoped.close()
            assert set(snapshot.nodes) == set(graph.nodes)
            assert [e.model_dump() for e in sorted(snapshot.edges, key=lambda e: e.edge_id)] == [
                e.model_dump() for e in sorted(graph.edges, key=lambda e: e.edge_id)
            ]
            result = build_pipeline(graph_id=record.graph_id).analyze(evidence_for(linear_mask()))
            assert result.ranked_root_causes
            assert len(result.ranked_root_causes) == (2 if index == 0 else 1)
            assert result.reasoning_metadata["graph_id"] == record.graph_id
            uploaded = create_run_from_upload(
                "regions.jsonl",
                json.dumps(
                    {
                        "case_id": shared_case_id,
                        "severity": (len(uploaded_run_ids) + 1) / 10,
                        "object": "metal_nut",
                        "predicted_mask": linear_mask().tolist(),
                    }
                ).encode(),
                mode="records",
                dataset="mvtec",
                top_k=5,
                graph_id=record.graph_id,
                runs_dir=tmp_path / "uploads",
            )
            uploaded_run_ids.append(uploaded.run.run_id)
            with psycopg.connect(pg_config.dsn) as connection:
                connection.execute(
                    "UPDATE run_evidence_cases SET generated_evidence_path = %s WHERE run_id = %s",
                    (str(tmp_path / "unavailable-evidence.json"), uploaded.run.run_id),
                )
            restored_run = get_run_detail(uploaded.run.run_id)
            for key in (
                "linked_entities",
                "reasoning_metadata",
                "top_k_paths",
                "ranked_root_causes",
                "generated_evidence",
            ):
                assert uploaded.cases[0][key] == restored_run.cases[0][key], key
            assert all(link.get("obs_id") for link in restored_run.linked_entities)
        # Two graph runs of the same case retain their own complete input snapshot.
        for index, run_id in enumerate(uploaded_run_ids):
            restored_run = get_run_detail(run_id)
            assert restored_run.cases[0]["generated_evidence"]["severity"] == (index + 1) / 10
        after = repository.to_knowledge_graph(scenario="mvtec")
        assert len(before.nodes) == len(after.nodes)
        assert len(before.edges) == len(after.edges)
    finally:
        # Delete only IDs created by this test, leaving all seeds and other graphs intact.
        with psycopg.connect(pg_config.dsn) as connection:
            for run_id in uploaded_run_ids:
                connection.execute("DELETE FROM analysis_runs WHERE run_id = %s", (run_id,))
        for record in records:
            with repository.driver.session(database=neo4j_config.database) as session:
                session.run(
                    "MATCH (n:KGEntity {graph_id: $id}) DETACH DELETE n",
                    {"id": record.graph_id},
                ).consume()
            with psycopg.connect(pg_config.dsn) as connection:
                connection.execute(
                    "DELETE FROM working_graphs WHERE graph_id = %s", (record.graph_id,)
                )
        repository.close()
