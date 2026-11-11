"""Current demo clients use the published cases and never fabricate matching media."""

import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pandas as pd
import pytest

from scripts import _wm811k_table as wafer_table
from scripts import prepare_two_loop_demo as prepare
from scripts import prepare_two_loop_demo_api as api_demo
from scripts.prepare_two_loop_demo_api import DemoClient

MVTEC = "mvtec-bottle-006-graded"
TEP_D04 = "tep-d04-graded"
TEP_D05 = "tep-d05-graded"
WAFER = "wm811k-248536-31707-graded"


def test_prepare_without_download_only_checks_the_shipped_assets(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("read-only check must not prepare inputs, fit a model, or write")

    for method in ("prepare_bottle_checkpoint", "prepare_tep", "prepare_wafer", "write_json"):
        monkeypatch.setattr(prepare, method, forbidden)
    manifest = prepare.prepare(dataset="mvtec")
    (demo,) = manifest["demos"]
    (sample,) = demo["samples"]
    assert demo["id"] == "mvtec-graded"
    assert sample["sample_id"] == MVTEC and sample["recommended"]
    assert sample["raw_options"] == {
        "object_name": "bottle",
        "model_preset": "patchcore",
        "semantic_mode": "disabled",
    }
    assert "normal_reference" not in sample
    assert all("asset_id" not in model and "path" not in model for model in demo["models"])
    assert sample["raw_input"]["path"].endswith("graded_rca/mvtec/sample_006.png")
    report = prepare.check(manifest)
    assert not report["missing_assets"] and report["validated"][0]["frames"] == 1


@pytest.mark.parametrize("payload,valid", [(b"exact-checkpoint", True), (b"partial", False)])
def test_bottle_checkpoint_publish_is_atomic(tmp_path, monkeypatch, payload, valid):
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    monkeypatch.setattr(prepare, "RUNTIME", tmp_path / "runs/graded_rca_demo")
    monkeypatch.setattr(prepare.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(payload))
    expected = b"exact-checkpoint"
    model = {
        "local_path": "runs/graded_rca_demo/models/bottle.ckpt",
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


def test_release_three_recommendations_four_samples_and_exact_frame_sets():
    manifest = prepare.read_manifest()
    expected = {
        "mvtec": {MVTEC: 1},
        "tep": {TEP_D04: 3, TEP_D05: 1},
        "wafer": {WAFER: 2},
    }
    assert len(manifest["demos"]) == len(expected)
    for demo in manifest["demos"]:
        scene = demo["dataset"]
        assert demo["id"] == f"{scene}-graded"
        assert [s["sample_id"] for s in demo["samples"] if s["recommended"]] == [
            next(iter(expected[scene]))
        ]
        assert {s["sample_id"] for s in demo["samples"]} == set(expected[scene])
        for asset in [*demo["materials"], demo["working_graph"]]:
            assert asset["path"].startswith(f"data/demo/graded_rca/{scene}/")
            assert (prepare.ROOT / asset["path"]).stat().st_size == asset["size_bytes"]
        for sample in demo["samples"]:
            identity = sample["sample_id"]
            assert sample["reasoner_ids"] == (
                ["graded_abduction", "tep_rootkgd"] if identity == TEP_D04 else ["graded_abduction"]
            )
            frames = prepare.frames_from_asset(sample["evidence"])
            assert len(frames) == expected[scene][identity]
            assert all(f.source_dataset == scene for f in frames)
            if scene == "tep":
                support = sample["supporting_assets"]
                assert {
                    a["frame_case_id"] for a in support if a.get("case_asset_id") == "window"
                } == {f.case_id for f in frames}
                assert [
                    [scope.sample_start, scope.sample_end]
                    for f in frames
                    for scope in f.scopes
                    if scope.scope_id == f.task.scope_id
                ] == sample["raw_options"]["windows"]
                assert sample["raw_input"]["sha256"] and sample["normal_reference"]["sha256"]
            if scene == "wafer":
                assert sample["raw_input"]["storage_scope"] == "local_runtime"
                rows = prepare.wafer_rows(sample, frames)
                assert [(r["row_id"], r["shape"]) for r in rows] == [
                    ("248536", [38, 38]),
                    ("31707", [63, 62]),
                ]
                support = prepare.attachment_targets(sample, {(f.case_id, "grid") for f in frames})
                assert len(set(support.values())) == 2
                assert '"waferMap"' not in (prepare.ROOT / sample["evidence"]["path"]).read_text()
    report = prepare.check(manifest)
    assert not report["missing_assets"]
    assert {item["sample_id"]: item["frames"] for item in report["validated"]} == {
        key: count for scene in expected.values() for key, count in scene.items()
    }


def test_tep_preparation_uses_each_pin_and_the_shared_d00_once(monkeypatch):
    (demo,) = prepare.read_manifest("tep")["demos"]
    seen, hydrated = [], []
    monkeypatch.setattr(prepare, "prepare_transfer", lambda asset, **kw: seen.append(asset["path"]))
    monkeypatch.setattr(
        prepare,
        "hydrate_process_support",
        lambda frames, sample: hydrated.append((sample["sample_id"], len(frames))),
    )
    prepare.prepare_tep(demo)
    assert [Path(path).name for path in seen] == [
        "sequence_04.dat",
        "normal_reference.dat",
        "sequence_05.dat",
    ]
    assert hydrated == [(TEP_D04, 3), (TEP_D05, 1)]


def test_wafer_preparation_matches_each_saved_frame_and_refuses_a_swapped_grid(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    monkeypatch.setattr(prepare, "RUNTIME", tmp_path / "runs/graded_rca_demo")
    first, second = [[0, 1], [2, 1]], [[1, 2, 0], [2, 1, 2]]
    table = pd.DataFrame(
        {
            "waferMap": [np.array(second), np.array([[1]]), np.array(first)],
            "failureType": ["ignore", "extra row", "never copy"],
        },
        index=[31707, 2, 248536],
    )
    payloads = {"table": b"example-pinned-table", "model": b"example-pinned-weight"}

    def read_verified_table(handle):
        assert handle.read() == payloads["table"]
        return SimpleNamespace(load=lambda: table)

    monkeypatch.setattr(wafer_table, "DataOnlyUnpickler", read_verified_table)

    def asset(label):
        raw = payloads[label]
        return {
            "source_url": label,
            "local_path": f"runs/graded_rca_demo/{label}",
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr(
        prepare.urllib.request, "urlopen", lambda url, **_: io.BytesIO(payloads[url])
    )
    runtime = "runs/graded_rca_demo"
    cases = [("248536", first), ("31707", second)]
    rows = [
        {
            "row_id": identity,
            "shape": [len(grid), len(grid[0])],
            "frame_case_id": f"wm811k_{identity}/query/grid",
        }
        for identity, grid in cases
    ]
    frames = [
        SimpleNamespace(
            case_id=row["frame_case_id"],
            assets=[SimpleNamespace(asset_id="grid", shape=row["shape"])],
        )
        for row in rows
    ]
    monkeypatch.setattr(prepare, "frames_from_asset", lambda _: frames)
    raw = f"{runtime}/wafer.jsonl"
    files = [f"{runtime}/grid-{row['row_id']}.json" for row in rows]
    demo = {
        "models": [asset("model")],
        "samples": [
            {
                "raw_input": {"path": raw},
                "evidence": {},
                "raw_source": {**asset("table"), "rows": rows},
                "supporting_assets": [
                    {"frame_case_id": row["frame_case_id"], "case_asset_id": "grid", "path": file}
                    for row, file in zip(rows, files, strict=True)
                ],
            }
        ],
    }
    prepare.prepare_wafer(demo)
    actual = (tmp_path / raw).read_bytes()
    assert [json.loads(line) for line in actual.splitlines()] == [
        {"wafer_id": i, "case_id": f"wm811k_{i}", "waferMap": grid} for i, grid in cases
    ]
    assert [json.loads((tmp_path / file).read_text()) for file in files] == [first, second]
    swapped = tmp_path / files[1]
    swapped.write_text(json.dumps(first))
    with pytest.raises(ValueError, match="不是同一片晶圆"):
        prepare.prepare_wafer(demo)
    assert (tmp_path / raw).read_bytes() == actual
    assert json.loads(swapped.read_text()) == first


def test_api_runner_rejects_previous_catalog_and_incompatible_choice_before_writes():
    library = prepare.read_manifest()
    kwargs = {"selected": set(), "all_samples": False, "reasoner": "graded_abduction"}
    assert [d["samples"][0]["sample_id"] for d in api_demo.select_demos(library, **kwargs)] == [
        MVTEC,
        TEP_D04,
        WAFER,
    ]
    with pytest.raises(ValueError, match="不支持推理器"):
        api_demo.select_demos(
            library, selected={TEP_D05}, all_samples=False, reasoner="tep_rootkgd"
        )
    previous = deepcopy(library)
    previous["demos"][0]["samples"][0]["sample_id"] = "bottle-rim-break"
    with pytest.raises(ValueError, match="未提交任务"):
        api_demo.select_demos(previous, **kwargs)


def test_api_demo_delegates_graph_install_to_the_shared_managed_endpoint(tmp_path, monkeypatch):
    client = DemoClient("http://unused.invalid", tmp_path / "client")
    calls = []

    def request(method, path, **kwargs):
        assert not kwargs  # The managed endpoint consumes no package body.
        calls.append((method, path))
        already = "/existing/" in path
        return {
            "state": "ready",
            "available": True,
            "graph_id": "exact-id" if already else "new-graph",
            "action": "already_ready" if already else "installed",
        }

    monkeypatch.setattr(client, "request", request)
    try:
        demos = [{"id": "existing"}, {"id": "mvtec-graded"}]
        client.import_graphs(demos)
        client.import_graphs(demos)  # Resume does not repeat the recorded operation.
        assert client.state["graphs"] == {"existing": "exact-id", "mvtec-graded": "new-graph"}
        assert calls == [
            ("POST", "/api/demo-library/existing/working-graph"),
            ("POST", "/api/demo-library/mvtec-graded/working-graph"),
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
        "graph_id": "dedicated-new-source-graph",
        "reasoner_id": "graded_abduction",
        "input_mode": "evidence",
        "cases": [{"case_id": "test-case", "evidence_frames": [{}], "results": [result]}],
    }
    monkeypatch.setattr(client, "request", lambda *a, **k: run)
    try:
        client.inference(
            {"sample_id": "mvtec-bottle-006-graded", "title": "测试"},
            "dedicated-new-source-graph",
            "graded_abduction",
            "evidence",
        )
        saved = client.state["analyses"]["mvtec-bottle-006-graded-evidence-graded_abduction"]
        assert saved["graph_id"] == "dedicated-new-source-graph"
        assert saved["cases"][0]["results"][0] == {
            "outcome": "insufficient_evidence",
            "path_count": 0,
            "candidates": [],
        }
        assert json.loads((client.output / "state.json").read_text())["analyses"]
    finally:
        client.client.close()
