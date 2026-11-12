"""Read-only/isolated tests for demo visuals, source resolution and advisory drafts."""

from __future__ import annotations

import csv
import json
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from kgtracevis.demo_assets import generate_visual_fixtures
from kgtracevis.service.api import create_app
from kgtracevis.service.graph_workspace import GraphWorkspacePatch
from kgtracevis.service.kg_drafts import (
    KGDraftListRequest,
    KGDraftRequest,
    list_kg_drafts,
    record_kg_draft,
)
from kgtracevis.service.postgres import PostgresConfig
from kgtracevis.service.postgres_graph_drafts import OPERATION, PostgresGraphDraftStore
from kgtracevis.service.source_provenance import get_registered_source


def patch() -> dict:
    return {
        "version": 1,
        "scope": "demo|mvtec-project",
        "changes": [
            {
                "kind": "node",
                "operation": "upsert",
                "id": "scratch",
                "before": None,
                "after": {"id": "scratch", "name": "Scratch", "kind": "Defect"},
                "source": "manual_curation",
                "evidence": "linear defect",
                "note": "Fix label",
            }
        ],
    }


def request() -> KGDraftRequest:
    return KGDraftRequest(
        target_type="graph_workspace",
        target_id="mvtec-project",
        target_key="editor:demo|mvtec-project",
        draft_action="revise",
        source="rootlens-editor",
        metadata={"dataset": "mvtec", "editor_patch": patch()},
    )


def test_graph_patch_requires_provenance_identity_and_unique_changes() -> None:
    assert GraphWorkspacePatch.model_validate(patch()).changes[0].source == "manual_curation"
    for field in ("source", "evidence", "note"):
        invalid = patch()
        invalid["changes"][0][field] = " "
        with pytest.raises(ValidationError):
            GraphWorkspacePatch.model_validate(invalid)
    duplicate = patch()
    duplicate["changes"] *= 2
    with pytest.raises(ValidationError, match="one net change"):
        GraphWorkspacePatch.model_validate(duplicate)
    with pytest.raises(ValidationError, match="scope"):
        KGDraftRequest.model_validate({**request().model_dump(), "target_key": "editor:other"})


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), True])
def test_graph_patch_rejects_invalid_relation_confidence(confidence: object) -> None:
    invalid = patch()
    invalid["changes"][0].update(
        kind="edge",
        after={
            "id": "scratch",
            "source": "a",
            "target": "b",
            "relation": "CAUSES",
            "confidence": confidence,
        },
    )
    with pytest.raises(ValidationError):
        GraphWorkspacePatch.model_validate(invalid)


def test_graph_drafts_append_and_restore_without_runtime_mutation(tmp_path: Path) -> None:
    output = tmp_path / "drafts.jsonl"
    first = record_kg_draft(request(), output_path=output)
    second = record_kg_draft(request(), output_path=output)
    result = list_kg_drafts(
        KGDraftListRequest(target_type="graph_workspace", target_key=request().target_key),
        input_path=output,
    )
    assert result.total_count == 2
    assert first["record"]["draft_id"] != second["record"]["draft_id"]
    assert all(r.metadata["editor_patch"] == patch() for r in result.records)
    assert set(tmp_path.iterdir()) == {output}


def test_postgres_drafts_only_append_to_advisory_table_and_filter_scope() -> None:
    now = datetime(2026, 11, 11, tzinfo=UTC)
    payload = request().model_dump(mode="json")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.transaction.side_effect = lambda: nullcontext()
    insert = MagicMock()
    insert.fetchone.return_value = {"draft_id": "saved", "created_at": now}
    rows = MagicMock()
    rows.fetchall.return_value = [
        {"draft_id": "saved", "draft_payload": payload, "created_at": now}
    ]
    count = MagicMock()
    count.fetchone.return_value = {"total_count": 1}
    connection.execute.side_effect = [insert, rows, count]
    store = PostgresGraphDraftStore(PostgresConfig(dsn="test-only"), lambda: connection)
    assert store.append(payload)["record"]["draft_id"] == "saved"
    page = store.list(
        KGDraftListRequest(target_type="graph_workspace", target_key=request().target_key)
    )
    assert page["records"][0]["metadata"] == payload["metadata"]
    sql_calls = connection.execute.call_args_list
    assert "INSERT INTO kg_edit_drafts" in sql_calls[0].args[0]
    assert sql_calls[0].args[1][2] == OPERATION
    assert request().target_key in sql_calls[1].args[1]
    assert not any("DELETE" in call.args[0] or "UPDATE" in call.args[0] for call in sql_calls)
    with pytest.raises(ValueError):
        store.append({**payload, "metadata": {"dataset": "unknown"}})


def registry(root: Path, location: str) -> None:
    directory = root / "data/kg"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "source_registry.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_id", "path_or_url", "title"])
        writer.writeheader()
        writer.writerow({"source_id": "manual", "path_or_url": location, "title": "Manual source"})


def test_registered_source_returns_real_excerpt_and_rejects_unknown(tmp_path: Path) -> None:
    doc = tmp_path / "docs/sources/notes.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "# Notes\n\n- `manual`: development knowledge\n  candidate only\n- `other`: other source\n"
    )
    registry(tmp_path, "docs/sources/notes.md")
    result = get_registered_source("manual", root=tmp_path)
    assert result["available"] is True
    assert result["excerpt"] == "- `manual`: development knowledge\n  candidate only"
    assert (result["line_start"], result["line_end"]) == (3, 4)
    with pytest.raises(ValueError, match="Unknown"):
        get_registered_source("unknown", root=tmp_path)


@pytest.mark.parametrize(
    "location",
    [
        "../../secret.txt",
        "private.txt",
        "https://example.com/private",
        "docs/sources/no-file.md",
        "docs/sources/config.json",
    ],
)
def test_source_registry_is_not_arbitrary_file_read_authority(
    tmp_path: Path, location: str
) -> None:
    (tmp_path / "private.txt").write_text("secret")
    registry(tmp_path, location)
    result = get_registered_source("manual", root=tmp_path)
    assert result["available"] is False
    assert result["excerpt"] is None


def test_source_symlink_cannot_escape_boundary(tmp_path: Path) -> None:
    outside = tmp_path / "secret.md"
    outside.write_text("secret")
    folder = tmp_path / "docs/sources"
    folder.mkdir(parents=True)
    (folder / "link.md").symlink_to(outside)
    registry(tmp_path, "docs/sources/link.md")
    assert get_registered_source("manual", root=tmp_path)["available"] is False


def test_visual_fixtures_are_distinct_reproducible_and_honestly_labeled(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    metadata = generate_visual_fixtures(first)
    generate_visual_fixtures(second)
    assert metadata["fixture_type"] == "controlled_synthetic"
    assert metadata["trained_model"] is False and metadata["dataset_sample"] is False
    assert "pixel difference" in metadata["response_method"]
    assert all(
        (first / name).read_bytes() == (second / name).read_bytes()
        for name in (
            "bottle-clean.png",
            "bottle-scratch.png",
            "bottle-mask.png",
            "bottle-response.png",
            "manifest.json",
        )
    )
    clean, scratched = (
        np.asarray(Image.open(first / name)) for name in ("bottle-clean.png", "bottle-scratch.png")
    )
    mask = np.asarray(Image.open(first / "bottle-mask.png"))
    changed = np.any(clean != scratched, axis=2)
    assert changed.any() and np.array_equal(changed, mask > 0)
    assert (first / "bottle-response.png").read_bytes() != (
        first / "bottle-scratch.png"
    ).read_bytes()
    assert json.loads((first / "manifest.json").read_text()) == metadata


def test_demo_origin_cors_and_missing_source_http_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    response = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5174", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"
    assert client.get("/api/kg/sources/unknown").status_code == 404


def test_graph_preview_api_accepts_bounded_limit_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kgtracevis.service import api

    payload = MagicMock()
    payload.model_dump.return_value = {"graph_edges": []}
    loader = MagicMock(return_value=payload)
    monkeypatch.setattr(api, "kg_studio_payload", loader)
    client = TestClient(create_app())
    assert client.get("/api/kg/studio?graph_edge_limit=2000").status_code == 200
    loader.assert_called_once_with(graph_edge_limit=2000)
    assert client.get("/api/kg/studio?graph_edge_limit=2001").status_code == 422
