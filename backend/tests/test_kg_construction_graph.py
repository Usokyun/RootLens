"""Explicit build previews stay isolated from Neo4j and analysis results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kgtracevis.service import kg_construction, kg_studio
from kgtracevis.service.api import app


@pytest.fixture
def build_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def reject_runtime(*args: object, **kwargs: object) -> None:
        pytest.fail("construction preview must not connect to Neo4j")

    monkeypatch.setattr(kg_studio.Neo4jKGRepository, "connect", reject_runtime)
    monkeypatch.setattr(kg_construction, "DEFAULT_SOURCE_KG_BUILD_DIR", tmp_path)
    monkeypatch.setattr(kg_construction, "LEGACY_SOURCE_KG_BUILD_DIR", tmp_path)
    for build_id in ("mvtec_snapshot", "another_build"):
        directory = tmp_path / build_id
        directory.mkdir()
        nodes = [
            {
                "id": name,
                "name": f"{build_id} {name}",
                "label": "RootCause",
                "scenario": "mvtec",
                "aliases": "",
                "description": "candidate only",
            }
            for name in ("Scratch", "Contact", "Isolated")
        ]
        edges = [
            {
                "head": "Scratch",
                "relation": "HAS_PLAUSIBLE_CAUSE",
                "tail": "Contact",
                "scenario": "mvtec",
                "source": "manual_curation",
                "evidence": "plausible mechanism, not truth",
                "confidence": "0.66",
                "weight": "0.3",
                "review_status": "auto",
                "feedback_count": "0",
                "accepted_count": "0",
                "rejected_count": "0",
            }
        ]
        for name, rows in (("nodes", nodes), ("edges", edges)):
            with (directory / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        (directory / "kg_construction_manifest.json").write_text(
            json.dumps({"run": {"run_id": build_id}})
        )
        # Deliberately stale summary counts must not override actual graph counts.
        (directory / "kg_construction_summary.json").write_text(
            json.dumps({"run_id": build_id, "node_count": 99, "title": "MVTec fixture"})
        )
    return tmp_path


def test_requested_build_includes_isolated_nodes_and_preserves_provenance(build_root: Path) -> None:
    before = {p: p.read_bytes() for p in build_root.rglob("*") if p.is_file()}
    result = kg_studio.construction_kg_studio_payload("mvtec_snapshot", build_root=build_root)
    assert result.build_id == "mvtec_snapshot"
    assert result.title == "MVTec fixture"
    assert result.graph_origin == "candidate_artifacts"
    assert result.read_only and not result.truncated
    assert (result.node_count, result.edge_count) == (3, 1)
    assert {node.node_id for node in result.graph_nodes} == {"Scratch", "Contact", "Isolated"}
    assert all(node.label.startswith("mvtec_snapshot") for node in result.graph_nodes)
    edge = result.graph_edges[0]
    assert edge.edge_id == "Scratch|HAS_PLAUSIBLE_CAUSE|Contact|mvtec"
    assert (edge.source, edge.evidence, edge.confidence, edge.review_status) == (
        "manual_curation",
        "plausible mechanism, not truth",
        0.66,
        "auto",
    )
    assert result.review_targets == []
    assert "ranked_root_causes" not in result.model_dump()
    assert before == {p: p.read_bytes() for p in build_root.rglob("*") if p.is_file()}


def test_limits_are_explicit_and_never_leave_dangling_edges(build_root: Path) -> None:
    result = kg_studio.construction_kg_studio_payload(
        "mvtec_snapshot", build_root=build_root, graph_node_limit=1
    )
    assert result.truncated
    assert (result.node_count, result.edge_count) == (3, 1)
    assert len(result.graph_nodes) == 1 and result.graph_edges == []
    result = kg_studio.construction_kg_studio_payload(
        "mvtec_snapshot", build_root=build_root, graph_edge_limit=0
    )
    assert len(result.graph_nodes) == 3 and result.graph_edges == [] and result.truncated


def test_api_returns_only_the_selected_build(build_root: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/api/kg/construction/builds/mvtec_snapshot/graph")
    assert response.status_code == 200
    payload = response.json()
    assert payload["build_id"] == "mvtec_snapshot"
    assert payload["read_only"] is True
    assert len(payload["graph_nodes"]) == 3
    assert payload["graph_edges"][0]["source"] == "manual_curation"


@pytest.mark.parametrize("build_id", ["unknown", "mvtec_snapshot"])
def test_missing_build_or_files_returns_404_without_fallback(
    build_root: Path, build_id: str
) -> None:
    if build_id == "mvtec_snapshot":
        (build_root / build_id / "nodes.csv").unlink()
    with TestClient(app) as client:
        response = client.get(f"/api/kg/construction/builds/{build_id}/graph")
    assert response.status_code == 404
    assert "graph_nodes" not in response.json()


def test_malformed_graph_returns_400_without_runtime_substitution(build_root: Path) -> None:
    path = build_root / "mvtec_snapshot" / "edges.csv"
    path.write_text(path.read_text().replace("Contact,", "AbsentNode,"))
    with TestClient(app) as client:
        response = client.get("/api/kg/construction/builds/mvtec_snapshot/graph")
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]
