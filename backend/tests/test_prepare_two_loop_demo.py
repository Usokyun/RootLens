"""Demo clients preserve authoring budgets and truthful insufficient outcomes."""

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pandas as pd
import pytest

from kgtracevis.source_kg_compiler import llm, material_parser, unified
from scripts import prepare_public_wafer_demo as wafer_demo
from scripts import prepare_two_loop_demo as prepare
from scripts import prepare_two_loop_demo_api as api_demo
from scripts.prepare_two_loop_demo_api import DemoClient


def test_shipped_mvtec_catalog_is_independent_of_runtime_archives(tmp_path, monkeypatch):
    old = (
        tmp_path
        / "runs/two_loop_demo/api-e2e-002/bottle-chipped-raw-unified_abduction.analysis.json"
    )
    old.parent.mkdir(parents=True)
    old.write_text('{"cases": [{"evidence_frames": [{"must_not_be_reused": true}]}]}')
    monkeypatch.setattr(prepare, "RUNTIME", tmp_path / "runs/two_loop_demo")
    manifest_path = prepare.SMALL / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    catalog = prepare.prepare(dataset="mvtec")
    (demo,) = catalog["demos"]
    (sample,) = demo["samples"]
    assert demo["id"] == "bottle"
    assert sample["sample_id"] == "bottle-rim-break" and sample["recommended"]
    assert sample["raw_options"] == {
        "object_name": "bottle",
        "model_preset": "patchcore",
        "semantic_mode": "disabled",
    }
    assert "normal_reference" not in sample
    assert all("asset_id" not in model and "path" not in model for model in demo["models"])
    for asset in demo["materials"] + [
        demo["working_graph"],
        sample["raw_input"],
        sample["evidence"],
    ]:
        assert asset["path"].startswith("data/demo/two_loop/mvtec/")
        assert (prepare.ROOT / asset["path"]).is_file()
    # The distributed export is the native envelope, not a copied bare frame from an old run.
    assert "frames" in json.loads((prepare.ROOT / sample["evidence"]["path"]).read_text())
    report = prepare.check(catalog)
    assert report["missing_assets"] == []
    assert report["validated"][0]["frames"] == 1
    assert manifest_path.read_bytes() == manifest_bytes


@pytest.mark.parametrize("payload,valid", [(b"exact-checkpoint", True), (b"partial", False)])
def test_bottle_checkpoint_publish_is_atomic(tmp_path, monkeypatch, payload, valid):
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    monkeypatch.setattr(prepare, "RUNTIME", tmp_path / "runs/two_loop_demo")
    monkeypatch.setattr(prepare, "PUBLIC", tmp_path / "unused-cache")
    monkeypatch.setattr(prepare.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(payload))
    expected = b"exact-checkpoint"
    model = {
        "local_path": "runs/two_loop_demo/models/bottle.ckpt",
        "source_url": "https://unused.invalid/fixed/model.ckpt",
        "size_bytes": len(expected),
        "sha256": hashlib.sha256(expected).hexdigest(),
    }
    if valid:
        prepare.prepare_bottle_checkpoint({"models": [model]})
        assert (tmp_path / model["local_path"]).read_bytes() == expected
        registry = json.loads((tmp_path / prepare.MVTEC_MODEL_MANIFEST).read_text())
        assert registry["objects"]["bottle"]["patchcore"] == {"checkpoint": model["local_path"]}
    else:
        with pytest.raises(ValueError, match="不符合固定发布版本"):
            prepare.prepare_bottle_checkpoint({"models": [model]})
        assert not (tmp_path / prepare.MVTEC_MODEL_MANIFEST).exists()
        assert not (tmp_path / model["local_path"]).exists()
    assert not list((tmp_path / Path(model["local_path"]).parent).glob("*.part"))


def test_release_has_only_the_three_paired_examples_and_exact_tep_windows():
    manifest = prepare.read_manifest()
    expected = {
        "mvtec": ("bottle-rim-break", 1),
        "tep": ("tep-sequence-04", 3),
        "wafer": ("wafer-nearfull", 1),
    }
    assert len(manifest["demos"]) == len(expected)
    for demo in manifest["demos"]:
        scene = demo["dataset"]
        sample_id, frame_count = expected[scene]
        (sample,) = demo["samples"]
        assert sample["sample_id"] == sample_id and sample["recommended"]
        assert all((prepare.ROOT / a["path"]).is_file() for a in demo["materials"])
        assert all(a["path"].startswith(f"data/demo/two_loop/{scene}/") for a in demo["materials"])
        frames = prepare.frames_from_asset(sample["evidence"])
        assert len(frames) == frame_count and all(frame.source_dataset == scene for frame in frames)
        if scene == "tep":
            support = sample["supporting_assets"]
            assert {a["frame_case_id"] for a in support if a.get("case_asset_id") == "window"} == {
                f.case_id for f in frames
            }
            assert [
                [scope.sample_start, scope.sample_end]
                for f in frames
                for scope in f.scopes
                if scope.scope_id == f.task.scope_id
            ] == sample["raw_options"]["windows"]
        if scene == "wafer":
            assert sample["raw_input"]["storage_scope"] == "local_runtime"
            assert sample["raw_source"]["row_id"] == "248536"
            assert sample["raw_input"]["path"].startswith("runs/two_loop_demo/")
            assert '"waferMap"' not in (prepare.ROOT / sample["evidence"]["path"]).read_text()
    report = prepare.check(manifest)
    assert not report["missing_assets"]
    assert {item["sample_id"]: item["frames"] for item in report["validated"]} == {
        sample_id: frame_count for sample_id, frame_count in expected.values()
    }


def test_wafer_preparation_emits_only_the_pinned_row_identity_and_cells(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    monkeypatch.setattr(prepare, "RUNTIME", tmp_path / "runs/two_loop_demo")
    monkeypatch.setattr(prepare, "PUBLIC", tmp_path / "unused-cache")
    table = pd.DataFrame(
        {
            "waferMap": [np.array([[0, 1], [2, 1]]), np.array([[1, 2], [2, 1]])],
            "failureType": ["must not copy", "another row"],
        },
        index=[248536, 2],
    )
    payloads = {"table": b"example-pinned-table", "model": b"example-pinned-weight"}

    def read_verified_table(handle):
        assert handle.read() == payloads["table"]
        return SimpleNamespace(load=lambda: table)

    monkeypatch.setattr(wafer_demo, "DataOnlyUnpickler", read_verified_table)

    def asset(label):
        raw = payloads[label]
        return {
            "source_url": label,
            "local_path": f"runs/two_loop_demo/{label}",
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr(
        prepare.urllib.request, "urlopen", lambda url, **_: io.BytesIO(payloads[url])
    )
    raw = "runs/two_loop_demo/wafer.jsonl"
    demo = {
        "models": [asset("model")],
        "samples": [
            {
                "raw_input": {"path": raw},
                "raw_source": {**asset("table"), "row_id": "248536", "shape": [2, 2]},
            }
        ],
    }
    prepare.prepare_wafer(demo, download=True)
    assert json.loads((tmp_path / raw).read_text()) == {
        "wafer_id": "248536",
        "case_id": "wm811k_248536",
        "waferMap": [[0, 1], [2, 1]],
    }


def test_api_demo_graph_reuses_exact_enabled_pair_or_only_installs_missing(tmp_path, monkeypatch):
    client = DemoClient("http://unused.invalid", tmp_path / "client")
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path))
        if method == "GET":
            return {"title": "unchanged paired package"}
        if path.endswith("/import"):
            assert kwargs["json"] == {"title": "unchanged paired package"}
            return {"graph_id": "new-graph"}
        assert kwargs["json"] == {"enabled": True}

    monkeypatch.setattr(client, "request", request)
    try:
        client.import_graphs(
            [
                {"id": "existing", "graph_ref": {"state": "ready", "graph_id": "exact-id"}},
                {
                    "id": "bottle",
                    "working_graph": {"download_url": "/api/demo-library/assets/pair"},
                    "graph_ref": {"state": "missing", "graph_id": None},
                },
            ]
        )
        assert client.state["graphs"] == {"existing": "exact-id", "bottle": "new-graph"}
        assert calls == [
            ("GET", "/api/demo-library/assets/pair"),
            ("POST", "/api/kg/working-graphs/import"),
            ("POST", "/api/kg/working-graphs/new-graph/enable"),
        ]
    finally:
        client.client.close()


def test_api_demo_retries_status_read_without_resubmitting_task(tmp_path, monkeypatch):
    client = DemoClient("http://unused.invalid", tmp_path / "client")
    responses = iter(
        [
            {"task_id": "run-once"},
            httpx.ReadError("connection reset"),
            {"task_id": "run-once", "stage": "completed", "status": "completed"},
        ]
    )
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path))
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(client, "request", request)
    monkeypatch.setattr(api_demo.time, "sleep", lambda _: None)
    try:
        assert client.task("raw", "/api/tasks/inference/demo", {})["status"] == "completed"
        assert calls == [
            ("POST", "/api/tasks/inference/demo"),
            ("GET", "/api/tasks/run-once"),
            ("GET", "/api/tasks/run-once"),
        ]
    finally:
        client.client.close()


@pytest.mark.parametrize(
    "dataset,capability_id,recommended,hard_limit",
    [
        ("bottle", "visual-region-v2", 16, 32),
        ("tep", "process-window-v2", 16, 32),
        ("wafer", "spatial-grid-v2", 8, 8),
    ],
)
def test_build_knowledge_keeps_compact_recommendation_separate_from_hard_limit(
    tmp_path, monkeypatch, dataset, capability_id, recommended, hard_limit
):
    captured = []

    def capture_compile(units, capability, **kwargs):
        captured.append((units, capability, kwargs))
        return SimpleNamespace(nodes=[], edges=[])

    monkeypatch.setattr(
        material_parser, "parse_material", lambda *a, **k: SimpleNamespace(units=[])
    )
    monkeypatch.setattr(
        llm,
        "OpenAICompatibleSourceKGLLM",
        lambda **kwargs: SimpleNamespace(calls=0, total_tokens=0),
    )
    monkeypatch.setattr(unified, "compile_unified_knowledge", capture_compile)

    result = prepare.build_knowledge(dataset, tmp_path / "new-build")

    assert len(captured) == 1
    capability = captured[0][1]
    assert capability.capability_id == capability_id
    assert capability.recommended_max_candidates == recommended
    assert capability.max_candidates == hard_limit
    assert captured[0][2]["dataset"] == ("mvtec" if dataset == "bottle" else dataset)
    assert result["llm_calls"] == 0


def test_refine_tep_does_not_turn_eight_candidate_recommendation_into_hard_limit(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.txt"
    source.write_text("仅用于调用者合同测试，不是工业诊断证据。")
    units = material_parser.parse_material(source, source_id="caller-test", scenario="tep").units
    assertion = {
        "text": "测试用数值条件，非生产规则",
        "origin": "declared_demo_heuristic",
        "source_unit_id": units[0].unit_id,
        "parameter_origin": "declared_demo_heuristic",
    }
    blueprint = {
        "title": "调用者合同",
        "signatures": [
            {
                "signature_key": "caller_fixture",
                "label": "测试过程现象",
                "context_external_id": "Tennessee Eastman Process",
                "conditions": [
                    {
                        "label": "测试均值偏移",
                        "feature_id": "statistics.mean_z",
                        "op": "abs_gte",
                        "operand": {"kind": "number", "number": 2.0, "unit": "1"},
                        "subject_external_id": "xmeas_9",
                        "assertion": assertion,
                    }
                ],
                "causes": [
                    {
                        "candidate_key": "test_candidate",
                        "label": "测试候选",
                        "mechanism_key": "test_mechanism",
                        "mechanism_label": "测试机制",
                        "assertion": assertion,
                    }
                ],
                "assertion": assertion,
            }
        ],
    }
    original = tmp_path / "original"
    original.mkdir()
    (original / "proposal-1.txt").write_text(json.dumps(blueprint))
    (original / "source_units.json").write_text(
        json.dumps({"units": [u.model_dump(mode="json") for u in units]})
    )
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    captured = []

    def capture_compile(source_units, capability, **kwargs):
        captured.append((source_units, capability, kwargs))
        return SimpleNamespace(
            nodes=[], edges=[], knowledge=SimpleNamespace(hypotheses=[], observable_definitions=[])
        )

    monkeypatch.setattr(unified, "compile_unified_knowledge", capture_compile)

    prepare.refine_tep(original, tmp_path / "new-refinement")

    assert len(captured) == 1
    assert captured[0][1].recommended_max_candidates == 8
    assert captured[0][1].max_candidates == 32
    assert captured[0][2]["llm_client"] is None
    assert captured[0][2]["stored_blueprint"].signatures[0].signature_key == "caller_fixture"
    assert captured[0][0][0].unit_id == units[0].unit_id


def test_api_build_uses_server_budget_and_does_not_fallback_after_failure(tmp_path, monkeypatch):
    client = DemoClient("http://unused.invalid", tmp_path / "client")
    captured = []

    def failed_task(label, endpoint, body):
        captured.append((label, endpoint, body))
        return {"status": "failed", "task_id": "test-only-no-server-task"}

    monkeypatch.setattr(
        client, "request", lambda *a, **k: {"materials": [{"material_id": "test-public-source"}]}
    )
    monkeypatch.setattr(client, "task", failed_task)
    try:
        client.build_bottle()
        assert client.state["graphs"] == {}
        assert len(captured) == 1
        assert captured[0][1] == "/api/tasks/material-build"
        assert captured[0][2] == {
            "material_ids": ["test-public-source"],
            "dataset": "mvtec",
            "title": "几何演示规则 → 真实 LLM · 玻璃瓶局部异常",
            "capability_id": "visual-region-v2",
            "enable_when_ready": False,
        }
    finally:
        client.client.close()


def test_completed_insufficient_inference_is_saved_without_positive_fallback(tmp_path, monkeypatch):
    client = DemoClient("http://unused.invalid", tmp_path / "client")
    monkeypatch.setattr(
        client,
        "task",
        lambda *a, **k: {"status": "completed", "result": {"run_id": "test-only-no-server-run"}},
    )
    result = {"outcome": "insufficient_evidence", "top_k_paths": [], "ranked_root_causes": []}
    run = {
        "run_id": "test-only-no-server-run",
        "cases": [{"case_id": "test-case", "evidence_frames": [{}], "results": [result]}],
    }
    monkeypatch.setattr(client, "request", lambda *a, **k: run)
    try:
        client.inference(
            {"sample_id": "bottle-rim-break", "title": "测试"},
            "dedicated-new-source-graph",
            "unified_abduction",
            "evidence",
        )
        saved = client.state["analyses"]["bottle-rim-break-evidence-unified_abduction"]
        assert saved["graph_id"] == "dedicated-new-source-graph"
        assert saved["cases"][0]["results"][0] == {
            "outcome": "insufficient_evidence",
            "path_count": 0,
            "candidates": [],
        }
        assert json.loads((client.output / "state.json").read_text())["analyses"]
    finally:
        client.client.close()
