import os
from dataclasses import replace
from urllib.parse import urlparse

import pytest
from test_visual_profile_reasoning import evidence_for, linear_mask, visual_graph
from test_working_graphs import MemoryStore

from kgtracevis.kg.visual_profile_compiler import compile_visual_profiles
from kgtracevis.kg.working_graph_package import WorkingGraphPackage, graph_package
from kgtracevis.service import working_graph_editor as editor
from kgtracevis.service import working_graphs as service
from kgtracevis.workflows.root_cause_provider_selection import build_pipeline


@pytest.fixture
def setup_editor(monkeypatch, tmp_path):
    graph = visual_graph()
    graph.nodes["MetalNutObject"] = replace(graph.nodes["MetalNutObject"], aliases=("nut", "螺母"))
    snapshots = {"fixture": graph}
    store = MemoryStore()
    store.create(
        service.WorkingGraphRecord(
            graph_id="fixture",
            title="Editable",
            build_id="test",
            status="ready",
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            profiles=compile_visual_profiles(graph),
        )
    )

    class Repository:
        def __init__(self, graph_id):
            self.graph_id = graph_id

        def to_knowledge_graph(self, **_):
            return snapshots[self.graph_id]

        def replace(self, graph):
            snapshots[self.graph_id] = graph

        def write_new(self, graph):
            snapshots[self.graph_id] = graph

        def close(self):
            pass

    monkeypatch.setattr(editor.WorkingGraphRepository, "connect", Repository)
    monkeypatch.setattr(editor, "BACKUP_ROOT", tmp_path)
    service.configure_working_graph_store_for_testing(store)
    yield store, snapshots, tmp_path
    service.configure_working_graph_store_for_testing(None)


def test_complete_roundtrip_and_changed_knowledge_affects_new_runs(setup_editor):
    _, snapshots, backups = setup_editor
    package = editor.export_working_graph("fixture")
    restored = WorkingGraphPackage.model_validate_json(package.model_dump_json())
    assert restored == package
    imported = editor.import_working_graph(restored)
    assert imported.graph_id != "fixture"
    assert snapshots[imported.graph_id].nodes["MetalNutObject"].aliases == ("nut", "螺母")
    old_pipeline = build_pipeline(graph_id="fixture")
    before = old_pipeline.analyze(evidence_for(linear_mask()))
    edge_ids = [e.edge_id for e in snapshots["fixture"].edges if e.tail == "MechanicalContact"]
    editor.mutate_working_graph("fixture", editor.WorkingGraphMutation(delete_edge_ids=edge_ids))
    after = build_pipeline(graph_id="fixture").analyze(evidence_for(linear_mask()))
    assert len(after.ranked_root_causes) < len(before.ranked_root_causes)
    assert (
        old_pipeline.analyze(evidence_for(linear_mask())).ranked_root_causes
        == before.ranked_root_causes
    )
    assert old_pipeline.graph_snapshot == package.model_dump(mode="json")
    assert len(list(backups.glob("*.json"))) == 1


def test_custom_threshold_survives_node_edit_and_dependencies_reject(setup_editor):
    store, _, _ = setup_editor
    package = editor.export_working_graph("fixture")
    condition = (
        package.profiles.profiles[0]
        .conditions[0]
        .model_copy(
            update={
                "feature": "region.area_ratio",
                "op": "gte",
                "value": 0.04,
                "group": "geometry",
            }
        )
    )
    package.profiles.profiles[0].conditions.append(condition)
    editor.save_working_graph("fixture", package)
    node = package.nodes[0].model_copy(update={"description": "persistent edit"})
    editor.mutate_working_graph("fixture", editor.WorkingGraphMutation(upsert_nodes=[node]))
    assert any(
        c.feature == "region.area_ratio" and c.value == 0.04
        for c in store.get("fixture").profiles.profiles[0].conditions
    )
    with pytest.raises(ValueError, match="dependent edges"):
        editor.mutate_working_graph(
            "fixture", editor.WorkingGraphMutation(delete_node_ids=["MetalNutObject"])
        )
    malformed = package.model_dump(mode="json")
    malformed["edges"][0]["head"] = "missing"
    with pytest.raises(ValueError, match="dangling"):
        WorkingGraphPackage.model_validate(malformed)


def test_failed_registry_save_restores_graph_and_preserves_backup(setup_editor, monkeypatch):
    store, snapshots, backup = setup_editor
    old = snapshots["fixture"]
    original = store.update
    failed = False

    def update(record):
        nonlocal failed
        if record.status == "ready" and record.title == "new title" and not failed:
            failed = True
            raise RuntimeError("injected PG write failure")
        original(record)

    monkeypatch.setattr(store, "update", update)
    package = editor.export_working_graph("fixture").model_copy(update={"title": "new title"})
    with pytest.raises(RuntimeError, match="injected"):
        editor.save_working_graph("fixture", package)
    assert snapshots["fixture"].nodes == old.nodes
    assert store.get("fixture").status == "ready"
    assert store.get("fixture").title == "Editable"
    assert list(backup.glob("*.json"))


@pytest.mark.skipif(os.getenv("ROOTLENS_TEST_DATABASES") != "1", reason="isolated DB opt-in")
def test_real_persistent_edit_import_reanalysis_and_original_run(tmp_path, monkeypatch):
    import json

    import psycopg

    from kgtracevis.kg.working_graph_repository import WorkingGraphRepository
    from kgtracevis.service.postgres import resolve_postgres_config
    from kgtracevis.service.runs import create_run_from_upload, get_run_detail

    config = resolve_postgres_config()
    assert urlparse(config.dsn).port == 55433
    monkeypatch.setattr(editor, "BACKUP_ROOT", tmp_path / "backups")
    graph = visual_graph()
    package = graph_package(
        graph,
        graph_id="source",
        title="Editor integration",
        build_id="test",
        profiles=compile_visual_profiles(graph),
    )
    graphs = []
    run = None
    try:
        gid = editor.import_working_graph(package).graph_id
        graphs.append(gid)
        run = create_run_from_upload(
            "mask.jsonl",
            json.dumps(
                {
                    "case_id": "editor-real",
                    "object": "metal_nut",
                    "predicted_mask": linear_mask().tolist(),
                }
            ).encode(),
            mode="records",
            dataset="mvtec",
            top_k=5,
            graph_id=gid,
            runs_dir=tmp_path / "runs",
        )
        assert run.ranked_root_causes
        original_snapshot = run.summary["working_graph_snapshot"]
        exported = editor.export_working_graph(gid).model_dump(mode="json")
        exported["nodes"][0]["aliases"].append("持久别名")
        for p in exported["profiles"]["profiles"]:
            p["conditions"].append(
                {"feature": "region.area_ratio", "op": "gte", "value": 0.99, "required": True}
            )
        edited = WorkingGraphPackage.model_validate(exported)
        assert editor.save_working_graph(gid, edited).status == "ready"
        reread = editor.export_working_graph(gid)
        assert reread == edited
        assert (
            build_pipeline(graph_id=gid).analyze(evidence_for(linear_mask())).ranked_root_causes
            == []
        )
        assert get_run_detail(run.run.run_id).ranked_root_causes == run.ranked_root_causes
        assert get_run_detail(run.run.run_id).summary["working_graph_snapshot"] == original_snapshot
        gid2 = editor.import_working_graph(reread).graph_id
        graphs.append(gid2)
        assert (
            build_pipeline(graph_id=gid2).analyze(evidence_for(linear_mask())).ranked_root_causes
            == []
        )
    finally:
        # Only identities created by this test are removed; no seeds/reinitialization.
        for gid in graphs:
            repository = WorkingGraphRepository.connect(gid)
            with repository.repository.driver.session(
                database=repository.repository.config.database
            ) as session:
                session.run("MATCH (n:KGEntity {graph_id:$id}) DETACH DELETE n", id=gid).consume()
            repository.close()
        with psycopg.connect(config.dsn) as connection:
            for gid in graphs:
                connection.execute("DELETE FROM working_graphs WHERE graph_id=%s", (gid,))
            if run:
                connection.execute("DELETE FROM analysis_runs WHERE run_id=%s", (run.run.run_id,))
