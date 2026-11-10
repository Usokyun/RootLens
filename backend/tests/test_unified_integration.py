import json
import os
from pathlib import Path

import pytest
from test_working_graphs import MemoryStore

from kgtracevis.adapters.unified import evidence_frames
from kgtracevis.kg.unified_projection import runtime_projection, validate_runtime_projection
from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.schema.evidence_schema import Evidence, EvidenceObservation, RawEvidence
from kgtracevis.schema.unified_knowledge import KnowledgePackage
from kgtracevis.service import working_graph_editor as editor
from kgtracevis.service import working_graphs as service
from kgtracevis.workflows.root_cause_provider_selection import build_pipeline

DESIGN = Path(__file__).resolve().parents[2] / "src/doc/design-examples/unified-reasoning-v2"


@pytest.fixture
def package():
    data = json.loads((DESIGN / "knowledge-package.json").read_text())
    for binding in data["subject_bindings"]:
        if binding["namespace"] == "mvtec.object":
            binding["namespace"] = "industrial.object"
    return UnifiedWorkingGraphPackage(
        title="Common", dataset="mvtec", knowledge=KnowledgePackage.model_validate(data)
    )


def visual_evidence(*, normal=False, regions=1):
    return Evidence(
        case_id="input",
        dataset="mvtec",
        source="image",
        object="metal_nut",
        anomaly_type="unknown",
        raw_evidence=RawEvidence(
            extra={"detector": {"raw_pred_label": not normal}, "image_path": "public.png"}
        ),
        observations=[
            EvidenceObservation(
                obs_id=f"obs:{i}",
                facet="visual_region",
                name="ROI",
                value_type="visual_region.v1",
                value=dict(
                    region_id=f"roi{i}",
                    source="detector_mask",
                    coordinate_space="image",
                    image_shape=[100, 200],
                    bbox_xyxy=[10, 20, 160, 30],
                    eccentricity=0.98,
                    aspect_ratio=15.0,
                    area_ratio=0.03,
                    semantic_source="vlm:test",
                    semantic_status="predicted",
                    semantic_candidates=["scratch"],
                ),
            )
            for i in range(regions)
        ],
    )


@pytest.fixture
def storage(monkeypatch, tmp_path):
    store, graphs = MemoryStore(), {}

    class Repository:
        def __init__(self, graph_id):
            self.id = graph_id

        def to_knowledge_graph(self, **kwargs):
            return graphs[self.id]

        def write_new(self, graph):
            assert self.id not in graphs
            graphs[self.id] = graph

        def replace(self, graph):
            graphs[self.id] = graph

        def close(self):
            pass

    monkeypatch.setattr(editor.WorkingGraphRepository, "connect", Repository)
    monkeypatch.setattr(editor, "BACKUP_ROOT", tmp_path)
    service.configure_working_graph_store_for_testing(store)
    yield store, graphs, tmp_path
    service.configure_working_graph_store_for_testing(None)


def test_roi_adapter_preserves_scope_provenance_and_no_native_label():
    evidence = visual_evidence(regions=2)
    evidence.anomaly_type = "invented_cause"
    frames = evidence_frames(evidence)
    assert len(frames) == 2
    assert frames[0].scopes[0].bbox_xyxy == (10, 20, 160, 30)
    assert "invented_cause" not in frames[0].model_dump_json()
    assert all(f.procedures[-1].kind == "model_estimate" for f in frames)
    assert not any(
        o.feature_id == "appearance.foreign_material_present" for o in frames[0].observations
    )
    normal = evidence_frames(visual_evidence(normal=True, regions=0))[0]
    assert normal.scopes[0].kind == "event"
    assert normal.observations[0].value.boolean is False


def test_canonical_roundtrip_pipeline_edit_and_snapshot(package, storage):
    _, graphs, backups = storage
    record = editor.import_working_graph(package)
    assert record.knowledge.graph_id == record.graph_id
    exported = editor.export_working_graph(record.graph_id)
    assert UnifiedWorkingGraphPackage.model_validate_json(exported.model_dump_json()) == exported
    old_pipeline = build_pipeline(graph_id=record.graph_id)
    result = old_pipeline.analyze(visual_evidence())
    assert {r.candidate_id for r in result.ranked_root_causes} == {"h:contact", "h:wear"}
    assert result.reasoning_metadata["query_results"][0]["outcome"] == "ambiguous"
    assert all(p["support_obs_ids"] == ["obs:0"] for p in result.top_k_paths)
    assert all(
        edge.get("origin_edge_id", edge["edge_id"])
        in {e.edge_id for e in graphs[record.graph_id].edges}
        for p in result.top_k_paths
        for edge in p["source_edges"]
    )
    deletion = next(
        e.edge_id
        for e in graphs[record.graph_id].edges
        if e.external_edge_id == "r:contact_effect::from"
    )
    editor.mutate_working_graph(
        record.graph_id, editor.WorkingGraphMutation(delete_edge_ids=[deletion])
    )
    after = build_pipeline(graph_id=record.graph_id).analyze(visual_evidence())
    assert [r.candidate_id for r in after.ranked_root_causes] == ["h:wear"]
    assert old_pipeline.analyze(visual_evidence()).ranked_root_causes == result.ranked_root_causes
    assert len(list(backups.glob("*.json"))) == 1


def test_diverged_projection_rejected(package):
    graph = runtime_projection(package.knowledge, scenario="mvtec")
    graph.edges.pop()
    with pytest.raises(ValueError, match="diverged"):
        validate_runtime_projection(package.knowledge, graph, scenario="mvtec")


def test_api_typed_contract_and_export(package, storage):
    from fastapi.testclient import TestClient

    from kgtracevis.service.api import app

    client = TestClient(app)
    imported = client.post("/api/kg/working-graphs/import", json=package.model_dump(mode="json"))
    assert imported.status_code == 200, imported.text
    identity = imported.json()["graph_id"]
    frame = evidence_frames(visual_evidence())[0]
    result = client.post(f"/api/reasoning/{identity}/analyze", json=frame.model_dump(mode="json"))
    assert result.status_code == 200, result.text
    assert result.json()["outcome"] == "ambiguous"
    assert (
        client.get(f"/api/kg/working-graphs/{identity}/package").json()["knowledge"]["graph_id"]
        == identity
    )


def test_value_binding_save_reopen_changes_next_run_not_existing_snapshot(package, storage):
    from fastapi.testclient import TestClient

    from kgtracevis.service.api import app

    client = TestClient(app)
    imported = client.post("/api/kg/working-graphs/import", json=package.model_dump(mode="json"))
    assert imported.status_code == 200, imported.text
    identity = imported.json()["graph_id"]
    evidence = visual_evidence()
    evidence.observations[0].value["semantic_candidates"] = ["LegacyScratch"]
    old_pipeline = build_pipeline(graph_id=identity)
    assert not old_pipeline.analyze(evidence).ranked_root_causes
    exported = client.get(f"/api/kg/working-graphs/{identity}/package").json()
    exported["knowledge"]["value_bindings"] = [
        {
            "binding_id": "alias:legacy-scratch",
            "feature_id": "appearance.semantic_candidates",
            "external_value": "LegacyScratch",
            "canonical_value": "scratch",
            "procedure_model_id": "vlm:test",
            "source_assertion_ids": ["s:visual-design"],
        }
    ]
    saved = client.put(f"/api/kg/working-graphs/{identity}/package", json=exported)
    assert saved.status_code == 200, saved.text
    reread = client.get(f"/api/kg/working-graphs/{identity}/package").json()
    assert reread["knowledge"]["value_bindings"] == exported["knowledge"]["value_bindings"]
    next_pipeline = build_pipeline(graph_id=identity)
    result = next_pipeline.analyze(evidence)
    assert len(result.ranked_root_causes) == 2
    frame = evidence_frames(evidence)[0]
    native = client.post(f"/api/reasoning/{identity}/analyze", json=frame.model_dump(mode="json"))
    assert native.status_code == 200, native.text
    fact = next(f for f in native.json()["grounded_facts"] if f["predicate_id"] == "q:scratch_cue")
    assert fact["actual_values"][0]["items"] == ["LegacyScratch"]
    assert fact["applied_value_binding_ids"] == ["alias:legacy-scratch"]
    assert not old_pipeline.analyze(evidence).ranked_root_causes
    reread["knowledge"]["value_bindings"] = []
    assert client.put(f"/api/kg/working-graphs/{identity}/package", json=reread).status_code == 200
    assert not build_pipeline(graph_id=identity).analyze(evidence).ranked_root_causes
    assert len(next_pipeline.analyze(evidence).ranked_root_causes) == 2


@pytest.mark.skipif(os.getenv("ROOTLENS_TEST_DATABASES") != "1", reason="isolated DB opt-in")
def test_real_v2_registry_projection_save_and_reopen(package, tmp_path, monkeypatch):
    from urllib.parse import urlparse

    import psycopg

    from kgtracevis.kg.working_graph_repository import WorkingGraphRepository
    from kgtracevis.service.postgres import resolve_postgres_config

    config = resolve_postgres_config()
    assert urlparse(config.dsn).port == 55433
    monkeypatch.setattr(editor, "BACKUP_ROOT", tmp_path)
    ids = []
    try:
        record = editor.import_working_graph(package)
        ids.append(record.graph_id)
        # Each call opens independent PG/Neo4j connections, not an in-memory cache.
        old_pipeline = build_pipeline(graph_id=record.graph_id)
        before = old_pipeline.analyze(visual_evidence())
        assert len(before.ranked_root_causes) == 2
        restored = editor.export_working_graph(record.graph_id)
        restored.knowledge.effect_rules = [
            r for r in restored.knowledge.effect_rules if r.from_id != "h:contact"
        ]
        editor.save_working_graph(record.graph_id, restored)
        after = build_pipeline(graph_id=record.graph_id).analyze(visual_evidence())
        assert [r.candidate_id for r in after.ranked_root_causes] == ["h:wear"]
        reimport = editor.import_working_graph(editor.export_working_graph(record.graph_id))
        ids.append(reimport.graph_id)
        assert (
            len(
                build_pipeline(graph_id=reimport.graph_id)
                .analyze(visual_evidence())
                .ranked_root_causes
            )
            == 1
        )
        assert len(old_pipeline.analyze(visual_evidence()).ranked_root_causes) == 2
    finally:
        for identity in ids:
            repo = WorkingGraphRepository.connect(identity)
            try:
                with repo.repository.driver.session(
                    database=repo.repository.config.database
                ) as session:
                    session.run(
                        "MATCH (n:KGEntity {graph_id: $graph_id}) DETACH DELETE n",
                        graph_id=identity,
                    ).consume()
            finally:
                repo.close()
            with psycopg.connect(config.dsn) as connection:
                connection.execute("DELETE FROM working_graphs WHERE graph_id = %s", (identity,))
