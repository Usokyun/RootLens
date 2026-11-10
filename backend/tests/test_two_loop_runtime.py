"""Original input to Evidence and native Evidence re-use the same saved reasoning contract."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from test_two_loop_tasks import MemoryStore, finish

from kgtracevis.service import two_loop_runtime as runtime
from kgtracevis.service.two_loop_tasks import TaskManager


def package(name):
    return json.loads(Path(f"data/kg/unified/{name}-working-graph.v2.json").read_text())


def test_raw_process_to_exported_frame_has_identical_rootkgd_result_without_backbone(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    rng = np.random.default_rng(47)
    normal = rng.normal(size=(80, 52))
    sequence = rng.normal(size=(60, 52))
    sequence[:, 9] += 8
    sequence[:, 50] += 8
    normal_path, sequence_path = tmp_path / "normal.dat", tmp_path / "sequence.dat"
    np.savetxt(normal_path, normal)
    np.savetxt(sequence_path, sequence)
    manager = TaskManager(MemoryStore())
    manager.handlers["inference"] = runtime.infer
    request = {
        "input_mode": "process",
        "input_path": str(sequence_path),
        "reference_path": str(normal_path),
        "windows": [[1, 30]],
        "title": "原始窗口",
        "graph_snapshot": package("tep"),
        "reasoner_id": "tep_rootkgd",
        "top_k": 5,
    }
    task = finish(manager, manager.submit("inference", request, title=request["title"]))
    assert task["status"] == "completed", task["error"]
    original = manager.store.analyses[task["result"]["run_id"]]
    assert original["cases"][0]["results"][0]["ranked_root_causes"]
    assert len(original["cases"][0]["process_trends"]) == 52
    diagnostics = original["cases"][0]["results"][0]["authoring_diagnostics"]
    assert diagnostics["grouping_basis"] == "actual_structural_projection"
    assert diagnostics["evidence_usage"]["score_input_observation_count"] == 52
    reimport = {
        **request,
        "input_mode": "evidence",
        "input_path": original["artifacts"]["evidence-frames.json"],
        "title": "Frame复算",
    }
    second = finish(manager, manager.submit("inference", reimport, title=reimport["title"]))
    assert second["status"] == "completed", second["error"]
    repeated = manager.store.analyses[second["result"]["run_id"]]
    assert original["run_id"] != repeated["run_id"]
    assert original["cases"][0]["results"] == repeated["cases"][0]["results"]
    assert original["cases"][0]["process_trends"] == repeated["cases"][0]["process_trends"]
    manager.executor.shutdown()


def test_native_frame_never_reads_unmanaged_local_media_uri(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    frame = json.loads(Path("data/examples/unified/mvtec-chipped.json").read_text())
    secret = tmp_path / "private-image.png"
    Image.new("RGB", (20, 20), (255, 0, 0)).save(secret)
    next(a for a in frame["assets"] if a["asset_id"] == "image")["uri"] = str(secret)
    input_path = tmp_path / "frame.json"
    input_path.write_text(json.dumps(frame))
    manager = TaskManager(MemoryStore())
    manager.handlers["inference"] = runtime.infer
    request = {
        "input_mode": "evidence",
        "input_path": str(input_path),
        "title": "只有统计",
        "graph_snapshot": package("bottle"),
        "reasoner_id": "unified_abduction",
    }
    task = finish(manager, manager.submit("inference", request, title=request["title"]))
    assert task["status"] == "completed", task["error"]
    run = manager.store.analyses[task["result"]["run_id"]]
    assert run["cases"][0]["results"][0]["ranked_root_causes"]
    diagnostics = run["cases"][0]["results"][0]["authoring_diagnostics"]
    assert diagnostics["grouping_basis"] == "reachable_expectation_conditions"
    assert diagnostics["grouping_status"] == "available"
    assert run["cases"][0]["media_status"] == "not_attached"
    assert run["cases"][0]["media_note"] == "只有统计与引用，原始媒体未附带。"
    assert run["cases"][0]["visual_evidence"] == []
    assert not run["media_assets"]
    manager.executor.shutdown()


def test_process_matrix_accepts_canonical_csv_but_rejects_ambiguous_axis(tmp_path):
    from kgtracevis.core.rootkgd_reasoner import CHANNELS

    canonical = tmp_path / "canonical.csv"
    canonical.write_text(",".join(CHANNELS) + "\n" + ",".join(["1"] * 52) + "\n")
    assert runtime._process_matrix(canonical, tmp_path / "converted.dat").is_file()
    ambiguous = tmp_path / "unknown.csv"
    ambiguous.write_text("temperature,pressure\n1,2\n")
    with pytest.raises(ValueError, match="标题"):
        runtime._process_matrix(ambiguous, tmp_path / "no-output.dat")


def test_multi_wafer_raw_grid_and_native_reimport_keep_distinct_managed_media(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    nearfull, normal = [[2] * 21 for _ in range(21)], [[1] * 21 for _ in range(21)]
    records = [
        {
            "case_id": identity,
            "dataset": "wafer",
            "adapter": "wm811k",
            "wafer_map": grid,
            "predicted_pattern": "nearfull",
        }
        for identity, grid in (("nearfull", nearfull), ("normal", normal))
    ]
    monkeypatch.setattr(runtime, "_wafer_records", lambda *args: records)
    input_path = tmp_path / "grids.jsonl"
    input_path.write_text("public raw grids")
    manager = TaskManager(MemoryStore())
    manager.handlers["inference"] = runtime.infer
    request = {
        "input_mode": "wafer",
        "input_path": str(input_path),
        "title": "不同晶圆",
        "graph_snapshot": package("wafer"),
        "reasoner_id": "unified_abduction",
    }
    task = finish(manager, manager.submit("inference", request, title=request["title"]))
    assert task["status"] == "completed", task["error"]
    original = manager.store.analyses[task["result"]["run_id"]]
    assert [c["wafer_map"] for c in original["cases"]] == [nearfull, normal]
    assert all(c["media_status"] == "available" for c in original["cases"])
    native = {
        **request,
        "input_mode": "evidence",
        "input_path": original["artifacts"]["evidence-frames.json"],
    }
    repeated = finish(manager, manager.submit("inference", native, title="Frame复算"))
    assert repeated["status"] == "completed", repeated["error"]
    restored = manager.store.analyses[repeated["result"]["run_id"]]
    assert [c["wafer_map"] for c in restored["cases"]] == [nearfull, normal]
    assert all(c["visual_evidence"] for c in restored["cases"])
    manager.executor.shutdown()
