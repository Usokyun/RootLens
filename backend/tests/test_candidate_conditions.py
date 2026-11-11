"""Candidate-local authoring uses actual typed Frames and existing persistent editor paths."""

import json

import pytest
from fastapi.testclient import TestClient
from graded_fixtures import public_release, without_grades
from test_two_loop_tasks import MemoryStore, finish
from test_unified_integration import storage as storage

from kgtracevis.core.candidate_discriminability import analyze_candidate_discriminability
from kgtracevis.core.rootkgd_reasoner import CHANNELS, RootKGDReasoner
from kgtracevis.core.unified_reasoner import UnifiedReasoner
from kgtracevis.schema.unified_knowledge import KnowledgePackage
from kgtracevis.service import two_loop_api as api
from kgtracevis.service import two_loop_runtime as runtime
from kgtracevis.service.api import create_app
from kgtracevis.service.candidate_conditions import (
    CandidateConditionRequest,
    add_condition,
    condition_options,
    list_conditions,
    remove_condition,
)
from kgtracevis.service.two_loop_tasks import TaskManager

IDENTITY = "candidate-condition:" + "0" * 32


def actual_inputs():
    package, frames = public_release("tep")
    package["knowledge"] = without_grades(package["knowledge"])
    return package, frames[1]


@pytest.fixture
def condition_api(storage, tmp_path, monkeypatch):
    client = TestClient(create_app())
    package, frames = public_release("tep")
    frame = frames[1]
    response = client.post("/api/kg/working-graphs/import", json=package)
    assert response.status_code == 200, response.text
    graph_id = response.json()["graph_id"]
    assert (
        client.post(f"/api/kg/working-graphs/{graph_id}/enable", json={"enabled": True}).status_code
        == 200
    )
    manager = TaskManager(MemoryStore())
    manager.handlers["inference"] = runtime.infer
    monkeypatch.setattr(api, "task_manager", lambda: manager)
    monkeypatch.setattr(api, "TASK_ROOT", tmp_path / "tasks")
    monkeypatch.setattr(runtime, "TASK_ROOT", tmp_path / "tasks")
    yield client, graph_id, frame, manager
    manager.executor.shutdown()


def run_frame(client, graph_id, frame, manager):
    response = client.post(
        "/api/tasks/inference",
        data={"graph_id": graph_id, "input_mode": "evidence", "top_k": 8},
        files={"file": ("frame.json", json.dumps(frame).encode(), "application/json")},
    )
    assert response.status_code == 202, response.text
    task = finish(manager, response.json())
    assert task["status"] == "completed", task["error"]
    return client.get("/api/analyses/" + task["result"]["run_id"]).json()


def request_for(
    knowledge, frame, *, feature="statistics.std_z", op="gte", passing=False, channel="xmv_10"
):
    result = UnifiedReasoner(knowledge).analyze(frame, top_k=8)
    candidate = result["ranked_root_causes"][0]["candidate_id"]
    observation = next(
        o
        for o in frame["observations"]
        if o["subject_id"] == "variable:" + channel and o["feature_id"] == feature
    )
    value = observation["value"]["number"]
    threshold = value + ((0.1 if passing else -0.1) if op == "lte" else (-0.1 if passing else 0.1))
    entity = next(
        b["target_id"]
        for b in knowledge["subject_bindings"]
        if b["namespace"] == "tep_braatz.channel" and b["external_id"] == channel
    )
    return {
        "candidate_id": candidate,
        "label": "单候选响应检查",
        "feature_id": feature,
        "op": op,
        "operand": {"kind": "number", "number": threshold, "unit": observation["value"]["unit"]},
        "subject_entity_id": entity,
        "mode": "necessary",
        "description": "测试用作者条件，不声称工业机理。",
    }


def test_create_save_analyze_delete_restores_knowledge_and_keeps_old_run(condition_api, storage):
    client, graph_id, frame, manager = condition_api
    route = f"/api/kg/working-graphs/{graph_id}/package"
    original = client.get(route).json()
    baseline = run_frame(client, graph_id, frame, manager)
    options = condition_options(graph_id)
    assert len(options["subjects"]) == 52 and options["zones"] == []
    feature = next(f for f in options["features"] if f["feature_id"] == "statistics.slope_z")
    assert feature["unit"] == "1/sample" and feature["subject_kind"] == "variable"
    assert feature["allowed_operators"] == ["gte", "lte", "abs_gte", "eq"]
    assert not any(f["value_kind"] == "array_ref" for f in options["features"])
    request = request_for(original["knowledge"], frame)
    edited = add_condition(
        KnowledgePackage.model_validate(original["knowledge"]),
        "tep",
        CandidateConditionRequest.model_validate(request),
        IDENTITY,
    )
    (condition,) = list_conditions(edited)
    assert condition["can_delete"] and condition["candidate_id"] == request["candidate_id"]
    # Full-package editing is explicit: include a reviewed slot as part of the same save.
    modified = {**original, "knowledge": edited.model_dump(mode="json")}
    policy = modified["knowledge"]["graded_policy"]
    policy["groups"][0]["slots"].append(
        {
            "slot_id": "candidate-local-check",
            "predicate_ids": [condition["predicate_id"]],
            "weight": 0.5,
        }
    )
    response = client.put(route, json=modified)
    assert response.status_code == 200, response.text
    modified = client.get(route).json()
    assert modified["knowledge"]["graded_policy"] == policy
    assert modified["knowledge"]["mechanisms"] == original["knowledge"]["mechanisms"]
    assert modified["knowledge"]["effect_rules"] == original["knowledge"]["effect_rules"]
    assert modified["knowledge"]["expectation_rules"][-1]["from_id"] == request["candidate_id"]
    assert modified["knowledge"]["source_assertions"][-1]["origin"] == "declared_demo_heuristic"
    changed = run_frame(client, graph_id, frame, manager)
    result = changed["cases"][0]["results"][0]
    row = next(
        r for r in result["candidate_evaluations"] if r["candidate_id"] == request["candidate_id"]
    )
    assert row["status"] == "ruled_out" and row["eligible_for_ranking"] is False
    assert all(
        request["candidate_id"] not in g["candidate_ids"]
        for g in result["authoring_diagnostics"]["equivalence_groups"]
    )
    assert client.get("/api/analyses/" + baseline["run_id"]).json() == baseline
    # Deleting a predicate while leaving its slot behind is not a valid full package.
    stale = {**original, "knowledge": {**original["knowledge"], "graded_policy": policy}}
    assert client.put(route, json=stale).status_code == 422
    assert client.get(route).json() == modified
    assert client.put(route, json=original).status_code == 200
    assert client.get(route).json() == original
    restored = run_frame(client, graph_id, frame, manager)
    assert restored["cases"][0]["results"] == baseline["cases"][0]["results"]
    assert len(list(storage[2].glob("backup_*.json"))) == 2


@pytest.mark.parametrize(
    "feature,op",
    [
        ("statistics.mean_z", "gte"),
        ("statistics.mean_z", "lte"),
        ("statistics.std_z", "gte"),
        ("statistics.slope_z", "gte"),
    ],
)
def test_signed_std_slope_conditions_are_candidate_local_and_use_actual_grounding(feature, op):
    package, frame = actual_inputs()
    knowledge = KnowledgePackage.model_validate(package["knowledge"])
    request = request_for(package["knowledge"], frame, feature=feature, op=op, passing=True)
    identity = "candidate-condition:" + "1" * 32
    changed = add_condition(
        knowledge, "tep", CandidateConditionRequest.model_validate(request), identity
    )
    result = UnifiedReasoner(changed).analyze(frame)
    fact = next(f for f in result["grounded_facts"] if f["predicate_id"] == identity + ":predicate")
    assert fact["value"] is True
    checks = {r["candidate_id"]: r["expectation_checks"] for r in result["candidate_evaluations"]}
    assert (
        sum(
            any(c["rule_id"] == identity + ":expectation" for c in rows) for rows in checks.values()
        )
        == 1
    )
    assert any(c["rule_id"] == identity + ":expectation" for c in checks[request["candidate_id"]])
    assert remove_condition(changed, identity) == knowledge


def test_anomaly_false_cannot_be_bypassed_by_a_true_new_numeric_condition():
    package, frame = actual_inputs()
    request = request_for(package["knowledge"], frame, passing=True)
    changed = add_condition(
        KnowledgePackage.model_validate(package["knowledge"]),
        "tep",
        CandidateConditionRequest.model_validate(request),
        "candidate-condition:" + "2" * 32,
    )
    # Contract counterexample: hold all numeric measurements fixed, change only the explicit gate.
    next(o for o in frame["observations"] if o["feature_id"] == "detection.anomaly_present")[
        "value"
    ]["boolean"] = False
    result = UnifiedReasoner(changed).analyze(frame)
    assert (
        next(
            f
            for f in result["grounded_facts"]
            if f["predicate_id"].endswith("2" * 32 + ":predicate")
        )["value"]
        is True
    )
    assert not result["ranked_root_causes"]


def test_modes_preserve_existing_conflict_and_necessary_semantics():
    package, frame = actual_inputs()
    request = request_for(package["knowledge"], frame)
    rows = {}
    for mode in ("necessary", "expected", "possible"):
        changed = add_condition(
            KnowledgePackage.model_validate(package["knowledge"]),
            "tep",
            CandidateConditionRequest.model_validate({**request, "mode": mode}),
            "candidate-condition:" + "5" * 32,
        )
        result = UnifiedReasoner(changed).analyze(frame)
        row = next(
            r
            for r in result["candidate_evaluations"]
            if r["candidate_id"] == request["candidate_id"]
        )
        check = next(
            c for c in row["expectation_checks"] if c["rule_id"].endswith("5" * 32 + ":expectation")
        )
        assert check["observed_value"] is False
        assert bool(check["conflicting_fact_ids"]) == (mode != "possible")
        rows[mode] = row
    assert rows["necessary"]["status"] == "ruled_out"
    assert (
        rows["expected"]["scoring_details"]["conflict_loss"]
        > rows["possible"]["scoring_details"]["conflict_loss"]
    )


@pytest.mark.parametrize(
    "dataset,feature,operand,zone",
    [
        (
            "mvtec",
            "appearance.semantic_candidates",
            {"kind": "category", "category": "distinct-appearance"},
            None,
        ),
        (
            "wafer",
            "spatial.failure_density",
            {"kind": "number", "number": 0.2, "unit": "1"},
            "edge",
        ),
        ("tep", "residual.energy", {"kind": "number", "number": 0.1, "unit": "1"}, None),
    ],
)
def test_all_three_scene_scopes_create_and_remove_only_owned_nodes(dataset, feature, operand, zone):
    package, _ = public_release(dataset)
    original = KnowledgePackage.model_validate(without_grades(package["knowledge"]))
    source = original.source_assertions[0].assertion_id
    request = CandidateConditionRequest(
        candidate_id=original.hypotheses[0].hypothesis_id,
        label="独立场景条件",
        feature_id=feature,
        op="candidate_contains" if operand["kind"] == "category" else "gte",
        operand=operand,
        zone=zone,
        source_assertion_ids=[source],
    )
    changed = add_condition(original, dataset, request, IDENTITY)
    (condition,) = list_conditions(changed)
    assert condition["subject_entity_id"] is None
    assert condition["zone"] == zone and condition["source_assertion_ids"] == [source]
    assert condition["anomaly_gate_id"] in {p.predicate_id for p in original.observable_definitions}
    assert remove_condition(changed, IDENTITY) == original


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"candidate_id": "unknown"}, "目标候选"),
        ({"feature_id": "statistics.unmeasured"}, "目录"),
        ({"subject_entity_id": "new-variable"}, "已绑定"),
        ({"zone": "invented-zone"}, "范围"),
        ({"source_assertion_ids": ["invented-source"]}, "来源"),
        ({"operand": {"kind": "number", "number": 1.0, "unit": "wrong"}}, "units differ"),
    ],
)
def test_invalid_authoring_keeps_the_original_knowledge(change, expected):
    package, frame = actual_inputs()
    before = KnowledgePackage.model_validate(package["knowledge"])
    request = {**request_for(package["knowledge"], frame), **change}
    with pytest.raises(ValueError, match=expected):
        add_condition(before, "tep", CandidateConditionRequest.model_validate(request), IDENTITY)
    assert before == KnowledgePackage.model_validate(package["knowledge"])


@pytest.mark.parametrize(
    "feature,operand,op",
    [
        ("detection.anomaly_present", {"kind": "boolean", "boolean": True}, "bool_eq"),
        ("appearance.defect_present", {"kind": "boolean", "boolean": True}, "bool_eq"),
        ("residual.normal_limit", {"kind": "number", "number": 0.1, "unit": "1"}, "gte"),
    ],
)
def test_operator_catalog_rejects_presence_or_background_only_conditions(
    condition_api, feature, operand, op
):
    client, graph_id, _, _ = condition_api
    dataset = "mvtec" if feature == "appearance.defect_present" else "tep"
    if dataset == "mvtec":
        package, _ = public_release(dataset)
        imported = client.post("/api/kg/working-graphs/import", json=package)
        assert imported.status_code == 200, imported.text
        graph_id = imported.json()["graph_id"]
    assert feature not in {f["feature_id"] for f in condition_options(graph_id)["features"]}
    before = client.get(f"/api/kg/working-graphs/{graph_id}/package").json()
    original = KnowledgePackage.model_validate(before["knowledge"])
    request = CandidateConditionRequest(
        candidate_id=original.hypotheses[0].hypothesis_id,
        label="拒绝泛门控充分替代",
        feature_id=feature,
        operand=operand,
        op=op,
    )
    with pytest.raises(ValueError, match="不是候选区分条件"):
        add_condition(original, dataset, request, IDENTITY)


def test_shared_dependency_blocks_delete_and_foreign_rule_is_not_a_bundle():
    package, frame = actual_inputs()
    original = KnowledgePackage.model_validate(package["knowledge"])
    request = CandidateConditionRequest.model_validate(request_for(package["knowledge"], frame))
    changed = add_condition(original, "tep", request, IDENTITY)
    rule = changed.expectation_rules[-1].model_copy(
        update={
            "rule_id": "another-shared-expectation",
            "from_id": next(
                h.hypothesis_id
                for h in original.hypotheses
                if h.hypothesis_id != request.candidate_id
            ),
        }
    )
    changed.expectation_rules.append(rule)
    assert list_conditions(changed)[0]["can_delete"] is False
    with pytest.raises(ValueError, match="共享依赖"):
        remove_condition(changed, IDENTITY)
    with pytest.raises(ValueError, match="只能撤销"):
        remove_condition(changed, "an-existing-rule")


def test_missing_gate_rejects_only_new_authoring_not_original_reasoning():
    package, frame = actual_inputs()
    request = request_for(package["knowledge"], frame)
    for predicate in package["knowledge"]["observable_definitions"]:
        if predicate["feature_id"] == "detection.anomaly_present":
            predicate["operand"]["boolean"] = False
    knowledge = KnowledgePackage.model_validate(package["knowledge"])
    assert UnifiedReasoner(knowledge).analyze(frame)["case_id"] == frame["case_id"]
    with pytest.raises(ValueError, match="异常前置条件"):
        add_condition(
            knowledge,
            "tep",
            CandidateConditionRequest.model_validate(request),
            "candidate-condition:" + "3" * 32,
        )


def test_rootkgd_uses_actual_structure_not_threshold_truth_or_expectation_mode():
    package, frame = actual_inputs()
    knowledge = KnowledgePackage.model_validate(package["knowledge"])
    request = request_for(package["knowledge"], frame)
    base = RootKGDReasoner(knowledge).analyze(frame)
    selected = next(
        r for r in base["candidate_evaluations"] if r["candidate_id"] == request["candidate_id"]
    )
    existing_channel = next(
        c
        for c, value in zip(
            CHANNELS, selected["scoring_details"]["propagated_channel_vector"], strict=True
        )
        if value > 0
    )
    same_request = request_for(package["knowledge"], frame, channel=existing_channel)
    same_channel = add_condition(
        knowledge,
        "tep",
        CandidateConditionRequest.model_validate(same_request),
        "candidate-condition:" + "6" * 32,
    )
    same_result = RootKGDReasoner(same_channel).analyze(frame)
    same_row = next(
        r
        for r in same_result["candidate_evaluations"]
        if r["candidate_id"] == request["candidate_id"]
    )
    # A redundant upstream expectation is provenance, not a new physical
    # shortcut to an already-reachable channel.
    assert (
        same_row["scoring_details"]["propagated_channel_vector"]
        == selected["scoring_details"]["propagated_channel_vector"]
    )
    channel = next(
        c
        for c, value in zip(
            CHANNELS, selected["scoring_details"]["propagated_channel_vector"], strict=True
        )
        if value == 0
    )
    request = request_for(package["knowledge"], frame, channel=channel)
    changed = add_condition(
        knowledge,
        "tep",
        CandidateConditionRequest.model_validate(request),
        "candidate-condition:" + "4" * 32,
    )
    first = RootKGDReasoner(changed).analyze(frame)
    row = next(
        r for r in first["candidate_evaluations"] if r["candidate_id"] == request["candidate_id"]
    )
    assert row["scoring_details"]["propagated_channel_vector"][CHANNELS.index(channel)] > 0
    changed.observable_definitions[-1].operand.number = 1e6
    changed.expectation_rules[-1].mode = "possible"
    second = RootKGDReasoner(changed).analyze(frame)
    assert [(r["score"], r["scoring_details"]) for r in first["candidate_evaluations"]] == [
        (r["score"], r["scoring_details"]) for r in second["candidate_evaluations"]
    ]
    report = analyze_candidate_discriminability(changed, frame, second, reasoner_id="tep_rootkgd")
    assert report["grouping_basis"] == "actual_structural_projection"
    assert all(c["condition_checks_used_for_score"] is False for c in report["candidate_checks"])
