"""Reversible material archive preserves stored provenance and guards active tasks."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient
from test_two_loop_tasks import MemoryStore, finish

from kgtracevis.service import kg_materials, two_loop_api, two_loop_runtime, two_loop_tasks
from kgtracevis.service.api import create_app

MATERIALS = "/api/kg/materials"
TASKS = "/api/tasks"
SOURCE = b"Inspect the surface; keep the original source and its precise text location."


class ArchiveTaskStore(MemoryStore):
    def material_has_active_task(self, material_id: str) -> bool:
        return any(
            task["kind"] in {"material_parse", "material_build"}
            and task["status"] in {"queued", "running"}
            and material_id in task["request"]["material_ids"]
            for task in self.tasks.copy().values()
        )


@pytest.fixture
def materials_api(tmp_path, monkeypatch):
    root = tmp_path / "materials"
    monkeypatch.setattr(kg_materials, "DEFAULT_SOURCE_KG_MATERIAL_DIR", root)
    store = kg_materials.FileKGMaterialStore(root)
    monkeypatch.setattr(kg_materials, "_MATERIAL_STORE_OVERRIDE", store)
    manager = two_loop_tasks.TaskManager(ArchiveTaskStore(), workers=1)
    manager.handlers.update(
        material_parse=two_loop_runtime.parse_materials,
        material_build=two_loop_runtime.build_materials,
    )
    monkeypatch.setattr(two_loop_tasks, "_manager", manager)
    monkeypatch.setattr(two_loop_api, "task_manager", lambda: manager)
    with TestClient(create_app()) as client:
        yield client, manager
    manager.executor.shutdown()


def upload(client, identity, *, content=SOURCE, overwrite=False):
    return client.post(
        f"{MATERIALS}/upload",
        data={"material_id": identity, "title": identity, "overwrite": str(overwrite).lower()},
        files={"file": ("source.txt", content, "text/plain")},
    )


def submit_parse(client, *ids):
    return client.post(f"{TASKS}/material-parse", json={"material_ids": list(ids)})


def submit_build(client, *ids):
    return client.post(
        f"{TASKS}/material-build",
        json={
            "material_ids": list(ids),
            "dataset": "mvtec",
            "title": "archive guard test",
            "capability_id": "visual-region-v2",
        },
    )


def list_ids(client, query=""):
    response = client.get(MATERIALS + query)
    assert response.status_code == 200
    return [item["material_id"] for item in response.json()["materials"]]


def test_archive_and_restore_preserve_source_and_extraction_history(materials_api):
    client, manager = materials_api
    uploaded = upload(client, "sample")
    assert uploaded.status_code == 200
    assert uploaded.json()["material"]["archived_at"] is None
    source_path = Path(uploaded.json()["material"]["path"])
    parsed = submit_parse(client, "sample")
    assert parsed.status_code == 202
    task = finish(manager, parsed.json())
    assert task["status"] == "completed", task["error"]
    route = f"{MATERIALS}/sample"
    original = client.get(route).json()["material"]
    assert original["chunk_count"] == 1
    paths = {
        "chunks": "chunks",
        "extractions": "runs",
        "artifacts": "artifacts",
    }
    history = {path: client.get(f"{route}/{path}").json()[key] for path, key in paths.items()}
    assert history["chunks"][0]["text_content"] == SOURCE.decode()
    assert history["chunks"][0]["source_locator"]
    assert Path(history["artifacts"][0]["uri"]).is_file()
    assert list_ids(client) == ["sample"]

    archive = client.post(f"{route}/archive")
    assert archive.status_code == 200, archive.text
    archived = archive.json()["material"]
    assert archived["archived_at"]
    assert archive.json()["status"] == "archived"
    assert {**archived, "archived_at": None} == original
    assert client.post(f"{route}/archive").json()["material"] == archived
    assert list_ids(client) == []
    assert list_ids(client, "?archived=true") == ["sample"]
    assert client.get(route).json()["material"] == archived
    for path, key in paths.items():
        assert client.get(f"{route}/{path}").json()[key] == history[path]
    assert client.get(f"{TASKS}/{task['task_id']}").json()["result"] == task["result"]
    assert source_path.read_bytes() == SOURCE

    assert submit_parse(client, "sample").status_code == 409
    assert submit_build(client, "sample").status_code == 409
    assert upload(client, "sample", content=b"replacement", overwrite=True).status_code == 409
    assert source_path.read_bytes() == SOURCE
    assert client.get(route).json()["material"] == archived
    assert len(manager.store.tasks) == 1

    restored = client.post(f"{route}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "restored"
    assert restored.json()["material"] == original
    assert client.post(f"{route}/restore").json()["material"] == original
    assert list_ids(client) == ["sample"]
    assert list_ids(client, "?archived=true") == []
    assert client.post(f"{MATERIALS}/missing/archive").status_code == 404
    assert client.post(f"{MATERIALS}/missing/restore").status_code == 404
    reused = finish(manager, submit_parse(client, "sample").json())
    assert reused["status"] == "completed"
    assert client.get(f"{route}/extractions").json()["runs"] == history["extractions"]


def test_queued_and_running_tasks_block_archive_of_only_their_sources(materials_api):
    client, manager = materials_api
    for identity in ("working", "queued", "unrelated"):
        assert upload(client, identity).status_code == 200
    started, release = Event(), Event()

    def blocked_parse(context, request):
        context.progress("parsing")
        started.set()
        assert release.wait(timeout=5)
        return {"material_ids": request["material_ids"]}

    manager.handlers["material_parse"] = blocked_parse
    manager.handlers["material_build"] = lambda *_: {"graph_id": "fixture"}
    running = submit_parse(client, "working").json()
    try:
        assert started.wait(timeout=5)
        queued = submit_build(client, "queued").json()
        assert manager.store.get_task(running["task_id"])["status"] == "running"
        assert manager.store.get_task(queued["task_id"])["status"] == "queued"
        assert client.post(f"{MATERIALS}/working/archive").status_code == 409
        assert client.post(f"{MATERIALS}/queued/archive").status_code == 409
        assert client.post(f"{MATERIALS}/unrelated/archive").status_code == 200
    finally:
        release.set()
    assert finish(manager, running)["status"] == "completed"
    assert finish(manager, queued)["status"] == "completed"
    assert client.post(f"{MATERIALS}/queued/archive").status_code == 200
    assert client.get(f"{TASKS}/{queued['task_id']}").json()["result"] == {"graph_id": "fixture"}


def test_uploaded_filename_cannot_collide_with_archive_metadata(materials_api):
    client, _ = materials_api
    content = b'{"note":"user-supplied JSON material"}'
    uploaded = client.post(
        f"{MATERIALS}/upload",
        data={"material_id": "json_source"},
        files={"file": ("metadata.json", content, "application/json")},
    )
    assert uploaded.status_code == 200
    material = uploaded.json()["material"]
    assert material["filename"] == "metadata.json"
    assert material["path"] != material["metadata_path"]
    assert client.post(f"{MATERIALS}/json_source/archive").status_code == 200
    assert Path(material["path"]).read_bytes() == content


def test_archive_cannot_interleave_with_task_validation_and_enqueue(materials_api, monkeypatch):
    client, manager = materials_api
    assert upload(client, "sample").status_code == 200
    entering_store, release = Event(), Event()
    save = manager.store.save_task

    def pause_queued_write(task):
        if task["status"] == "queued":
            entering_store.set()
            assert release.wait(timeout=5)
        save(task)

    monkeypatch.setattr(manager.store, "save_task", pause_queued_write)
    with ThreadPoolExecutor(max_workers=1) as request_thread:
        submitted = request_thread.submit(submit_parse, client, "sample")
        try:
            assert entering_store.wait(timeout=5)
            assert not manager.store.tasks
            assert client.post(f"{MATERIALS}/sample/archive").status_code == 409
        finally:
            release.set()
        response = submitted.result(timeout=5)
    assert response.status_code == 202, response.text
    assert finish(manager, response.json())["status"] == "completed"
    assert client.post(f"{MATERIALS}/sample/archive").status_code == 200


def test_retry_validates_archive_state_and_uses_same_source_after_restore(materials_api):
    client, manager = materials_api
    assert upload(client, "sample").status_code == 200

    def fail(_context, _request):
        raise ValueError("controlled failure")

    manager.handlers["material_parse"] = fail
    failed = finish(manager, submit_parse(client, "sample").json())
    assert failed["status"] == "failed"
    assert client.post(f"{MATERIALS}/sample/archive").status_code == 200
    retry_url = f"{TASKS}/{failed['task_id']}/retry"
    blocked = client.post(retry_url)
    assert blocked.status_code == 409
    assert "恢复" in blocked.json()["detail"]
    assert len(manager.store.tasks) == 1
    assert client.post(f"{MATERIALS}/sample/restore").status_code == 200
    manager.handlers["material_parse"] = two_loop_runtime.parse_materials
    submitted = client.post(retry_url)
    assert submitted.status_code == 202
    result = finish(manager, submitted.json())
    assert result["status"] == "completed"
    assert result["retry_of"] == failed["task_id"]
    assert result["request"]["material_ids"] == ["sample"]


def test_archived_source_rejects_entire_build_before_parsing_any_input(materials_api):
    client, manager = materials_api
    assert upload(client, "active").status_code == 200
    assert upload(client, "archived").status_code == 200
    assert client.post(f"{MATERIALS}/archived/archive").status_code == 200
    response = submit_build(client, "active", "archived")
    assert response.status_code == 409
    assert manager.store.tasks == {}
    assert client.get(f"{MATERIALS}/active/extractions").json()["runs"] == []
