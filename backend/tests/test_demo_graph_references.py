"""Recommended examples must resolve exact installed knowledge, not the newest graph."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.service import two_loop_api as api
from kgtracevis.service.api import create_app
from kgtracevis.service.working_graphs import WorkingGraphStorageError


@pytest.fixture
def library(tmp_path, monkeypatch):
    package = UnifiedWorkingGraphPackage.model_validate_json(
        Path("data/demo/two_loop/knowledge/bottle-working-graph.v2.json").read_text()
    )
    original_id = package.knowledge.graph_id
    path = tmp_path / "paired-graph.json"
    path.write_text(package.model_dump_json())
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "demos": [
                    {
                        "id": "bottle",
                        "dataset": "mvtec",
                        "working_graph": {
                            "asset_id": "paired-graph",
                            "path": path.name,
                            "media_type": "application/json",
                        },
                        "materials": [],
                        "samples": [{"sample_id": "sample", "dataset": "mvtec"}],
                    }
                ]
            }
        )
    )
    records = []
    monkeypatch.setattr(api, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(api, "DEMO_MANIFEST", manifest)
    monkeypatch.setattr(
        api, "working_graph_store", lambda: SimpleNamespace(list_ready=lambda: records)
    )
    return TestClient(create_app()), records, package, path, original_id


def record(package, identity, *, enabled=True, changed=False):
    knowledge = package.knowledge.model_copy(deep=True, update={"graph_id": identity})
    if changed:
        knowledge.hypotheses[0].assumption_cost += 1.0
    return SimpleNamespace(
        graph_id=identity,
        title="图 " + identity,
        dataset=package.dataset,
        status="ready",
        enabled=enabled,
        knowledge=knowledge,
    )


def references(client):
    response = client.get("/api/demo-library")
    assert response.status_code == 200, response.text
    value = response.json()
    group = value["demos"][0]["graph_ref"]
    assert value["demos"][0]["samples"][0]["graph_ref"] == group
    assert value["samples"][0]["graph_ref"] == group
    return group


def test_paired_graph_wins_over_latest_enabled_source_and_unmodified_clone(library):
    client, records, package, _, original_id = library
    records.extend(
        [
            record(package, "latest-strict-source", changed=True),
            record(package, "audit-clone"),
            record(package, original_id),
        ]
    )
    ref = references(client)
    assert ref["state"] == "ready" and ref["available"] is True
    assert ref["graph_id"] == original_id
    assert "latest-strict-source" not in {r["graph_id"] for r in ref["candidates"]}
    assert ref["download_url"] == "/api/demo-library/assets/paired-graph"


def test_modified_original_identity_is_not_a_content_match(library):
    client, records, package, _, original_id = library
    records.extend([record(package, original_id, changed=True), record(package, "exact-copy")])
    ref = references(client)
    assert ref["graph_id"] == "exact-copy" and ref["available"]
    assert len(ref["candidates"]) == 1


def test_disabled_original_is_explicit_not_bypassed_by_another_clone(library):
    client, records, package, _, original_id = library
    records.extend([record(package, original_id, enabled=False), record(package, "clone")])
    ref = references(client)
    assert ref["state"] == "disabled" and ref["graph_id"] == original_id
    assert ref["ready"] is True and ref["enabled"] is False and ref["available"] is False


def test_missing_and_ambiguous_never_choose_by_scenario_or_recency(library):
    client, records, package, _, _ = library
    records.append(record(package, "same-scenario-but-different", changed=True))
    ref = references(client)
    assert ref["state"] == "missing" and ref["graph_id"] is None
    records[:] = [record(package, "copy-a"), record(package, "copy-b")]
    ref = references(client)
    assert ref["state"] == "ambiguous" and ref["available"] is False
    assert ref["graph_id"] is None and len(ref["candidates"]) == 2


def test_unique_enabled_match_is_usable_but_content_edits_are_not_ignored(library):
    client, records, package, _, _ = library
    records.extend([record(package, "only-enabled"), record(package, "disabled", enabled=False)])
    assert references(client)["graph_id"] == "only-enabled"
    records[0].knowledge.entities[0].aliases.append("edited-binding-alias")
    ref = references(client)
    assert ref["state"] == "disabled" and ref["graph_id"] == "disabled"


def test_missing_asset_and_registry_failure_are_unavailable_without_import(library, monkeypatch):
    client, _, _, path, _ = library

    def unavailable():
        raise WorkingGraphStorageError("unavailable test registry")

    monkeypatch.setattr(api, "working_graph_store", lambda: SimpleNamespace(list_ready=unavailable))
    ref = references(client)
    assert ref["state"] == "unavailable" and not ref["available"]
    assert "目录" in ref["note"]
    # Downloads remain a pure whitelist lookup even when the graph registry is down.
    response = client.get("/api/demo-library/assets/paired-graph")
    assert response.status_code == 200 and response.content == path.read_bytes()
    path.unlink()
    missing = references(client)
    assert missing["state"] == "unavailable" and missing["download_url"] is None
