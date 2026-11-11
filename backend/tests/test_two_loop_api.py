"""The new public API persists native Frames and exposes honest task state."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from test_two_loop_tasks import MemoryStore, finish

from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.service import two_loop_api as api
from kgtracevis.service import two_loop_runtime as runtime
from kgtracevis.service import visual_evidence
from kgtracevis.service.api import create_app
from kgtracevis.service.two_loop_tasks import TaskManager


@pytest.fixture
def client_runtime(tmp_path, monkeypatch):
    package = UnifiedWorkingGraphPackage.model_validate_json(
        Path("data/kg/unified/bottle-working-graph.v2.json").read_text()
    )
    record = SimpleNamespace(
        status="ready", enabled=True, knowledge=package.knowledge, dataset="mvtec"
    )
    monkeypatch.setattr(api, "working_graph_store", lambda: SimpleNamespace(get=lambda _: record))
    monkeypatch.setattr(api, "export_working_graph", lambda _: package)
    monkeypatch.setattr(api, "TASK_ROOT", tmp_path / "tasks")
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    manager = TaskManager(MemoryStore())
    manager.handlers["inference"] = runtime.infer
    monkeypatch.setattr(api, "task_manager", lambda: manager)
    yield TestClient(create_app()), manager, record
    manager.executor.shutdown()


def test_native_frame_upload_returns_real_task_saved_run_and_download(client_runtime):
    client, manager, _ = client_runtime
    content = Path("data/examples/unified/mvtec-chipped.json").read_bytes()
    response = client.post(
        "/api/tasks/inference",
        data={"graph_id": "g", "input_mode": "evidence"},
        files={"file": ("actual-frame.json", content, "application/json")},
    )
    assert response.status_code == 202, response.text
    submitted = response.json()
    final = finish(manager, submitted)
    assert final["status"] == "completed", final["error"]
    status = client.get("/api/tasks/" + submitted["task_id"]).json()
    assert status["status"] == "completed"
    assert "graph_snapshot" not in status["request"]
    run = client.get("/api/analyses/" + final["result"]["run_id"]).json()
    assert run["cases"][0]["results"][0]["ranked_root_causes"]
    evidence = client.get(run["evidence_download_url"])
    assert evidence.status_code == 200
    assert evidence.json()["frames"] == run["cases"][0]["evidence_frames"]
    assert "evidence-frames.json" in evidence.headers["content-disposition"]
    second = client.post(
        "/api/tasks/inference",
        data={"graph_id": "g", "input_mode": "evidence"},
        files={"file": ("export.json", evidence.content, "application/json")},
    )
    repeat = finish(manager, second.json())
    repeated = client.get("/api/analyses/" + repeat["result"]["run_id"]).json()
    assert repeated["cases"][0]["results"] == run["cases"][0]["results"]


def test_inference_requires_enabled_graph_and_compatible_engine(client_runtime):
    client, _, record = client_runtime
    args = {"data": {"graph_id": "g"}, "files": {"file": ("frame.json", b"{}", "application/json")}}
    record.enabled = False
    response = client.post("/api/tasks/inference", **args)
    assert response.status_code == 400
    assert "启用" in response.json()["detail"]
    record.enabled = True
    args["data"]["reasoner_id"] = "tep_rootkgd"
    response = client.post("/api/tasks/inference", **args)
    assert response.status_code == 400
    assert "TEP" in response.json()["detail"]


def test_history_without_diagnostics_is_not_enriched_from_current_graph(
    client_runtime, monkeypatch
):
    client, manager, _ = client_runtime
    historical = {"run_id": "old", "cases": [{"results": [{"outcome": "no_match"}]}]}
    manager.store.save_analysis(historical)

    def forbidden():
        raise AssertionError("historical run must not load current graph")

    monkeypatch.setattr(api, "working_graph_store", forbidden)
    response = client.get("/api/analyses/old")
    assert response.status_code == 200
    assert response.json() == historical
    assert "authoring_diagnostics" not in response.json()["cases"][0]["results"][0]


def test_invalid_process_windows_rejected_before_running_backbone(client_runtime):
    client, manager, _ = client_runtime
    response = client.post(
        "/api/tasks/inference",
        data={"graph_id": "g", "windows": "[[4,1]]"},
        files={"file": ("x.dat", b"data", "text/plain")},
    )
    assert response.status_code == 400
    assert "闭区间" in response.json()["detail"]
    assert not manager.store.tasks


def test_raw_analysis_with_unregistered_model_stops_at_adapter(
    client_runtime,
    tmp_path,
    monkeypatch,
):
    client, manager, _ = client_runtime
    monkeypatch.setenv("KGTRACEVIS_MVTEC_MODEL_MANIFEST", str(tmp_path / "missing.json"))
    response = client.post(
        "/api/tasks/inference",
        data={
            "graph_id": "g",
            "input_mode": "image",
            "object_name": "bottle",
            "model_preset": "efficientad",
        },
        files={"file": ("unused.png", b"not-read", "image/png")},
    )
    assert response.status_code == 202
    task = finish(manager, response.json())
    assert task["status"] == "failed"
    assert task["error"]["stage"] == "adapter"
    assert "efficientad" in task["error"]["message"]
    assert not manager.store.analyses


def test_visual_provider_failure_does_not_save_a_substitute_diagnosis(client_runtime, monkeypatch):
    from kgtracevis.producers.visual_semantics import ROISemanticServiceError

    client, manager, _ = client_runtime

    def failed(*_args):
        raise ROISemanticServiceError("ROI 视觉服务调用失败")

    monkeypatch.setattr(runtime, "_image_records", failed)
    response = client.post(
        "/api/tasks/inference",
        data={"graph_id": "g", "input_mode": "image", "semantic_mode": "vlm"},
        files={"file": ("public.png", b"image-fixture", "image/png")},
    )
    assert response.status_code == 202
    task = finish(manager, response.json())
    assert task["status"] == "failed"
    assert task["error"]["stage"] == "adapter"
    assert "视觉服务" in task["error"]["message"]
    assert not manager.store.analyses


def test_demo_library_only_resolves_manifest_whitelist(client_runtime, tmp_path, monkeypatch):
    client, _, _ = client_runtime
    manifest = tmp_path / "unsafe.json"
    manifest.write_text(
        json.dumps(
            {
                "demos": [
                    {
                        "id": "bad",
                        "samples": [],
                        "working_graph": {"asset_id": "outside", "path": "/etc/passwd"},
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(api, "DEMO_MANIFEST", manifest)
    response = client.get("/api/demo-library")
    assert response.status_code == 400
    assert "越出" in response.json()["detail"]


@pytest.mark.parametrize(
    "filename,media_type",
    [
        ("wafer-nearfull.jsonl", "application/x-ndjson"),
        ("process-sequence.dat", "application/octet-stream"),
        ("sample_006.png", "image/png"),
    ],
)
def test_demo_download_preserves_real_filename_extension(
    client_runtime, tmp_path, monkeypatch, filename, media_type
):
    client, _, _ = client_runtime
    (tmp_path / filename).write_bytes(b"public-demo-asset")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "demos": [
                    {
                        "id": "test",
                        "samples": [],
                        "materials": [
                            {"asset_id": "public-asset", "path": filename, "media_type": media_type}
                        ],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(api, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(api, "DEMO_MANIFEST", manifest)
    response = client.get("/api/demo-library/assets/public-asset")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'
    assert response.headers["content-type"] == media_type
    assert response.content == b"public-demo-asset"


def write_demo_manifest(tmp_path, monkeypatch, sample):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"demos": [{"id": "test", "samples": [sample]}]}))
    monkeypatch.setattr(api, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(api, "DEMO_MANIFEST", manifest)


@pytest.mark.parametrize(
    "dataset,mode,package_stem,frame_stem,support_id",
    [
        ("mvtec", "image", "bottle", "mvtec-chipped", "mask"),
        ("tep", "process", "tep", "tep-cooling-window", "window"),
        ("wafer", "wafer", "wafer", "wafer-nearfull", "grid"),
    ],
)
def test_demo_native_evidence_can_run_without_optional_media(
    client_runtime, tmp_path, monkeypatch, dataset, mode, package_stem, frame_stem, support_id
):
    client, manager, record = client_runtime
    package = UnifiedWorkingGraphPackage.model_validate_json(
        Path(f"data/kg/unified/{package_stem}-working-graph.v2.json").read_text()
    )
    record.dataset = dataset
    monkeypatch.setattr(api, "export_working_graph", lambda _: package)
    frame = Path(f"data/examples/unified/{frame_stem}.json").read_bytes()
    (tmp_path / "evidence.json").write_bytes(frame)
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "sample",
            "title": "无原件的公开 Frame",
            "dataset": dataset,
            "input_mode": mode,
            "evidence": {"asset_id": "frame", "path": "evidence.json"},
            "raw_input": {"asset_id": "original", "path": "not-downloaded.dat"},
            "supporting_assets": [
                {"asset_id": "support", "path": "not-downloaded.json", "frame_asset_id": support_id}
            ],
        },
    )
    args = {"sample_id": "sample", "graph_id": "g", "input_variant": "evidence"}
    response = client.post("/api/tasks/inference/demo", json=args)
    assert response.status_code == 202, response.text
    task = finish(manager, response.json())
    assert task["status"] == "completed", task["error"]
    assert task["request"]["media_bindings"] == {}
    run = client.get("/api/analyses/" + task["result"]["run_id"]).json()
    assert run["input_mode"] == "evidence"
    assert run["cases"][0]["evidence_frames"][0]["case_id"] == json.loads(frame)["case_id"]
    assert run["cases"][0]["results"][0]["ranked_root_causes"]
    assert run["cases"][0]["media_status"] == "not_attached"
    assert run["media_assets"] == {}

    rejected = client.post("/api/tasks/inference/demo", json={**args, "input_variant": "raw"})
    assert rejected.status_code == 400
    assert "演示资产不可用" in rejected.json()["detail"]
    assert len(manager.store.tasks) == 1


def test_demo_native_evidence_preserves_prepared_image_attachment(
    client_runtime, tmp_path, monkeypatch
):
    client, manager, _ = client_runtime
    frame = Path("data/examples/unified/mvtec-chipped.json").read_text()
    (tmp_path / "evidence.json").write_text(json.dumps({"frames": [json.loads(frame)]}))
    image = tmp_path / "original.png"
    Image.new("RGB", (16, 16), "white").save(image)
    monkeypatch.setattr(visual_evidence, "PROJECT_ROOT", tmp_path)
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "sample",
            "title": "有原图的公开 Frame",
            "dataset": "mvtec",
            "input_mode": "image",
            "evidence": {"asset_id": "frame", "path": "evidence.json"},
            "raw_input": {"asset_id": "original", "path": image.name},
            "supporting_assets": [
                {"asset_id": "support", "path": "optional-mask.json", "frame_asset_id": "mask"}
            ],
        },
    )
    response = client.post(
        "/api/tasks/inference/demo",
        json={"sample_id": "sample", "graph_id": "g", "input_variant": "evidence"},
    )
    assert response.status_code == 202, response.text
    task = finish(manager, response.json())
    assert task["status"] == "completed", task["error"]
    assert list(task["request"]["media_bindings"].values()) == [str(image)]
    run = client.get("/api/analyses/" + task["result"]["run_id"]).json()
    assert run["cases"][0]["media_status"] == "available"
    assert any(
        item["kind"] == "image" and item["available"] for item in run["cases"][0]["visual_evidence"]
    )


def test_demo_process_media_is_scoped_to_the_actual_frame(client_runtime, tmp_path, monkeypatch):
    client, manager, record = client_runtime
    package = UnifiedWorkingGraphPackage.model_validate_json(
        Path("data/kg/unified/tep-working-graph.v2.json").read_text()
    )
    record.dataset = "tep"
    monkeypatch.setattr(api, "export_working_graph", lambda _: package)
    frames, supporting = [], []
    for value in (1, 2):
        frame = json.loads(Path("data/examples/unified/tep-cooling-window.json").read_text())
        frame["case_id"] = f"window_{value}/query/window"
        asset = next(item for item in frame["assets"] if item["asset_id"] == "window")
        asset["uri"] = f"evidence://window_{value}"
        filename = f"window-{value}.npy"
        np.save(tmp_path / filename, np.full(asset["shape"], value), allow_pickle=False)
        frames.append(frame)
        supporting.append(
            {
                "asset_id": f"media-{value}",
                "path": filename,
                "case_asset_id": "window",
                "frame_case_id": frame["case_id"],
            }
        )
    (tmp_path / "evidence.json").write_text(json.dumps({"frames": frames}))
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "sample",
            "title": "两个保存窗口",
            "dataset": "tep",
            "input_mode": "process",
            "evidence": {"asset_id": "frame", "path": "evidence.json"},
            "raw_input": {"asset_id": "original", "path": "not-downloaded.dat"},
            "supporting_assets": supporting,
        },
    )
    response = client.post(
        "/api/tasks/inference/demo",
        json={"sample_id": "sample", "graph_id": "g", "input_variant": "evidence"},
    )
    assert response.status_code == 202, response.text
    task = finish(manager, response.json())
    assert task["status"] == "completed", task["error"]
    run = client.get("/api/analyses/" + task["result"]["run_id"]).json()
    assert [case["media_status"] for case in run["cases"]] == ["available", "available"]
    assert [case["process_trends"][0]["samples"][0] for case in run["cases"]] == [1.0, 2.0]


@pytest.mark.parametrize(
    "asset_location,message", [("../outside.png", "越出"), ("directory", "不可用")]
)
def test_demo_evidence_rejects_invalid_optional_attachment(
    client_runtime, tmp_path, monkeypatch, asset_location, message
):
    client, manager, _ = client_runtime
    (tmp_path / "evidence.json").write_text("{}")
    (tmp_path / "directory").mkdir()
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "sample",
            "title": "错误的资源路径",
            "dataset": "mvtec",
            "input_mode": "image",
            "evidence": {"asset_id": "frame", "path": "evidence.json"},
            "raw_input": {"asset_id": "original", "path": asset_location},
        },
    )
    response = client.post(
        "/api/tasks/inference/demo",
        json={"sample_id": "sample", "graph_id": "g", "input_variant": "evidence"},
    )
    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert not manager.store.tasks


def test_demo_raw_process_still_requires_a_normal_reference(client_runtime, tmp_path, monkeypatch):
    client, manager, record = client_runtime
    record.dataset = "tep"
    (tmp_path / "raw.dat").write_text("placeholder")
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "sample",
            "title": "缺正常参考的过程原始输入",
            "dataset": "tep",
            "input_mode": "process",
            "raw_input": {"asset_id": "original", "path": "raw.dat"},
        },
    )
    response = client.post(
        "/api/tasks/inference/demo", json={"sample_id": "sample", "graph_id": "g"}
    )
    assert response.status_code == 400
    assert "正常参考" in response.json()["detail"]
    assert not manager.store.tasks
