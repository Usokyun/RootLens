"""Demo clients preserve authoring budgets and truthful insufficient outcomes."""

import json
from types import SimpleNamespace

import pytest

from kgtracevis.source_kg_compiler import llm, material_parser, unified
from scripts import prepare_two_loop_demo as prepare
from scripts.prepare_two_loop_demo_api import DemoClient


@pytest.mark.parametrize(
    "dataset,capability_id,recommended,hard_limit",
    [
        ("bottle", "visual-region-v2", 16, 32),
        ("tep", "process-window-v2", 8, 32),
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
            "title": "原厂PDF → 真实LLM · 双闭环玻璃缺损知识",
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
