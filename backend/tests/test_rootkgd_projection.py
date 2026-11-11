"""Logical expression rewrites do not become extra physical propagation votes."""

import copy

import pytest
from graded_fixtures import public_release, without_grades

from kgtracevis.core.rootkgd_reasoner import CHANNELS, RootKGDReasoner
from kgtracevis.kg.unified_compiler import KnowledgeProgram
from kgtracevis.schema.unified_knowledge import KnowledgePackage
from kgtracevis.service.candidate_conditions import CandidateConditionRequest, add_condition


@pytest.fixture
def inputs():
    package, frames = public_release("tep")
    return without_grades(package["knowledge"]), frames[1]


def numeric_signature(result):
    return {
        "outcome": result["outcome"],
        "rows": [
            (r["candidate_id"], r["score"], r["scoring_details"])
            for r in result["candidate_evaluations"]
        ],
        "ranking": [
            (r["candidate_id"], r["rank"], r["score"]) for r in result["ranked_root_causes"]
        ],
        "coverage": result["propagation"]["graph_channel_coverage"],
    }


def selected_rule(knowledge, result):
    program = KnowledgeProgram(knowledge)
    candidate = result["ranked_root_causes"][0]["candidate_id"]
    return candidate, program.hypothesis_world(candidate)[3][0]


@pytest.mark.parametrize("rewrite", ["duplicate_pattern", "split_and", "extra_statistic"])
def test_host_channel_set_is_invariant_to_logical_spelling(inputs, rewrite):
    knowledge, frame = inputs
    baseline = RootKGDReasoner(knowledge).analyze(frame, top_k=8)
    _, rule = selected_rule(knowledge, baseline)
    changed = copy.deepcopy(knowledge)
    pattern = next(p for p in changed["pattern_definitions"] if p["pattern_id"] == rule.pattern_id)
    if rewrite == "duplicate_pattern":
        duplicate = {
            **copy.deepcopy(pattern),
            "pattern_id": "p:repr-copy",
            "definition_id": "d:repr-copy",
        }
        changed["pattern_definitions"].append(duplicate)
        changed["expectation_rules"].append(
            {
                **rule.model_dump(mode="json"),
                "rule_id": "r:repr-copy",
                "pattern_id": "p:repr-copy",
            }
        )
    elif rewrite == "split_and":
        program = KnowledgeProgram(knowledge)
        footprint = sorted(program.footprint(rule.pattern_id))
        gates = [
            p for p in footprint if program.observables[p].feature_id == "detection.anomaly_present"
        ]
        atoms = [p for p in footprint if p not in gates]
        assert len(atoms) >= 2
        # Two conjunctive expectation fragments have exactly the same channel
        # footprint; RootKGD does not score their logical form or truth value.
        changed["expectation_rules"] = [
            r for r in changed["expectation_rules"] if r["rule_id"] != rule.rule_id
        ]
        for index, rows in enumerate((atoms[:1], atoms[1:])):
            pid = f"p:repr-split:{index}"
            changed["pattern_definitions"].append(
                {
                    **copy.deepcopy(pattern),
                    "pattern_id": pid,
                    "definition_id": pid + ":definition",
                    "body": {"all": gates + rows},
                }
            )
            changed["expectation_rules"].append(
                {
                    **rule.model_dump(mode="json"),
                    "rule_id": f"r:repr-split:{index}",
                    "pattern_id": pid,
                }
            )
    else:
        program = KnowledgeProgram(knowledge)
        original = next(
            program.observables[p]
            for p in sorted(program.footprint(rule.pattern_id))
            if program.observables[p].subject_selector.kind == "bound_entity"
        )
        duplicate = original.model_dump(mode="json")
        duplicate.update(
            predicate_id="q:extra-stat",
            feature_id="statistics.std_z",
            op="gte",
            operand={"kind": "number", "number": 1e6, "unit": "1"},
        )
        changed["observable_definitions"].append(duplicate)
        pattern["body"] = {"all": [pattern["body"], "q:extra-stat"]}
    actual = RootKGDReasoner(changed).analyze(frame, top_k=8)
    assert numeric_signature(actual) == numeric_signature(baseline)
    assert (
        actual["propagation"]["projection"]["host_channel_edge_count"]
        == baseline["propagation"]["projection"]["host_channel_edge_count"]
    )


def test_upstream_redundant_expectation_merges_contiguous_provenance_not_signal(inputs):
    knowledge, frame = inputs
    original = RootKGDReasoner(knowledge).analyze(frame, top_k=8)
    top = original["ranked_root_causes"][0]
    channel = next(
        c
        for c, value in zip(
            CHANNELS, top["scoring_details"]["propagated_channel_vector"], strict=True
        )
        if value > 0
    )
    entity = next(
        b["target_id"] for b in knowledge["subject_bindings"] if b["external_id"] == channel
    )
    identity = "candidate-condition:" + "8" * 32
    changed = add_condition(
        KnowledgePackage.model_validate(knowledge),
        "tep",
        CandidateConditionRequest(
            candidate_id=top["candidate_id"],
            label="表示等价检查",
            feature_id="statistics.std_z",
            op="gte",
            operand={"kind": "number", "number": 1e6, "unit": "1"},
            subject_entity_id=entity,
        ),
        identity,
    )
    actual = RootKGDReasoner(changed).analyze(frame, top_k=8)
    assert numeric_signature(actual) == numeric_signature(original)
    program = KnowledgeProgram(changed)
    candidate_paths = [p for p in actual["top_k_paths"] if p["nodes"][0] == top["candidate_id"]]
    alternatives = [a for p in candidate_paths for a in p["source_path_alternatives"]]
    assert any(a["expectation_rule_id"] == identity + ":expectation" for a in alternatives)
    for path in actual["top_k_paths"]:
        for witness in [path, *path["source_path_alternatives"]]:
            assert witness["nodes"][0] == path["nodes"][0]
            assert witness["nodes"][-1] == path["nodes"][-1]
            assert witness["source_assertion_ids"]
            for i, view in enumerate(witness["source_edge_views"]):
                edge = program.edges[view["edge_id"]]
                expected = (
                    [edge["tail"], edge["head"]]
                    if view["reverse"]
                    else [edge["head"], edge["tail"]]
                )
                assert witness["nodes"][i : i + 2] == expected


def test_new_unreached_channel_changes_projection_and_score(inputs):
    knowledge, frame = inputs
    base = RootKGDReasoner(knowledge).analyze(frame, top_k=8)
    top = base["ranked_root_causes"][0]
    channel = next(
        c
        for c, value in zip(
            CHANNELS, top["scoring_details"]["propagated_channel_vector"], strict=True
        )
        if value == 0
    )
    entity = next(
        b["target_id"] for b in knowledge["subject_bindings"] if b["external_id"] == channel
    )
    changed = add_condition(
        KnowledgePackage.model_validate(knowledge),
        "tep",
        CandidateConditionRequest(
            candidate_id=top["candidate_id"],
            label="测试新增通道",
            feature_id="statistics.slope_z",
            op="lte",
            operand={"kind": "number", "number": -1e6, "unit": "1/sample"},
            subject_entity_id=entity,
        ),
        "candidate-condition:" + "9" * 32,
    )
    result = RootKGDReasoner(changed).analyze(frame, top_k=8)
    row = next(
        r for r in result["candidate_evaluations"] if r["candidate_id"] == top["candidate_id"]
    )
    assert row["scoring_details"]["propagated_channel_vector"][CHANNELS.index(channel)] > 0
    assert row["score"] != top["score"]


def test_explicit_effect_relation_is_preserved_and_changes_structure(inputs):
    knowledge, frame = inputs
    base = RootKGDReasoner(knowledge).analyze(frame, top_k=8)
    top, _ = selected_rule(knowledge, base)
    program = KnowledgeProgram(knowledge)
    active = program.hypothesis_world(top)[0]
    target = next(m for m in program.package.mechanisms if m.mechanism_id not in active)
    changed = copy.deepcopy(knowledge)
    changed["effect_rules"].append(
        {
            "rule_id": "r:test-physical-effect",
            "from_id": top,
            "to_id": target.mechanism_id,
            "source_assertion_ids": [knowledge["source_assertions"][0]["assertion_id"]],
        }
    )
    engine = RootKGDReasoner(changed)
    graph, _ = engine._propagation_graph(list(engine.program.hypotheses.values()))
    assert "rootkgd:effect:r:test-physical-effect" in graph["edges"]
    result = engine.analyze(frame, top_k=8)
    row = next(r for r in result["candidate_evaluations"] if r["candidate_id"] == top)
    original = next(r for r in base["candidate_evaluations"] if r["candidate_id"] == top)
    assert (
        row["scoring_details"]["propagated_channel_vector"]
        != original["scoring_details"]["propagated_channel_vector"]
    )


def test_effect_cycle_does_not_eliminate_all_channel_hosts(inputs):
    knowledge, frame = inputs
    base = RootKGDReasoner(knowledge).analyze(frame)
    top, expectation = selected_rule(knowledge, base)
    changed = copy.deepcopy(knowledge)
    source = knowledge["source_assertions"][0]["assertion_id"]
    for name in ("m:test-cycle-a", "m:test-cycle-b"):
        changed["mechanisms"].append({"mechanism_id": name, "label": "测试用循环状态"})
        changed["expectation_rules"].append(
            {
                "rule_id": "r:expect:" + name,
                "from_id": name,
                "pattern_id": expectation.pattern_id,
                "mode": "expected",
                "source_assertion_ids": [source],
            }
        )
    for i, (head, tail) in enumerate(
        (
            (top, "m:test-cycle-a"),
            ("m:test-cycle-a", "m:test-cycle-b"),
            ("m:test-cycle-b", "m:test-cycle-a"),
        )
    ):
        changed["effect_rules"].append(
            {
                "rule_id": f"r:cycle:{i}",
                "from_id": head,
                "to_id": tail,
                "source_assertion_ids": [source],
            }
        )
    engine = RootKGDReasoner(changed)
    graph, _ = engine._propagation_graph(list(engine.program.hypotheses.values()))
    hosts = {link["host_id"] for link in graph["projection"]["host_channel_links"]}
    assert {"m:test-cycle-a", "m:test-cycle-b"} <= hosts
    assert all(f"rootkgd:effect:r:cycle:{i}" in graph["edges"] for i in range(3))
