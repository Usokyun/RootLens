"""The new public API persists native Frames and exposes honest task state."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from graded_fixtures import compact_bottle, public_release, without_grades
from PIL import Image
from test_graded_reasoner import ECC, observation
from test_two_loop_tasks import MemoryStore, finish
from test_unified_integration import storage as storage

from kgtracevis.kg.unified_working_package import UnifiedWorkingGraphPackage
from kgtracevis.service import two_loop_api as api
from kgtracevis.service import two_loop_runtime as runtime
from kgtracevis.service import visual_evidence
from kgtracevis.service.api import create_app
from kgtracevis.service.two_loop_tasks import TaskManager


@pytest.fixture
def client_runtime(tmp_path, monkeypatch):
    package = UnifiedWorkingGraphPackage.model_validate(compact_bottle()[0])
    record = SimpleNamespace(
        status="ready", enabled=True, knowledge=package.knowledge, dataset="mvtec"
    )
    monkeypatch.setattr(api, "working_graph_store", lambda: SimpleNamespace(get=lambda _: record))
    monkeypatch.setattr(api, "export_v2_working_graph", lambda _: package)
    monkeypatch.setattr(api, "TASK_ROOT", tmp_path / "tasks")
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    manager = TaskManager(MemoryStore())
    manager.handlers["inference"] = runtime.infer
    monkeypatch.setattr(api, "task_manager", lambda: manager)
    yield TestClient(create_app()), manager, record
    manager.executor.shutdown()


def test_native_frame_upload_returns_real_task_saved_run_and_download(client_runtime):
    client, manager, _ = client_runtime
    _, (frame,) = compact_bottle()
    content = json.dumps(frame).encode()
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
    assert run["reasoner_id"] == "graded_abduction"
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


def test_graded_engine_requires_config_and_saves_the_same_native_analysis_on_reupload(
    client_runtime, monkeypatch
):
    client, manager, record = client_runtime
    row = next(
        r
        for r in client.get("/api/reasoners").json()["reasoners"]
        if r["reasoner_id"] == "graded_abduction"
    )
    assert row["requires_graded_policy"] is True
    args = {"graph_id": "g", "input_mode": "evidence", "reasoner_id": "graded_abduction"}
    payload, frames = compact_bottle()
    stripped = {**payload, "knowledge": without_grades(payload["knowledge"])}
    ungraded = UnifiedWorkingGraphPackage.model_validate(stripped)
    monkeypatch.setattr(api, "export_v2_working_graph", lambda _: ungraded)
    wrong = client.post(
        "/api/tasks/inference",
        data=args,
        files={"file": ("unread.json", b"{}", "application/json")},
    )
    assert wrong.status_code == 400 and "graded_policy" in wrong.json()["detail"]
    assert not manager.store.tasks

    package = UnifiedWorkingGraphPackage.model_validate(payload)
    record.knowledge = package.knowledge
    monkeypatch.setattr(api, "export_v2_working_graph", lambda _: package)
    frame = frames[0]
    eccentricity = observation(frame, ECC)
    eccentricity["value"]["number"] = 0.94

    def run(content):
        response = client.post(
            "/api/tasks/inference",
            data=args,
            files={"file": ("frame.json", content, "application/json")},
        )
        assert response.status_code == 202, response.text
        task = finish(manager, response.json())
        assert task["status"] == "completed", task["error"]
        return client.get("/api/analyses/" + task["result"]["run_id"]).json()

    saved = run(json.dumps(frame).encode())
    assert saved["reasoner_id"] == "graded_abduction"
    assert saved["working_graph_snapshot"]["knowledge"]["graded_policy"]
    result = saved["cases"][0]["results"][0]
    assert result["scoring_method"] == "graded_joint_abduction_v1"
    assert not result["ranked_root_causes"]
    pending = result["graded_candidates"]
    assert [r["score"] for r in pending] == pytest.approx([0.5, 0.5])
    (counter,) = [
        p for p in pending[0]["explanation_paths"] if p["contribution_kind"] == "conflict"
    ]
    assert counter["observation_locations"][0]["obs_id"] == eccentricity["obs_id"]
    assert counter["source_assertions"] and counter["joint_proof_id"] is None
    assert [e["edge_id"] for e in counter["source_edges"]] == [
        v["edge_id"] for v in counter["source_edge_views"]
    ]
    assert all(e["relation"] for e in counter["source_edges"])
    report = result["authoring_diagnostics"]
    assert report["evidence_usage"]["score_input_observation_count"] == 3
    assert report["equivalence_groups"][0]["cost_priors"] == []
    exported = client.get(saved["evidence_download_url"])
    assert exported.status_code == 200
    repeated = run(exported.content)
    assert repeated["working_graph_snapshot"] == saved["working_graph_snapshot"]
    assert repeated["cases"] == saved["cases"]


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
    manifest.write_text(
        json.dumps(
            {
                "demos": [
                    {"id": "test", "dataset": sample["dataset"], "samples": [sample]},
                ]
            }
        )
    )
    monkeypatch.setattr(api, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(api, "DEMO_MANIFEST", manifest)


def configure_dataset(record, monkeypatch, dataset):
    payload, frames = public_release(dataset)
    package = UnifiedWorkingGraphPackage.model_validate(payload)
    record.dataset = dataset
    record.knowledge = package.knowledge
    monkeypatch.setattr(api, "export_v2_working_graph", lambda _: package)
    return frames


@pytest.mark.parametrize(
    "dataset,mode,support_id,frame_index",
    [("mvtec", "image", "mask", 0), ("tep", "process", "window", 1), ("wafer", "wafer", "grid", 0)],
)
def test_demo_native_evidence_can_run_without_optional_media(
    client_runtime, tmp_path, monkeypatch, dataset, mode, support_id, frame_index
):
    client, manager, record = client_runtime
    frame = configure_dataset(record, monkeypatch, dataset)[frame_index]
    (tmp_path / "evidence.json").write_text(json.dumps(frame))
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
                {
                    "asset_id": "support",
                    "path": "not-downloaded.json",
                    "case_asset_id": support_id,
                    "frame_case_id": frame["case_id"],
                }
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
    assert run["cases"][0]["evidence_frames"][0]["case_id"] == frame["case_id"]
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
    _, frames = compact_bottle()
    (tmp_path / "evidence.json").write_text(json.dumps({"frames": frames}))
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
        json={"sample_id": "sample", "graph_id": "g"},
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
    source = configure_dataset(record, monkeypatch, "tep")
    frames, supporting = [], []
    for value, frame in enumerate(source[:2], 1):
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
    _, frames = compact_bottle()
    (tmp_path / "evidence.json").write_text(json.dumps({"frames": frames}))
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
    configure_dataset(record, monkeypatch, "tep")
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
        "/api/tasks/inference/demo",
        json={"sample_id": "sample", "graph_id": "g", "input_variant": "raw"},
    )
    assert response.status_code == 400
    assert "正常参考" in response.json()["detail"]
    assert not manager.store.tasks


def test_public_inference_does_not_accept_retired_aliases_or_legacy_payload(client_runtime):
    client, manager, _ = client_runtime
    assert [row["reasoner_id"] for row in client.get("/api/reasoners").json()["reasoners"]] == [
        "graded_abduction",
        "tep_rootkgd",
    ]
    for field, value in [
        ("reasoner_id", "unified_abduction"),
        ("reasoner_id", "unified"),
        ("input_mode", "records"),
        ("input_mode", "tep_raw"),
    ]:
        response = client.post(
            "/api/tasks/inference",
            data={"graph_id": "g", field: value},
            files={"file": ("frame.json", b"{}", "application/json")},
        )
        assert response.status_code == 422, response.text
    response = client.post(
        "/api/tasks/inference",
        data={"graph_id": "g"},
        files={"file": ("legacy.json", b'{"case_id":"old","dataset":"mvtec"}', "application/json")},
    )
    assert response.status_code == 400 and "rootlens-evidence.v2" in response.json()["detail"]
    assert not manager.store.tasks


def test_old_inference_retry_is_not_reinterpreted_as_a_new_reasoner(client_runtime):
    client, manager, _ = client_runtime
    historical = {
        "task_id": "old",
        "kind": "inference",
        "status": "failed",
        "events": [],
        "request": {"reasoner_id": "unified_abduction", "input_mode": "evidence"},
    }
    manager.store.save_task(historical)
    response = client.post("/api/tasks/old/retry")
    assert response.status_code == 400 and "解释器不可用" in response.json()["detail"]
    assert manager.store.tasks == {"old": historical}


def test_demo_evidence_rejects_cross_scenario_before_resolving_any_asset(
    client_runtime, tmp_path, monkeypatch
):
    client, manager, _ = client_runtime
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "wafer",
            "dataset": "wafer",
            "title": "晶圆样本",
            "input_mode": "wafer",
            "evidence": {"asset_id": "frame", "path": "not-read.json"},
        },
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("a cross-scenario request must not touch any asset")

    monkeypatch.setattr(api, "asset_path", forbidden)
    response = client.post(
        "/api/tasks/inference/demo",
        json={"sample_id": "wafer", "graph_id": "g", "input_variant": "evidence"},
    )
    assert response.status_code == 400 and "场景与所选工作图不一致" in response.json()["detail"]
    assert not manager.store.tasks


def test_demo_wafer_media_cannot_fall_back_to_first_grid_in_a_batch(
    client_runtime, tmp_path, monkeypatch
):
    client, manager, record = client_runtime
    frames = configure_dataset(record, monkeypatch, "wafer")
    (tmp_path / "evidence.json").write_text(json.dumps({"frames": frames}))
    first, second = [[0, 1], [2, 2]], [[0, 2], [1, 1]]
    (tmp_path / "batch.jsonl").write_text(
        "\n".join(
            json.dumps({"case_id": f["case_id"], "waferMap": grid})
            for f, grid in zip(frames, (first, second), strict=True)
        )
    )
    (tmp_path / "first.json").write_text(json.dumps(first))
    write_demo_manifest(
        tmp_path,
        monkeypatch,
        {
            "sample_id": "wafer",
            "dataset": "wafer",
            "title": "两帧晶圆样本",
            "input_mode": "wafer",
            "evidence": {"asset_id": "frame", "path": "evidence.json"},
            "raw_input": {"asset_id": "original", "path": "batch.jsonl"},
            "supporting_assets": [
                {
                    "asset_id": identity,
                    "path": identity + ".json",
                    "case_asset_id": "grid",
                    "frame_case_id": frame["case_id"],
                }
                for frame, identity in zip(frames, ("first", "not-downloaded"), strict=True)
            ],
        },
    )
    response = client.post(
        "/api/tasks/inference/demo",
        json={"sample_id": "wafer", "graph_id": "g", "input_variant": "evidence"},
    )
    assert response.status_code == 202, response.text
    task = finish(manager, response.json())
    assert task["status"] == "completed", task["error"]
    run = manager.store.get_analysis(task["result"]["run_id"])
    first_case, second_case = run["cases"]
    assert first_case["media_status"] == "available" and first_case["wafer_map"] == first
    assert second_case["media_status"] == "not_attached" and "wafer_map" not in second_case
    assert second_case["results"][0]["graded_candidates"]
    assert list(task["request"]["media_bindings"].values()) == [str(tmp_path / "first.json")]


def test_public_material_build_compiles_a_measured_budget_and_can_run_native_frame(
    storage, tmp_path, monkeypatch
):
    from contextlib import nullcontext

    from test_source_gate_safety import source_blueprint

    from kgtracevis.service import two_loop_tasks
    from kgtracevis.source_kg_compiler import compiler, llm

    store, _, _ = storage
    units, _, blueprint = source_blueprint(tmp_path, logic="all")
    proposal = blueprint.model_dump(mode="json")
    conditions = proposal["signatures"][0]["conditions"]
    template = conditions[1]
    conditions[0].update(feature_id="detection.anomaly_present")
    conditions[:] = [conditions[0]] + [
        {
            **template,
            "feature_id": feature,
            "label": label,
            "op": op,
            "operand": {"kind": "number", "number": boundary, "unit": "1"},
        }
        for feature, label, op, boundary in [
            ("geometry.area_ratio", "测试面积下界", "gte", 0.1),
            ("geometry.area_ratio", "测试面积上界", "lte", 0.5),
            ("geometry.aspect_ratio", "测试长短比", "lte", 2),
        ]
    ]

    class FixtureLLM:
        calls = 0

        def complete_json(self, **kwargs):
            self.calls += 1
            return json.dumps(proposal)

    provider = FixtureLLM()
    monkeypatch.setattr(two_loop_tasks, "material_operations", lambda _: nullcontext(None))
    monkeypatch.setattr(
        two_loop_tasks,
        "require_active_material",
        lambda _, identity: SimpleNamespace(material_id=identity, scenario="mvtec"),
    )
    monkeypatch.setattr(llm, "OpenAICompatibleSourceKGLLM", lambda: provider)
    monkeypatch.setattr(compiler, "load_source_units", lambda *a, **k: units)
    monkeypatch.setattr(runtime, "parse_materials", lambda context, request: None)
    monkeypatch.setattr(
        runtime,
        "prepare_kg_material_construction_build",
        lambda _: SimpleNamespace(
            sources=[SimpleNamespace(path=tmp_path / "source.txt")],
            materials=[],
        ),
    )
    monkeypatch.setattr(api, "TASK_ROOT", tmp_path / "tasks")
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    manager = TaskManager(MemoryStore())
    manager.handlers.update(material_build=runtime.build_materials, inference=runtime.infer)
    monkeypatch.setattr(api, "task_manager", lambda: manager)
    client = TestClient(create_app())
    try:
        submission = client.post(
            "/api/tasks/material-build",
            json={
                "material_ids": ["source"],
                "title": "测试源稿预算",
                "dataset": "mvtec",
                "capability_id": "visual-region-v2",
                "max_repairs": 0,
            },
        )
        assert submission.status_code == 202, submission.text
        built = finish(manager, submission.json())
        assert built["status"] == "completed", built["error"]
        assert provider.calls == 1
        gid = built["result"]["graph_id"]
        assert not store.get(gid).enabled
        graph = client.get(f"/api/kg/working-graphs/{gid}/package").json()
        knowledge = graph["knowledge"]
        (group,) = knowledge["graded_policy"]["groups"]
        assert group["group_id"] == "source-draft"
        assert [len(s["predicate_ids"]) for s in group["slots"]] == [2, 1]
        assert {s["weight"] for s in group["slots"]} == {1}
        assert all("grade" not in p for p in knowledge["observable_definitions"])
        artifact = tmp_path / "tasks" / built["task_id"] / "build" / "working-graph.v2.json"
        saved = UnifiedWorkingGraphPackage.model_validate_json(artifact.read_bytes())
        assert saved.knowledge.graded_policy == store.get(gid).knowledge.graded_policy

        entity = next(e for e in knowledge["entities"] if e["entity_id"].endswith(":bottle"))
        entity["aliases"].append("复核别名")
        edited = client.put(f"/api/kg/working-graphs/{gid}/package", json=graph)
        assert edited.status_code == 200, edited.text
        assert (
            client.post(f"/api/kg/working-graphs/{gid}/enable", json={"enabled": True}).status_code
            == 200
        )
        _, (frame,) = public_release("mvtec")
        infer = client.post(
            "/api/tasks/inference",
            data={"graph_id": gid},
            files={"file": ("frame.json", json.dumps(frame).encode(), "application/json")},
        )
        assert infer.status_code == 202, infer.text
        completed = finish(manager, infer.json())
        assert completed["status"] == "completed", completed["error"]
        run = manager.store.get_analysis(completed["result"]["run_id"])
        assert run["reasoner_id"] == "graded_abduction"
        assert (
            run["working_graph_snapshot"]["knowledge"]["graded_policy"]
            == knowledge["graded_policy"]
        )
        assert run["cases"][0]["results"][0]["outcome"] == "supported"
    finally:
        manager.executor.shutdown()
